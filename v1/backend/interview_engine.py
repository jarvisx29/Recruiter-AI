from openai import AsyncOpenAI
import json
import re
import os


def _parse_json(text: str) -> dict:
    """Extract JSON from model output — handles raw JSON or ```json blocks."""
    if text is None:
        raise ValueError("Model returned empty content")
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if match:
        text = match.group(1)
    return json.loads(text)


client = AsyncOpenAI(
    api_key=os.getenv("CEREBRAS_API_KEY"),
    base_url="https://api.cerebras.ai/v1",
)
_MODEL = "gemma-4-31b"  # non-reasoning model: consistent ~60ms, no variable reasoning overhead

DEPTH_LABELS = {1: "surface", 2: "intermediate", 3: "deep"}

JOB_CONTEXT = """
ROLE: Software Support Engineer at Motorq (connected-car data platform serving fleets, insurers, dealers)

INTERVIEW STRUCTURE — follow this order strictly:
1. WARM-UP (opening only): "Tell me a bit about yourself and your technical background." NOT scored — just sets context.
2. Topic 1 — DSA or Programming Fundamentals: establish technical competence first.
3. Topic 2 — SQL or Debugging: domain-specific for this support role.
4. Topic 3 — the other of SQL/Debugging not used in Topic 2.
5. Topic 4 — Projects/Experience LAST: "Earlier you mentioned X — walk me through a specific challenge you hit and how you solved it."

NEVER ask about projects first. Always follow this exact order.

QUESTION STYLE — entry-level, practical, voice-answerable:
- DSA: "Walk me through how you'd find duplicates in a large dataset — what data structure and why?"
- Programming: "How would you debug a Python script that's using way more memory than expected?"
- Debugging: "A production service throws 500 errors every few minutes but only for some users — what's your first move?"
- SQL: "How would you safely update a wrong value in a column for 10,000 rows in production?"
- Projects: dig into WHY they made specific technical decisions, not what the project does.

CANDIDATE CONTEXT: Final-year engineering students, fresh out of college. Entry-level bar only — practical thinking, not senior depth. No advanced internals, no obscure APIs.

SCORING LENS:
- Strong: systematic thinking, explains WHY, mentions edge cases
- Weak: vague, only defines without applying, no tradeoffs mentioned
- Communication: can they explain a technical issue to a non-engineer?
"""


