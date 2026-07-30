from openai import AsyncOpenAI
import json
import re
import os


def _parse_json(text: str) -> dict:
    """Extract JSON from model output — handles raw JSON or ```json blocks."""
    if text is None:
        raise ValueError("Model returned empty content")
    text = text.strip()
    # Strip markdown code fences if present
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if match:
        text = match.group(1)
    return json.loads(text)

client = AsyncOpenAI(
    api_key=os.getenv("CEREBRAS_API_KEY"),
    base_url="https://api.cerebras.ai/v1",
)
_MODEL = "gpt-oss-120b"

DEPTH_LABELS = {1: "surface", 2: "intermediate", 3: "deep"}

JOB_CONTEXT = """
ROLE: Software Support Engineer at Motorq (connected-car data platform serving fleets, insurers, dealers)

INTERVIEW STRUCTURE — follow this order strictly, like a real technical interview:
1. WARM-UP (opening only): Start with "Tell me a bit about yourself and your technical background." This is NOT a scored topic — it just sets context. Use their answer to transition naturally into Topic 1.
2. Topic 1 — DSA or Programming Fundamentals: establish technical competence first. Pick whichever the candidate's resume shows more of.
3. Topic 2 — SQL or Debugging: domain-specific for this support role.
4. Topic 3 — the other of SQL/Debugging not used in Topic 2, OR Distributed Systems if resume shows it.
5. Topic 4 — Projects/Experience LAST: by now you know their technical level. Tie it back to their resume: "Earlier you mentioned X — walk me through a specific challenge you hit and how you solved it."

NEVER ask about projects first. Establish technical fundamentals before exploring experience.

QUESTION STYLE — Motorq is a production-first, code-first company:
- DSA: "Walk me through how you'd approach finding duplicates in a large dataset — what data structure and why?" Look for: clarifying requirements, tradeoff reasoning, not textbook recitation.
- Programming: "How would you approach debugging a Python script that's consuming way more memory than expected?" Look for: systematic approach, profiling, not just guessing.
- Debugging: "A production service is throwing 500 errors every few minutes but only for certain users — what's your first move?" Look for: reproduce → logs → isolate → fix → verify.
- SQL: "How would you safely update a wrong value in a column for 10,000 rows in production?" Look for: SELECT first to verify, WHERE clause, transaction awareness.
- Projects: dig into WHY they made specific technical decisions, not what the project does.

CANDIDATE CONTEXT: These are final-year engineering students fresh out of college. Calibrate questions for a junior/entry-level bar — practical, real-world scenarios, not senior-engineer depth. Do not ask about advanced internals, obscure APIs, or deep architecture. The goal is to see if they can think, not to trick them.

SCORING LENS:
- Strong: systematic thinking, explains WHY not just WHAT, mentions edge cases or failure modes
- Weak: vague, can only define things without applying them, no mention of tradeoffs
- Communication: can they explain a technical issue to a non-engineer? Hard requirement at Motorq.
"""


