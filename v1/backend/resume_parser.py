from openai import AsyncOpenAI
import pdfplumber
import docx
import io
import json
import os
import base64

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


class ResumeParser:
    async def parse(self, file_bytes: bytes, filename: str) -> dict:
        text = self._extract_text(file_bytes, filename)
        if not text.strip():
            return {"error": "Could not extract text from resume"}

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": f"""Extract structured information from this resume. Be precise — only extract what is actually written, do not invent.

RESUME:
{text}

Return ONLY valid JSON:
{{
    "name": "full name or null",
    "email": "email or null",
    "phone": "phone or null",
    "skills": ["list of technical skills mentioned"],
    "experience_years": 0,
    "area_of_interest": ["stated areas of interest or inferred from projects"],
    "domain": "primary domain (e.g. Web Dev, ML, Data Science, DevOps, etc.)",
    "strongest_skills": ["top 3 skills with most evidence in resume"],
    "weak_claims": ["skills mentioned once with no supporting project or detail — possible bluff zones"],
    "education": "degree + institution + year",
    "projects": ["one-line summary of each notable project"],
    "certifications": ["any certifications listed"],
    "summary": "2-sentence neutral summary of this candidate"
}}"""
            }],
            response_format={"type": "json_object"}
        )

        return json.loads(response.choices[0].message.content)

    async def evaluate_fit(self, resume_data: dict, position: str, requirements: str) -> dict:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": f"""Evaluate this candidate for the role: {position}

Job Requirements:
{requirements}

Candidate Resume Data:
{json.dumps(resume_data, indent=2)}

Be strict. A candidate should only be shortlisted if they genuinely meet the core requirements.

Return ONLY valid JSON:
{{
    "score": 0-100,
    "recommendation": "Shortlist" | "Reject" | "Maybe",
    "strengths": ["specific matching strengths"],
    "gaps": ["specific missing requirements"],
    "domain_match": true | false,
    "reasoning": "2-3 sentence explanation of your decision"
}}"""
            }],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)

    def extract_photo(self, file_bytes: bytes, filename: str) -> str | None:
        """Try to pull a face photo from the resume PDF. Returns data-URL or None."""
        if not filename.lower().endswith('.pdf'):
            return None
        try:
            import fitz
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            for page_num in range(min(2, len(doc))):
                for img in doc[page_num].get_images(full=True):
                    xref = img[0]
                    base_img = doc.extract_image(xref)
                    w, h = base_img["width"], base_img["height"]
                    # Skip tiny icons/logos; a passport photo is at least 80×80
                    if w < 80 or h < 80:
                        continue
                    ext = base_img.get("ext", "png")
                    b64 = base64.b64encode(base_img["image"]).decode()
                    return f"data:image/{ext};base64,{b64}"
        except Exception:
            pass
        return None

    def _extract_text(self, file_bytes: bytes, filename: str) -> str:
        name = filename.lower()
        if name.endswith(".pdf"):
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                return "\n".join(page.extract_text() or "" for page in pdf.pages)
        elif name.endswith((".docx", ".doc")):
            doc = docx.Document(io.BytesIO(file_bytes))
            return "\n".join(p.text for p in doc.paragraphs)
        return ""