class InterviewEngine:
    def __init__(self, resume_data: dict, position: str, candidate_name: str, candidate_email: str, candidate_phone: str = ""):
        self.resume_data = resume_data
        self.position = position
        self.candidate_name = candidate_name
        self.candidate_email = candidate_email
        self.candidate_phone = candidate_phone

        self.resume_summary = self._build_resume_summary(resume_data)

        self.conversation_history = []
        self.current_topic = None
        self.current_depth = 1
        self.topics_remaining = []
        self.topics_covered = []
        self.topic_scores = {}
        self.interview_plan = None
        self.is_interview_done = False
        self.is_flagged = False
        self.exchanges_on_topic = 0
        self.face_embedding = None
        self._saved_to_admin = False

    def _build_resume_summary(self, r: dict) -> str:
        parts = []
        if r.get("domain"):           parts.append(f"Domain: {r['domain']}")
        if r.get("skills"):           parts.append(f"Skills: {', '.join(r['skills'][:12])}")
        if r.get("strongest_skills"): parts.append(f"Strongest: {', '.join(r['strongest_skills'][:5])}")
        if r.get("weak_claims"):      parts.append(f"Claimed but unverified: {', '.join(r['weak_claims'][:4])}")
        if r.get("projects"):         parts.append(f"Projects: {'; '.join(str(p) for p in r['projects'][:3])}")
        return "\n".join(parts)

    async def get_opening(self) -> str:
        plan_prompt = f"""You are RecruiterAI, a warm and professional Voice AI interviewer for SRM Placements. You are interviewing {self.candidate_name} for: {self.position}.

{JOB_CONTEXT}

Candidate profile:
{self.resume_summary}

Tasks:
1. Pick exactly 4 interview topics following the INTERVIEW STRUCTURE order above.
2. Write a warm opening using their first name that ends with: "Tell me a bit about yourself and your technical background." Do NOT ask a technical question yet.
3. Voice interview only — all questions must be answerable verbally.

Return ONLY valid JSON with the ACTUAL topic names (not placeholders):
{{
    "topics": ["DSA & Problem Solving", "SQL & Databases", "Debugging & Systems", "Projects & Experience"],
    "opening": "Hi Mano, it's great to meet you! Tell me a bit about yourself and your technical background.",
    "first_topic": "DSA & Problem Solving"
}}"""

        response = await client.chat.completions.create(
            model=_MODEL,
            messages=[{"role": "system", "content": plan_prompt}],
            temperature=0.7,
            max_tokens=600,
        )

        plan = _parse_json(response.choices[0].message.content)
        self.interview_plan = plan
        self.topics_remaining = list(plan["topics"])
        self.current_topic = plan["first_topic"]
        self.topics_remaining.remove(self.current_topic)

        opening = plan["opening"]
        self.conversation_history.append({"role": "assistant", "content": opening})
        return opening

    async def process_answer(self, candidate_answer: str) -> dict:
        self.conversation_history.append({"role": "user", "content": candidate_answer})
        self.exchanges_on_topic += 1

        # What topic comes next (so LLM knows exactly what to transition to)
        next_topic_hint = self.topics_remaining[0] if self.topics_remaining else "none — wrap up"

        system_prompt = f"""You are RecruiterAI, a warm and professional Voice AI interviewer for SRM Placements. {self.candidate_name} is applying for: {self.position}.

{JOB_CONTEXT}

INTERVIEW STATE:
- Current topic: {self.current_topic} | Depth: {self.current_depth} ({DEPTH_LABELS.get(self.current_depth)}) | Exchanges on this topic: {self.exchanges_on_topic}
- Topics remaining: {self.topics_remaining}
- Next topic (if you move on): {next_topic_hint}
- Done: {self.topics_covered} | Scores: {self.topic_scores}

CANDIDATE PROFILE:
{self.resume_summary}

CONVERSATION STYLE:
- response_text under 50 words. One question only. No lectures, no preamble.
- Begin with varied acknowledgment: "I see." / "Got it." / "Alright." / "Okay." / "Sure." — never repeat the same one twice in a row.
- Warm, recruiter-like tone. THIS IS A VOICE INTERVIEW — no writing/typing questions.
- When moving to a new topic, include the first question of that NEW topic in the SAME response.

PATIENCE RULES:
- Incomplete answer → "Would you like to add anything?" action: simplify, depth_change: 0.
- Fillers and thinking out loud are normal — do not penalise.
- "I don't know" → acknowledge, offer ONE gentle chance, then move on.

DECISION RULES:
1. DEPTH UP: Strong correct answer → harder follow-up on SAME topic. action: go_deeper, depth_change: 1.
2. DEPTH DOWN: Weak genuine attempt → simpler angle on SAME topic. action: simplify, depth_change: -1.
3. NEXT TOPIC: After 2-3 exchanges, move on. action: next_topic.
   → Your response_text MUST ask the first question for "{next_topic_hint}" — NOT any other topic.
4. WRAP UP: ONLY when Topics remaining is empty. action: wrap_up.

Return ONLY valid JSON (depth_change: integer -1, 0, or 1 — never null):
{{
    "response_text": "Spoken words — under 50 words, one question only",
    "action": "go_deeper" | "simplify" | "next_topic" | "bluff_called" | "wrap_up",
    "topic_score": 1-10,
    "depth_change": -1 or 0 or 1,
    "reasoning": "brief note"
}}"""

        response = await client.chat.completions.create(
            model=_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                *self.conversation_history[-12:]
            ],
            max_tokens=500,
            temperature=0.7,
        )

        result = _parse_json(response.choices[0].message.content)

        raw_depth = result.get("depth_change", 0)
        depth_change = int(raw_depth) if isinstance(raw_depth, (int, float)) else 0
        self.current_depth = max(1, min(3, self.current_depth + depth_change))
        action = result.get("action")

        # Python minimum: never leave a topic after only 1 exchange
        if self.exchanges_on_topic < 2 and action in ["next_topic", "wrap_up"]:
            action = "simplify"
            result["action"] = "simplify"
            result["depth_change"] = 0

        # Python maximum: force topic change after 4 exchanges
        if self.exchanges_on_topic >= 4 and action not in ["next_topic", "wrap_up"]:
            action = "next_topic" if self.topics_remaining else "wrap_up"
            result["action"] = action

        if action in ["next_topic", "bluff_called", "wrap_up"]:
            raw_score = result.get("topic_score", 5)
            score = int(raw_score) if isinstance(raw_score, (int, float)) else 5
            self.topic_scores[self.current_topic] = max(1, score)
            self.topics_covered.append(self.current_topic)

            if self.topics_remaining:
                self.current_topic = self.topics_remaining.pop(0)
                self.current_depth = 1
                self.exchanges_on_topic = 0
            else:
                self.is_interview_done = True
                first_name = self.candidate_name.split()[0]
                result["response_text"] = (
                    f"That's great, {first_name}, thank you so much for your time today. "
                    "This has been a really insightful conversation. "
                    "Our team will review your responses and get back to you shortly. "
                    "Do you have any final questions for me?"
                )

        if result.get("response_text"):
            self.conversation_history.append({"role": "assistant", "content": result["response_text"]})

        result["interview_complete"] = self.is_interview_done
        return result

    def get_current_score(self) -> float:
        if not self.topic_scores:
            return 0.0
        return round(sum(self.topic_scores.values()) / len(self.topic_scores), 1)

    def is_complete(self) -> bool:
        return self.is_interview_done

    def get_final_results(self) -> dict:
        score = self.get_current_score()
        return {
            "candidate": self.candidate_name,
            "email": self.candidate_email,
            "phone": self.candidate_phone,
            "position": self.position,
            "topics_covered": self.topics_covered,
            "topic_scores": self.topic_scores,
            "overall_score": score,
            "max_depth_reached": self.current_depth,
            "recommendation": "Hire" if score >= 6.5 else "Hold" if score >= 5.0 else "Reject",
            "transcript": self.conversation_history,
            "is_flagged": self.is_flagged,
        }