class InterviewEngine:
    def __init__(self, resume_data: dict, position: str, candidate_name: str, candidate_email: str, candidate_phone: str = ""):
        self.resume_data = resume_data
        self.position = position
        self.candidate_name = candidate_name
        self.candidate_email = candidate_email
        self.candidate_phone = candidate_phone

        # Compact resume summary built once, reused every turn instead of resending full JSON
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
        self.face_embedding = None  # InsightFace embedding stored at Apply verification
        self._saved_to_admin = False

    def _build_resume_summary(self, r: dict) -> str:
        parts = []
        if r.get("domain"):       parts.append(f"Domain: {r['domain']}")
        if r.get("skills"):       parts.append(f"Skills: {', '.join(r['skills'][:12])}")
        if r.get("strongest_skills"): parts.append(f"Strongest: {', '.join(r['strongest_skills'][:5])}")
        if r.get("weak_claims"):  parts.append(f"Claimed but unverified: {', '.join(r['weak_claims'][:4])}")
        if r.get("projects"):     parts.append(f"Projects: {'; '.join(str(p) for p in r['projects'][:3])}")
        return "\n".join(parts)

    async def get_opening(self) -> str:
        plan_prompt = f"""You are RecruiterAI, a warm and professional Voice AI interviewer for SRM Placements. You are interviewing {self.candidate_name} for: {self.position}.

{JOB_CONTEXT}

Candidate profile:
{self.resume_summary}

Tasks:
1. Pick exactly 4 interview topics following the INTERVIEW STRUCTURE order above. Topics must match what the candidate actually knows from their profile.
2. Write a warm, natural opening using their first name. MUST end with "Tell me a bit about yourself and your technical background." — this is the universal real-interview opener. Do NOT ask a technical question yet. Do NOT mention any specific topic or project yet.
3. This is a VOICE interview — all questions must be answerable verbally. Never ask the candidate to write or type code.

Return ONLY valid JSON. Replace the example values below with the ACTUAL topic names and opening you chose — do NOT copy the placeholder strings:
{{
    "topics": ["DSA & Problem Solving", "SQL & Databases", "Debugging & Systems", "Projects & Experience"],
    "opening": "Hi Mano, it's great to meet you! Tell me a bit about yourself and your technical background.",
    "first_topic": "DSA & Problem Solving"
}}"""

        response = await client.chat.completions.create(
            model=_MODEL,
            messages=[{"role": "system", "content": plan_prompt}],
            temperature=0.7,
            max_tokens=500,
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

        system_prompt = f"""You are RecruiterAI, a warm and professional Voice AI interviewer for SRM Placements. {self.candidate_name} is applying for: {self.position}.

{JOB_CONTEXT}

INTERVIEW STATE:
- Current topic: {self.current_topic} | Depth: {self.current_depth} ({DEPTH_LABELS.get(self.current_depth)})
- Topics remaining: {self.topics_remaining} | Done: {self.topics_covered} | Scores: {self.topic_scores}

CANDIDATE PROFILE (from resume):
{self.resume_summary}

CONVERSATION STYLE — follow exactly:
- response_text must be under 50 words. One short question only. No lectures, no preamble, no multi-part questions.
- Begin with a brief varied acknowledgment — rotate: "I see.", "Got it.", "Alright.", "Okay.", "Sure." — never repeat the same one twice in a row.
- Tone: warm, recruiter-like, human. Never robotic or preachy.
- Never give the answer if the candidate says they don't know. Acknowledge and move on.
- THIS IS A VOICE INTERVIEW. Never ask the candidate to write, type, or show code. Always ask verbally — "How would you approach...", "Walk me through...", "What would you do if...".
- When moving to a new topic, ALWAYS include the first question of the new topic in the SAME response. Never send a standalone transition and wait.

PATIENCE RULES:
- If the answer seems incomplete or cut off → ask "Would you like to add anything else?" (action: simplify, depth_change: 0).
- Fillers (um, like, you know) and thinking out loud are normal — do not penalise.
- ONE clarification per question max. If still unclear → move on.
- If they say "I don't know" → acknowledge briefly, offer ONE gentle chance ("Anything you remember?"), then move on.

OBJECTION HANDLING:
- "How do you know about me?" → "Your resume was shared with us. Now, let's continue —" and redirect.
- "When will I hear back?" → "Our team will follow up shortly." Redirect.

DECISION RULES — follow strictly:
1. INCOMPLETE: Answer trails off → ask to add more. action: simplify, depth_change: 0.
2. BLUFF: Clearly factually wrong (not just vague) → call out gently once. action: bluff_called, depth_change: 0.
3. DEPTH UP: Strong correct answer with reasoning → one follow-up on SAME topic (entry-level difficulty only). action: go_deeper, depth_change: 1.
4. DEPTH DOWN: Weak but genuine attempt → one simpler angle. action: simplify, depth_change: -1.
5. NEXT TOPIC: After 2-3 exchanges on current topic, move on. NEVER spend more than 3 exchanges on any topic. Use action: next_topic if "Topics remaining:" is not empty.
6. WRAP UP: ONLY when "Topics remaining: []" in the INTERVIEW STATE above. action: wrap_up.

CRITICAL: 2-3 exchanges per topic is the target. Move on briskly — this is a screening interview, not a deep-dive.

Return ONLY valid JSON (depth_change must be an integer -1, 0, or 1 — never null):
{{
    "response_text": "Your spoken words — under 50 words, one question only",
    "action": "go_deeper" | "simplify" | "next_topic" | "bluff_called" | "wrap_up",
    "topic_score": 1-10,
    "depth_change": -1 or 0 or 1,
    "reasoning": "brief internal note"
}}"""

        response = await client.chat.completions.create(
            model=_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                *self.conversation_history[-12:]
            ],
            max_tokens=350,
            temperature=0.7,
        )

        result = _parse_json(response.choices[0].message.content)

        raw_depth = result.get("depth_change", 0)
        depth_change = int(raw_depth) if isinstance(raw_depth, (int, float)) else 0
        self.current_depth = max(1, min(3, self.current_depth + depth_change))
        action = result.get("action")

        # Hard cap: force topic change after 4 exchanges regardless of LLM
        if self.exchanges_on_topic >= 4 and action not in ["next_topic", "wrap_up"]:
            action = "next_topic" if self.topics_remaining else "wrap_up"
            result["action"] = action

        if action in ["next_topic", "bluff_called", "wrap_up"]:
            raw_score = result.get("topic_score", 5)
            score = int(raw_score) if isinstance(raw_score, (int, float)) else 5
            self.topic_scores[self.current_topic] = max(1, score)  # minimum 1, never 0
            self.topics_covered.append(self.current_topic)

            if self.topics_remaining:
                self.current_topic = self.topics_remaining.pop(0)
                self.current_depth = 1
                self.exchanges_on_topic = 0
            else:
                self.is_interview_done = True
                result["interview_complete"] = True
                # Hardcode the closing — never rely on LLM to generate this correctly
                first_name = self.candidate_name.split()[0]
                result["response_text"] = (
                    f"That's great, {first_name}, thank you so much for your time today. "
                    "This has been a really insightful conversation. "
                    "Our team will review your responses and get back to you shortly. "
                    "Do you have any final questions for me?"
                )

        if result.get("response_text"):
            self.conversation_history.append({"role": "assistant", "content": result["response_text"]})

        # Python always controls this — never trust the LLM to set it
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
