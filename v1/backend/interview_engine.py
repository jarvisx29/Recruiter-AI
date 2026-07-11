from groq import AsyncGroq
import json
import os

client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))

DEPTH_LABELS = {1: "surface", 2: "intermediate", 3: "deep"}


class InterviewEngine:
    def __init__(self, resume_data: dict, position: str, candidate_name: str, candidate_email: str):
        self.resume_data = resume_data
        self.position = position
        self.candidate_name = candidate_name
        self.candidate_email = candidate_email

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
        self.face_embedding = None  # InsightFace embedding stored at Apply verification

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

Candidate profile:
{self.resume_summary}

Tasks:
1. Pick 4 interview topics from their actual skills, most relevant to the position.
2. Write a warm, natural 2-sentence opening using their first name — friendly but professional, like a real human recruiter. Do NOT over-introduce. Get to the point.
3. Immediately ask the first question on the first topic at surface level. Keep it concise.

Return ONLY valid JSON:
{{
    "topics": ["topic1", "topic2", "topic3", "topic4"],
    "opening": "Full opening statement including first question",
    "first_topic": "topic1"
}}"""

        response = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": plan_prompt}],
            response_format={"type": "json_object"}
        )

        plan = json.loads(response.choices[0].message.content)
        self.interview_plan = plan
        self.topics_remaining = list(plan["topics"])
        self.current_topic = plan["first_topic"]
        self.topics_remaining.remove(self.current_topic)

        opening = plan["opening"]
        self.conversation_history.append({"role": "assistant", "content": opening})
        return opening

    async def process_answer(self, candidate_answer: str) -> dict:
        self.conversation_history.append({"role": "user", "content": candidate_answer})

        system_prompt = f"""You are RecruiterAI, a warm and professional Voice AI interviewer for SRM Placements. {self.candidate_name} is applying for: {self.position}.

INTERVIEW STATE:
- Current topic: {self.current_topic} | Depth: {self.current_depth} ({DEPTH_LABELS.get(self.current_depth)})
- Topics remaining: {self.topics_remaining} | Done: {self.topics_covered} | Scores: {self.topic_scores}

CANDIDATE PROFILE (from resume):
{self.resume_summary}

CONVERSATION STYLE — follow exactly:
- Responses must be SHORT. One question at a time. No lectures, no explanations, no long intros.
- Begin with a brief varied acknowledgment — rotate through: "I see.", "Got it.", "Alright.", "Okay.", "Sure." — never repeat the same one twice in a row.
- Tone: warm, recruiter-like, human. Never robotic, never preachy, never silent.
- Never provide the answer if the candidate says they don't know. Just acknowledge and move on.

PATIENCE RULES (from Retell v0 — follow exactly):
- If the answer seems incomplete or cut off → ask "Would you like to add anything else?" before judging. Do NOT evaluate a half-finished answer.
- Candidates use fillers (um, like, you know) and think out loud — this is normal, do not penalise it.
- ONE clarification per question maximum. If still unclear after that → move on. Never loop.
- If they say "I don't know", go vague, or stay silent:
  * Acknowledge briefly with varied phrasing: "That's completely fine." / "No worries at all." / "Thank you for your honesty."
  * Offer ONE gentle chance: "Anything you remember about it?"
  * If still unsure → move to next topic without giving the answer.

OBJECTION HANDLING:
- "How do you know about me?" → "Your resume was shared with us as part of the application. Now, let's continue —" and redirect.
- "Why so many questions?" → "We want to understand both your depth and practical thinking." Redirect.
- "When will I hear back?" → "Our team will review and follow up with you shortly." Redirect.

DECISION RULES:
1. INCOMPLETE: Answer trails off or seems partial → "Would you like to add anything else?" (action: simplify, depth_change: 0)
2. BLUFF: Answer is clearly factually wrong — not just vague, incomplete, or filler-heavy. Call it out once, gently.
3. DEPTH UP: Strong, correct, detailed answer → harder follow-up on same topic. depth_change: +1.
4. DEPTH DOWN: Weak but genuine attempt → simpler angle. depth_change: -1.
5. MOVE ON: Depth 3 exhausted OR 2 consecutive wrong/vague answers → score topic and move to next. depth_change: 0.
6. WRAP UP: No topics remain → warm professional close: "This has been really insightful. Our team will review your responses and follow up with you shortly. Do you have any final questions?" Then set interview_complete: true.

Return ONLY valid JSON:
{{
    "response_text": "Your exact words — short, warm, one question at a time",
    "action": "go_deeper" | "simplify" | "next_topic" | "bluff_called" | "wrap_up",
    "topic_score": 1-10,
    "depth_change": -1 | 0 | 1,
    "interview_complete": false,
    "reasoning": "brief internal note"
}}"""

        response = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                *self.conversation_history[-12:]
            ],
            response_format={"type": "json_object"},
            max_tokens=400,
        )

        result = json.loads(response.choices[0].message.content)

        self.current_depth = max(1, min(3, self.current_depth + result.get("depth_change", 0)))
        action = result.get("action")

        if action in ["next_topic", "bluff_called", "wrap_up"]:
            raw_score = result.get("topic_score", 5)
            self.topic_scores[self.current_topic] = int(raw_score) if isinstance(raw_score, (int, float)) else 5
            self.topics_covered.append(self.current_topic)

            if self.topics_remaining:
                self.current_topic = self.topics_remaining.pop(0)
                self.current_depth = 1
            else:
                self.is_interview_done = True
                result["interview_complete"] = True

        if result.get("interview_complete"):
            self.is_interview_done = True

        if result.get("response_text"):
            self.conversation_history.append({"role": "assistant", "content": result["response_text"]})

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
            "position": self.position,
            "topics_covered": self.topics_covered,
            "topic_scores": self.topic_scores,
            "overall_score": score,
            "max_depth_reached": self.current_depth,
            "recommendation": "Hire" if score >= 6.5 else "Hold" if score >= 5.0 else "Reject",
            "transcript": self.conversation_history,
            "is_flagged": self.is_flagged,
        }
