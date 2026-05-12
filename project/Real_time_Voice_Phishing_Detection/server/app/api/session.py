import uuid
import logging
from fastapi import APIRouter, File, UploadFile, HTTPException
from app.models.stt import STTModel
from app.models.deepfake import DeepfakeModel
from app.services.audio_processor import convert_to_pcm

logger = logging.getLogger("vaia")
router = APIRouter(prefix="/session")

_deepfake = DeepfakeModel()

# 세션 저장소: {session_id: {"stt": STTModel, "chunks_pcm": [], "full_text": ""}}
_sessions: dict = {}


@router.post("/start")
async def start_session():
    session_id = str(uuid.uuid4())
    _sessions[session_id] = {
        "stt": STTModel(),
        "chunks_pcm": [],
        "full_text": "",
    }
    logger.info(f"[세션 시작] {session_id}")
    return {"session_id": session_id}


@router.post("/{session_id}/chunk")
async def analyze_chunk(session_id: str, file: UploadFile = File(...)):
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="세션 없음")

    raw = await file.read()
    if not raw:
        return {"text": "", "session_id": session_id}

    try:
        pcm = convert_to_pcm(raw)
    except Exception as e:
        logger.error(f"[청크 변환 실패] {e}")
        raise HTTPException(status_code=400, detail=str(e))

    session = _sessions[session_id]
    text = session["stt"].transcribe(pcm)
    session["chunks_pcm"].append(pcm)
    if text:
        session["full_text"] += " " + text

    logger.info(f"[청크 STT] {session_id[:8]} → {text[:60]}")
    return {"text": text.strip(), "session_id": session_id}


@router.post("/{session_id}/end")
async def end_session(session_id: str):
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="세션 없음")

    session = _sessions.pop(session_id)
    full_text = session["full_text"].strip()

    all_pcm = b"".join(session["chunks_pcm"])
    deepfake_result = _deepfake.predict(all_pcm) if all_pcm else {"is_fake": False, "confidence": 0.0}

    # NLU: placeholder (추후 연결)
    risk_score = 0
    warning_level = 3 if deepfake_result["is_fake"] else 0

    logger.info(f"[세션 종료] {session_id[:8]} | text={full_text[:60]} | fake={deepfake_result['is_fake']}")

    return {
        "text": full_text,
        "risk_score": risk_score,
        "warning_level": warning_level,
        "is_fake_voice": deepfake_result["is_fake"],
        "deepfake_confidence": deepfake_result["confidence"],
        "explanation": "",
        "detected_labels": [],
    }
