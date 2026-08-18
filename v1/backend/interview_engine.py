from anthropic import AsyncAnthropic
import json
import re
import os

_IDK_RE = re.compile(
    r"\b(i don'?t know|no idea|not sure|can'?t answer|have no clue|no clue|"
    r"i'?m not sure|i give up|i'?m lost|don'?t understand|have no idea|"
    r"cannot answer|not familiar|never (heard|learned|studied)|blank)\b",
    re.IGNORECASE,
)


def _parse_json(text: str) -> dict:
    """Extract JSON from model output — handles raw JSON, ```json blocks, and embedded JSON."""
    if not text:
        raise ValueError("Model returned empty content")
    text = text.strip()
    # Try ```json block first
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if match:
        return json.loads(match.group(1))
    # Try raw JSON
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Extract outermost JSON object from free text
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        return json.loads(match.group(0))
    raise ValueError(f"No valid JSON in model response: {text[:200]}")


client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
_MODEL = "claude-haiku-4-5-20251001"

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
        self.topic_idk_count = 0       # "I don't know" count for current topic
        self.topic_simplify_count = 0   # depth-down moves for current topic
        self.topic_depth_peaked = False  # whether depth ever increased on this topic
        self.topic_technical_started = False  # True once first real technical exchange lands
        self.total_answers_seen = 0    # safety fallback — all answers regardless of phase

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

        response = await client.messages.create(
            model=_MODEL,
            system=plan_prompt,
            messages=[
                {"role": "user", "content": "Begin the interview."},
                {"role": "assistant", "content": "{"},
            ],
            temperature=0.7,
            max_tokens=1024,
        )

        plan = _parse_json("{" + (response.content[0].text or ""))
        self.interview_plan = plan
        self.topics_remaining = list(plan["topics"])
        self.current_topic = plan["first_topic"]
        self.topics_remaining.remove(self.current_topic)

        opening = plan["opening"]
        self.conversation_history.append({"role": "assistant", "content": opening})
        return opening

    async def process_answer(self, candidate_answer: str) -> dict:
        self.conversation_history.append({"role": "user", "content": candidate_answer})
        self.total_answers_seen += 1
        # exchanges_on_topic and IDK only count AFTER the first real technical question lands.
        # Pre-phase: warmup, off-topic questions, self-intro don't pollute the topic score.
        if self.topic_technical_started:
            if len(candidate_answer.split()) >= 3:
                self.exchanges_on_topic += 1
            if _IDK_RE.search(candidate_answer):
                self.topic_idk_count += 1

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

HOW TO USE THE PROFILE:
- In DSA/SQL/Debugging topics: tie at least one question to their actual tech stack. E.g. if they know Python, ask "How would you do this in Python?" or "You listed SQL as a skill — walk me through...".
- In Projects topic: ALWAYS open by naming their actual project. E.g. "Earlier you mentioned your AI Recruitment Pipeline — walk me through a specific technical challenge you hit and how you solved it." Probe WHY they made specific choices (language, library, architecture).
- Never ask generic questions when their profile gives you something specific to probe.

CONVERSATION STYLE:
- response_text 40-70 words. One question only. Sound like a real, friendly interviewer.
- Open with a WARM, varied reaction — not a single filler word. Examples:
    "Nice thinking! Let's push that a bit further —"
    "That's a solid start — I like how you're thinking about it. Let me ask you this:"
    "Great, that makes sense! Now here's a trickier angle:"
    "Okay, good instinct! One follow-up:"
    "Exactly right — hash sets are perfect here. Let me dig a little deeper:"
  Vary it every response. Never say just "I see." or "Got it." alone.
- Warm, encouraging, recruiter-like tone. THIS IS A VOICE INTERVIEW.
- When moving to a new topic, briefly signal it: "Let's shift gears now." or "Moving on — " then ask the first question of the new topic.

PATIENCE RULES:
- Incomplete answer → sound encouraging, e.g. "No worries, take your time — could you walk me through even just the first step you'd take?" action: simplify, depth_change: 0.
- Fillers and thinking out loud are normal — do not penalise.
- "I don't know" → give a concrete hint first, e.g. "That's okay! Here's a clue — think about what tool you'd open first. What would you check?" action: simplify, depth_change: -1. Only move on if they say "I don't know" a SECOND time.

DECISION RULES:
1. DEPTH UP: Strong correct answer → harder follow-up on SAME topic. action: go_deeper, depth_change: 1.
2. DEPTH DOWN: Weak genuine attempt → simpler angle on SAME topic. action: simplify, depth_change: -1.
3. NEXT TOPIC: After 2-3 exchanges, move on. action: next_topic.
   → Your response_text MUST ask the first question for "{next_topic_hint}" — NOT any other topic.
4. WRAP UP: ONLY when Topics remaining is empty. action: wrap_up.

