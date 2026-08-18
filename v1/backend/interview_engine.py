from anthropic import AsyncAnthropic
import json
import re
import os

_IDK_RE = re.compile(
    r"\b(i don'?t know|no idea|not sure|can'?t answer|have no clue|no clue|"
    r"i'?m not sure|i give up|i'?m lost|don'?t understand|have no idea|"
    r"cannot answer|not familiar|never (heard|learned|studied)|i'?m? blank|"
    r"i'?m? stuck|i have no|beats me|no clue)\b",
    re.IGNORECASE,
)

# topic name → score weight for final recommendation (support engineer role: DSA+SQL > Projects)
_TOPIC_WEIGHTS = {
    "dsa": 1.3, "algorithm": 1.3, "programming": 1.2,
    "sql": 1.2, "database": 1.2,
    "debug": 1.1, "system": 1.1,
    "project": 0.9, "experience": 0.9,
}


def _topic_weight(topic_name: str) -> float:
    name = topic_name.lower()
    for key, w in _TOPIC_WEIGHTS.items():
        if key in name:
            return w
    return 1.0


def _parse_json(text: str) -> dict:
    if not text:
        raise ValueError("Model returned empty content")
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if match:
        return json.loads(match.group(1))
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        return json.loads(match.group(0))
    raise ValueError(f"No valid JSON in model response: {text[:200]}")


client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
_MODEL = "claude-haiku-4-5-20251001"

DEPTH_LABELS = {1: "surface", 2: "intermediate", 3: "deep"}

JOB_CONTEXT = """
ROLE: Software Support Engineer at Motorq (connected-car data platform serving fleets, insurers, dealers).
TARGET: Final-year engineering students. Entry-level bar — practical thinking over theory depth.

═══ INTERVIEW STRUCTURE (follow this order, never deviate) ═══
1. WARM-UP (opening only): "Tell me about yourself." — NOT scored.
   • 2 responses MAX in warm-up. After 2 candidate responses, pivot to Topic 1 REGARDLESS.
   • If candidate asks meta-questions (duration, role details, "how do you know me"), answer in ONE sentence then immediately start Topic 1.
2. Topic 1 — DSA or Programming Fundamentals first.
3. Topic 2 — SQL or Debugging.
4. Topic 3 — whichever of SQL/Debugging was NOT used in Topic 2.
5. Topic 4 — Projects/Experience LAST: name their ACTUAL project from their profile.

═══ DEPTH SCALE (use this to decide depth_change) ═══
Surface (depth 1) — WHAT and HOW:       "What data structure would you use?"
Intermediate (depth 2) — WHY + tradeoffs: "Why that over a sorted list? What's the tradeoff?"
Deep (depth 3) — edge cases + scale:    "What if the dataset doesn't fit in memory? How does your approach change?"
Start every topic at surface. Go deeper only on strong, correct answers.

═══ QUESTION STYLE — voice-answerable, tied to their actual tech stack ═══
- DSA: "Walk me through finding all duplicates in a list of a million numbers. What data structure and why?"
- Debugging: "A live API throws 500 errors every few minutes for some users but not others. What are your first three moves?"
- SQL: "You need to fix 10,000 wrong values in a production column. How do you do it safely?"
- Projects: "You mentioned [THEIR ACTUAL PROJECT NAME] — what was the hardest bug or technical decision you faced, and how did you solve it?"
Always tie questions to what's in the candidate profile. Never ask generic questions when their profile gives you something specific.

═══ CRITICAL RULES ═══
ONE QUESTION ONLY per response. Never ask two things. Never use "and also" or "additionally".
NO REPEATED ANGLES: don't ask two questions that test the same concept on one topic.
ANTI-BLUFF: If the candidate states something factually wrong with confidence (e.g., "dictionaries don't allow duplicates", "you don't need a WHERE in UPDATE"), immediately challenge it:
  "Let me push back on that — [one-sentence correction]. Given that, how does your approach change?" → action: bluff_called
PATIENCE: Incomplete answer → encourage, simplify. "I don't know" → give ONE concrete hint. If IDK a second time → next_topic.
"""


