import asyncio
import json
import uuid
import os
import httpx

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from interview_engine import InterviewEngine
from resume_parser import ResumeParser
import deepgram_interview
from face_checker import get_embedding, compare_embeddings, preload as preload_face


class ImagePayload(BaseModel):
    image: str


app = FastAPI(title="AI Recruiter v1")


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(preload_face())

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

sessions: dict[str, InterviewEngine] = {}
resume_parser = ResumeParser()

RETELL_API_KEY = os.getenv("RETELL_API_KEY")
RETELL_AGENT_ID = os.getenv("RETELL_AGENT_ID")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "1.0",
        "active_sessions": len(sessions),
        "deepgram_key_set": bool(os.getenv("DEEPGRAM_API_KEY")),
        "retell_key_set": bool(RETELL_API_KEY),
        "openai_key_set": bool(os.getenv("OPENAI_API_KEY")),
    }


@app.post("/api/upload-resume")
async def upload_resume(
    file: UploadFile = File(...),
    position: str = Form(...),
    email: str = Form(...),
    name: str = Form(...)
):
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    resume_data = await resume_parser.parse(content, file.filename)
    photo_b64 = resume_parser.extract_photo(content, file.filename)

    session_id = str(uuid.uuid4())
    engine = InterviewEngine(
        resume_data=resume_data,
        position=position,
        candidate_name=name,
        candidate_email=email
    )
    sessions[session_id] = engine

    return {
        "session_id": session_id,
        "candidate": name,
        "position": position,
        "resume_summary": resume_data.get("summary", ""),
        "detected_skills": resume_data.get("skills", []),
        "domain": resume_data.get("domain", ""),
        "photo_base64": photo_b64,
    }


@app.post("/api/start-interview/{session_id}")
async def start_interview(session_id: str):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    async with httpx.AsyncClient() as client:
        res = await client.post(
            "https://api.retellai.com/v2/create-web-call",
            headers={
                "Authorization": f"Bearer {RETELL_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "agent_id": RETELL_AGENT_ID,
                "metadata": {"session_id": session_id}
            }
        )
        if res.status_code != 201:
            raise HTTPException(status_code=500, detail=f"Retell error: {res.text}")
        data = res.json()

    return {
        "access_token": data["access_token"],
        "call_id": data["call_id"]
    }