STRICT SCORING RUBRIC — score ONLY the technical question-answer exchanges, NOT the warmup intro or off-topic chitchat:
- 9-10: Unprompted depth, explains tradeoffs and edge cases, correct approach with no hints
- 7-8: Correct approach with some depth, minor gaps, handled follow-ups well, no IDK
- 5-6: Partial understanding, needed one hint, direction correct but missing key details
- 3-4: Vague or partially wrong, needed multiple hints or simplifications to stay engaged
- 1-2: Said "I don't know", gave up, completely off-track even after hints
A friendly "I don't know" is STILL a 2. Effort and politeness do NOT raise the score. Off-topic questions ("how long will this take?") do NOT raise or lower the score.

Return ONLY valid JSON (depth_change: integer -1, 0, or 1 — never null):
{{
    "response_text": "Spoken words — under 70 words, one question only",
    "action": "go_deeper" | "simplify" | "next_topic" | "bluff_called" | "wrap_up",
    "topic_score": 1-10,
    "depth_change": -1 or 0 or 1,
    "reasoning": "brief note"
}}"""

        result = None
        last_err = None
        for _attempt in range(3):
            try:
                response = await client.messages.create(
                    model=_MODEL,
                    system=system_prompt,
                    messages=self.conversation_history[-12:] + [{"role": "assistant", "content": "{"}],
                    max_tokens=1024,
                    temperature=0.7,
                )
                result = _parse_json("{" + (response.content[0].text or ""))
                break
            except (ValueError, Exception) as _e:
                last_err = _e
                print(f"[process_answer retry {_attempt+1}] {type(_e).__name__}: {_e}", flush=True)
        if result is None:
            # Undo the user message we appended — prevents consecutive user messages
            # in history that cause all future LLM calls to also fail.
            if (self.conversation_history
                    and self.conversation_history[-1].get("role") == "user"
                    and self.conversation_history[-1].get("content") == candidate_answer):
                self.conversation_history.pop()
            raise last_err

        raw_depth = result.get("depth_change", 0)
        depth_change = int(raw_depth) if isinstance(raw_depth, (int, float)) else 0
        if depth_change > 0:
            self.topic_depth_peaked = True
        if depth_change < 0:
            self.topic_simplify_count += 1
        self.current_depth = max(1, min(3, self.current_depth + depth_change))
        action = result.get("action")

        # Mark technical phase started the first time LLM engages technically on this topic.
        # This means warmup answers, off-topic questions, self-intros don't inflate counters.
        if not self.topic_technical_started and action in ("go_deeper", "simplify", "next_topic", "bluff_called"):
            self.topic_technical_started = True
            self.exchanges_on_topic = 1  # this answer is the first real technical exchange
            self.topic_idk_count = 0     # reset — don't penalise warmup IDKs

        # Python minimum: never leave a topic after only 1 real technical exchange
        if self.exchanges_on_topic < 2 and action in ["next_topic", "wrap_up"]:
            action = "simplify"
            result["action"] = "simplify"
            result["depth_change"] = 0

        # Python maximum: force topic change after 4 real exchanges (safety fallback for total answers too)
        if (self.exchanges_on_topic >= 4 or self.total_answers_seen >= 10) and action not in ["next_topic", "wrap_up"]:
            action = "next_topic" if self.topics_remaining else "wrap_up"
            result["action"] = action

        if action in ["next_topic", "bluff_called", "wrap_up"]:
            raw_score = result.get("topic_score", 5)
            score = int(raw_score) if isinstance(raw_score, (int, float)) else 5

            # Hard caps based on observed IDK count — LLM scores tend to be generous
            if self.topic_idk_count >= 2:
                score = min(score, 3)
            elif self.topic_idk_count == 1:
                score = min(score, 5)
            # Penalise if depth never increased and needed multiple simplifications
            if not self.topic_depth_peaked and self.topic_simplify_count >= 2:
                score = min(score, 4)

            self.topic_scores[self.current_topic] = max(1, score)
            self.topics_covered.append(self.current_topic)
            print(
                f"[score] {self.current_topic}: LLM={raw_score} → final={score} "
                f"(idks={self.topic_idk_count}, simplifies={self.topic_simplify_count}, "
                f"depth_peaked={self.topic_depth_peaked})",
                flush=True,
            )

            if self.topics_remaining:
                self.current_topic = self.topics_remaining.pop(0)
                self.current_depth = 1
                self.exchanges_on_topic = 0
                self.topic_idk_count = 0
                self.topic_simplify_count = 0
                self.topic_depth_peaked = False
                self.topic_technical_started = True   # subsequent topics start technical immediately
                self.total_answers_seen = 0
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
            "recommendation": "Hire" if score >= 7.0 else "Hold" if score >= 5.0 else "Reject",
            "transcript": self.conversation_history,
            "is_flagged": self.is_flagged,
        }