class InterviewEngine:
    def __init__(self, resume_data: dict, position: str, candidate_name: str,
                 candidate_email: str, candidate_phone: str = ""):
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
        self.face_embedding = None
        self._saved_to_admin = False

        # Per-topic counters — reset on every topic transition
        self.exchanges_on_topic = 0     # real technical exchanges only
        self.topic_idk_count = 0        # IDK signals on this topic
        self.topic_simplify_count = 0   # depth-down moves
        self.topic_depth_peaked = False  # depth ever went up
        self.topic_bluff_count = 0      # bluff_called events on this topic
        self.topic_technical_started = False  # warmup phase over?

        # Safety counters (reset per topic)
        self.total_answers_seen = 0     # all answers including pre-technical

        # Interview-wide counters
        self.interview_bluff_total = 0

    def _build_resume_summary(self, r: dict) -> str:
        parts = []
        if r.get("domain"):           parts.append(f"Domain: {r['domain']}")
        if r.get("skills"):           parts.append(f"Skills: {', '.join(r['skills'][:12])}")
        if r.get("strongest_skills"): parts.append(f"Strongest: {', '.join(r['strongest_skills'][:5])}")
        if r.get("weak_claims"):      parts.append(f"Claimed but unverified: {', '.join(r['weak_claims'][:4])}")
        if r.get("projects"):         parts.append(f"Projects: {'; '.join(str(p) for p in r['projects'][:3])}")
        return "\n".join(parts)

    def _build_history_for_llm(self) -> list:
        """Always include the opening context (first 2 msgs) so the Projects topic
        can reference what the candidate said about themselves."""
        if len(self.conversation_history) <= 14:
            return self.conversation_history
        # Keep opening (first 2) + most recent 12
        return self.conversation_history[:2] + self.conversation_history[-12:]

    def _reset_topic_counters(self, technical_started: bool = True) -> None:
        self.exchanges_on_topic = 0
        self.topic_idk_count = 0
        self.topic_simplify_count = 0
        self.topic_depth_peaked = False
        self.topic_bluff_count = 0
        self.topic_technical_started = technical_started
        self.total_answers_seen = 0

    async def get_opening(self) -> str:
        plan_prompt = f"""You are RecruiterAI, a warm and professional Voice AI interviewer for SRM Placements.
You are interviewing {self.candidate_name} for: {self.position}.

{JOB_CONTEXT}

Candidate profile:
{self.resume_summary}

Tasks:
1. Pick exactly 4 interview topics following the INTERVIEW STRUCTURE order above.
2. Write a warm, natural opening using their first name that ends with asking them to tell you about themselves. Keep it under 40 words. Do NOT ask a technical question yet.
3. Voice interview only — all questions must be answerable verbally.

Return ONLY valid JSON with the ACTUAL topic names from their profile context (not generic placeholders):
{{
    "topics": ["DSA & Problem Solving", "SQL & Databases", "Debugging & Systems", "Projects & Experience"],
    "opening": "Hi Mano, great to meet you! Tell me a bit about yourself and your technical background.",
    "first_topic": "DSA & Problem Solving"
}}"""

        response = await client.messages.create(
            model=_MODEL,
            system=plan_prompt,
            messages=[
                {"role": "user", "content": "Begin the interview."},
                {"role": "assistant", "content": "{"},
            ],
            temperature=0.3,
            max_tokens=512,
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

        # IDK detection fires at any length — even "I don't know" (3 words)
        is_idk = bool(_IDK_RE.search(candidate_answer))
        is_substantial = len(candidate_answer.split()) >= 5  # real answer threshold

        # Counters only run after the first real technical engagement on this topic
        if self.topic_technical_started:
            if is_substantial:
                self.exchanges_on_topic += 1
            if is_idk:
                self.topic_idk_count += 1

        next_topic_hint = self.topics_remaining[0] if self.topics_remaining else "none — wrap up"

        system_prompt = f"""You are RecruiterAI, a warm and professional Voice AI interviewer for SRM Placements.
{self.candidate_name} is applying for: {self.position}.

{JOB_CONTEXT}

INTERVIEW STATE:
- Current topic: {self.current_topic} | Depth: {self.current_depth} ({DEPTH_LABELS.get(self.current_depth)})
- Technical exchanges on this topic: {self.exchanges_on_topic} | IDKs: {self.topic_idk_count}
- Topics done: {self.topics_covered} | Topics remaining: {self.topics_remaining}
- Next topic (use this exact name when transitioning): "{next_topic_hint}"
- Scores so far: {self.topic_scores}

CANDIDATE PROFILE:
{self.resume_summary}

HOW TO USE THE PROFILE:
- DSA/SQL/Debugging: anchor at least one question to their actual tech stack (e.g., "You listed Python — how would you write this in Python?").
- Projects topic: ALWAYS open by naming the ACTUAL project from their profile. Probe the WHY behind technical decisions, not what it does.
- Never ask generic questions when the profile gives you something specific to probe.

RESPONSE STYLE:
- 40-60 words. ONE question only. Never ask two things in one response.
- Open with a warm, VARIED reaction (not just "Got it." or "I see."):
    "Nice thinking! Let's push further —"  |  "Good instinct — but let me dig a bit deeper:"
    "That's a solid start. One follow-up:"  |  "Exactly right. Now here's a harder angle:"
    "Interesting approach! Let me challenge that slightly:"
- Voice interview: no bullet lists, no markdown, natural spoken language only.
- When moving to a new topic: signal it clearly: "Alright, let's shift gears." then ask the FIRST question of "{next_topic_hint}".

DECISION RULES:
1. DEPTH UP (go_deeper, depth_change: 1): Candidate gave a correct, substantial answer → ask a harder follow-up on the same concept.
2. DEPTH DOWN (simplify, depth_change: -1): Weak or incomplete attempt → encourage + ask a simpler angle.
3. SAME DEPTH (go_deeper or simplify, depth_change: 0): Partial answer — probe the missing piece.
4. NEXT TOPIC (next_topic): Move on after 2-3 real exchanges, OR after IDK twice on this topic.
   → response_text MUST ask the first question of "{next_topic_hint}" specifically.
5. BLUFF CALLED (bluff_called): Candidate stated something factually wrong with confidence → correct it directly, then re-ask.
6. WRAP UP (wrap_up): ONLY when topics_remaining is empty. Generate a warm, natural closing (40-50 words).

WARM-UP RULE: If we're still in the introduction phase and the candidate hasn't answered a real technical question yet, ask your first technical question for {self.current_topic} NOW. Don't extend warm-up beyond 2 responses.

STRICT SCORING RUBRIC (topic_score 1-10 — score ONLY the technical exchanges, not warm-up or off-topic chat):
- 9-10: Correct + unprompted depth. Explained WHY, mentioned edge cases, no hints needed.
- 7-8: Correct approach, some depth, handled follow-up well, no IDK.
- 5-6: Partially correct, needed one hint, right direction but missing key details.
- 3-4: Vague or mostly wrong, needed multiple simplifications, couldn't apply the concept.
- 1-2: Said IDK, gave up, factually wrong even after correction, or bluffed with jargon.
Confident + wrong = 2-3, not 5-6. A friendly IDK is still a 2. Politeness does NOT raise the score.
Off-topic questions ("how long?", "who are you?") do NOT affect the score.

Return ONLY valid JSON (depth_change must be -1, 0, or 1 — never null, never missing):
{{
    "response_text": "Your spoken words here — 40-60 words, one question only",
    "action": "go_deeper" | "simplify" | "next_topic" | "bluff_called" | "wrap_up",
    "topic_score": 1-10,
    "depth_change": -1 | 0 | 1,
    "reasoning": "one sentence on why this score/action"
}}"""

        result = None
        last_err = None
        for _attempt in range(3):
            try:
                response = await client.messages.create(
                    model=_MODEL,
                    system=system_prompt,
                    messages=self._build_history_for_llm() + [{"role": "assistant", "content": "{"}],
                    max_tokens=512,
                    temperature=0.4,
                )
                result = _parse_json("{" + (response.content[0].text or ""))
                break
            except (ValueError, Exception) as _e:
                last_err = _e
                print(f"[process_answer retry {_attempt+1}] {type(_e).__name__}: {_e}", flush=True)

        if result is None:
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
        action = result.get("action", "simplify")

        # Detect the first real technical engagement — flip the warmup gate
        if not self.topic_technical_started and action in ("go_deeper", "simplify", "next_topic", "bluff_called"):
            self.topic_technical_started = True
            # Count this answer as the first real exchange and reset warmup-era IDK noise
            if is_substantial:
                self.exchanges_on_topic = 1
            self.topic_idk_count = 1 if is_idk else 0

        if action == "bluff_called":
            self.topic_bluff_count += 1
            self.interview_bluff_total += 1

        # HARD RULES — Python overrides LLM
        # Minimum: don't leave a topic after only 1 real exchange
        if self.exchanges_on_topic < 2 and action in ("next_topic", "wrap_up"):
            action = "simplify"
            result["action"] = "simplify"
            result["depth_change"] = 0

        # Maximum: force topic change after 4 real exchanges OR 12 total answers on topic
        if (self.exchanges_on_topic >= 4 or self.total_answers_seen >= 12) and action not in ("next_topic", "wrap_up"):
            action = "next_topic" if self.topics_remaining else "wrap_up"
            result["action"] = action

        if action in ("next_topic", "bluff_called", "wrap_up"):
            raw_score = result.get("topic_score", 5)
            score = int(raw_score) if isinstance(raw_score, (int, float)) else 5

            # If no real technical exchanges happened on this topic → score 1
            if self.exchanges_on_topic == 0:
                score = 1
                print(f"[score] {self.current_topic}: forced to 1 (no technical exchanges)", flush=True)
            else:
                # IDK caps
                if self.topic_idk_count >= 2:
                    score = min(score, 3)
                elif self.topic_idk_count == 1:
                    score = min(score, 5)
                # Bluff penalty — confident wrong answers lower the ceiling
                if self.topic_bluff_count >= 1:
                    score = min(score, score - 1)
                # No depth progress + multiple simplifications
                if not self.topic_depth_peaked and self.topic_simplify_count >= 2:
                    score = min(score, 4)
                print(
                    f"[score] {self.current_topic}: LLM={raw_score} → final={max(1, score)} "
                    f"(idks={self.topic_idk_count}, bluffs={self.topic_bluff_count}, "
                    f"simplifies={self.topic_simplify_count}, depth_peaked={self.topic_depth_peaked}, "
                    f"exchanges={self.exchanges_on_topic})",
                    flush=True,
                )

            self.topic_scores[self.current_topic] = max(1, score)
            self.topics_covered.append(self.current_topic)

            if self.topics_remaining:
                self.current_topic = self.topics_remaining.pop(0)
                self.current_depth = 1
                self._reset_topic_counters(technical_started=True)  # subsequent topics are all technical
            else:
                self.is_interview_done = True

        if result.get("response_text"):
            self.conversation_history.append({"role": "assistant", "content": result["response_text"]})

        result["interview_complete"] = self.is_interview_done
        return result

    def get_current_score(self) -> float:
        if not self.topic_scores:
            return 0.0
        total_weighted = sum(s * _topic_weight(t) for t, s in self.topic_scores.items())
        total_weight = sum(_topic_weight(t) for t in self.topic_scores)
        return round(total_weighted / total_weight, 1)

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
            "bluff_events": self.interview_bluff_total,
        }