@app.post("/api/shortlist")
async def shortlist_candidates(
    files: list[UploadFile] = File(...),
    position: str = Form(...),
    requirements: str = Form(...)
):
    results = []
    for file in files:
        content = await file.read()
        if not content:
            continue
        resume_data = await resume_parser.parse(content, file.filename)
        score = await resume_parser.evaluate_fit(resume_data, position, requirements)
        results.append({
            "filename": file.filename,
            "candidate": resume_data.get("name", "Unknown"),
            "email": resume_data.get("email", ""),
            "domain": resume_data.get("domain", ""),
            "score": score["score"],
            "recommendation": score["recommendation"],
            "strengths": score["strengths"],
            "gaps": score["gaps"],
            "domain_match": score.get("domain_match", False),
            "reasoning": score.get("reasoning", "")
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    shortlisted = [r for r in results if r["recommendation"] == "Shortlist"]
    maybes = [r for r in results if r["recommendation"] == "Maybe"]
    rejected = [r for r in results if r["recommendation"] == "Reject"]

    return {
        "total": len(results),
        "shortlisted_count": len(shortlisted),
        "shortlist": results,
        "breakdown": {
            "shortlist": len(shortlisted),
            "maybe": len(maybes),
            "reject": len(rejected)
        }
    }


@app.websocket("/ws/retell-llm/{call_id}")
async def retell_llm_websocket(websocket: WebSocket, call_id: str):
    """Retell Custom LLM endpoint — Retell connects here as the interview brain."""
    await websocket.accept()

    engine: InterviewEngine | None = None
    opening_sent = False
    processed_user_count = 0
    last_response_text = ""

    try:
        # Step 1: send config — request call_details so we get session_id
        await websocket.send_json({
            "response_type": "config",
            "config": {
                "auto_reconnect": True,
                "call_details": True
            }
        })

        while True:
            data = await websocket.receive_json()
            interaction_type = data.get("interaction_type")

            if interaction_type == "call_details":
                metadata = data.get("call", {}).get("metadata", {})
                session_id = metadata.get("session_id")
                if session_id and session_id in sessions:
                    engine = sessions[session_id]
                    # Send opening proactively as the begin message
                    opening = await engine.get_opening()
                    opening_sent = True
                    last_response_text = opening
                    await websocket.send_json({
                        "response_type": "response",
                        "response_id": 1,
                        "content": opening,
                        "content_complete": True
                    })

            elif interaction_type == "ping_pong":
                await websocket.send_json({
                    "response_type": "ping_pong",
                    "timestamp": data.get("timestamp")
                })

            elif interaction_type in ("response_required", "reminder_required"):
                response_id = data.get("response_id")

                if not engine:
                    await websocket.send_json({
                        "response_type": "response",
                        "response_id": response_id,
                        "content": "Sorry, there was a session error. Please restart.",
                        "content_complete": True
                    })
                    continue

                transcript = data.get("transcript", [])
                user_messages = [t for t in transcript if t.get("role") == "user"]

                if not opening_sent:
                    # Fallback if call_details never arrived
                    opening = await engine.get_opening()
                    opening_sent = True
                    last_response_text = opening
                    await websocket.send_json({
                        "response_type": "response",
                        "response_id": response_id,
                        "content": opening,
                        "content_complete": True
                    })

                elif len(user_messages) > processed_user_count:
                    latest_answer = user_messages[-1].get("content", "")
                    processed_user_count = len(user_messages)

                    result = await engine.process_answer(latest_answer)
                    response_text = result.get("response_text", "")
                    last_response_text = response_text
                    interview_done = result.get("interview_complete", False)

                    await websocket.send_json({
                        "response_type": "response",
                        "response_id": response_id,
                        "content": response_text,
                        "content_complete": True,
                        "end_call": interview_done
                    })

                    if interview_done:
                        engine.is_interview_done = True
                        break

                else:
                    # Reminder — resend last response
                    await websocket.send_json({
                        "response_type": "response",
                        "response_id": response_id,
                        "content": last_response_text,
                        "content_complete": True
                    })

    except WebSocketDisconnect:
        pass
    except Exception:
        pass


@app.websocket("/ws/deepgram/{session_id}")
async def deepgram_interview_ws(websocket: WebSocket, session_id: str):
    """Deepgram STT + OpenAI TTS interview pipeline (cheaper alternative to Retell)."""
    await websocket.accept()
    if session_id not in sessions:
        await websocket.send_json({"type": "error", "message": "Session not found."})
        await websocket.close()
        return
    try:
        await deepgram_interview.run_session(websocket, sessions[session_id])
    except WebSocketDisconnect:
        pass
    except Exception:
        pass


@app.post("/api/store-face/{session_id}")
async def store_face(session_id: str, payload: ImagePayload):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    embedding, error = await get_embedding(payload.image)
    if error or embedding is None:
        raise HTTPException(status_code=400, detail=error or "no_face")
    sessions[session_id].face_embedding = embedding
    return {"status": "stored"}


@app.post("/api/check-face/{session_id}")
async def check_face(session_id: str, payload: ImagePayload):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    engine = sessions[session_id]
    if engine.face_embedding is None:
        return {"matched": True, "similarity": 1.0, "no_reference": True}
    embedding, error = await get_embedding(payload.image)
    if error == "no_face":
        return {"matched": None, "no_face": True}
    if error or embedding is None:
        return {"matched": True, "no_face": True}
    return compare_embeddings(engine.face_embedding, embedding)


@app.post("/api/flag/{session_id}")
async def flag_session(session_id: str):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    sessions[session_id].is_flagged = True
    return {"status": "flagged"}


@app.get("/api/results/{session_id}")
async def get_results(session_id: str):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found or already cleaned up")
    engine = sessions[session_id]
    return engine.get_final_results()
