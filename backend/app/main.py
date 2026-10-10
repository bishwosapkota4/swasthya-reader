import logging

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import db, flagging, gemma, ingest, tts
from .config import CHAT_HISTORY_LIMIT, MAX_UPLOAD_MB, MEDIA_DIR
from .prompts import DISCLAIMER_EN, DISCLAIMER_NE, EMERGENCY_CHAT_RESPONSE_NE

logger = logging.getLogger(__name__)
EMERGENCY_TERMS = (
    "chest pain",
    "chest hurts",
    "trouble breathing",
    "difficulty breathing",
    "shortness of breath",
    "fainting",
    "fainted",
    "passed out",
    "severe bleeding",
    "heavy bleeding",
    "bleeding won't stop",
    "छाती दुख",
    "सास फेर्न गाह्रो",
    "श्वास फेर्न गाह्रो",
    "बेहोस",
    "बेहोशी",
    "धेरै रगत बग",
    "अत्यधिक रक्तस्राव",
    "रगत नरोकिन",
)

app = FastAPI(title="Swasthya Reader API", version="0.1.0")

# Open CORS for the hackathon (browser, Capacitor Android WebView at https://localhost). Tighten later.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")


class ChatRequest(BaseModel):
    question: str


def _contains_emergency_term(question: str) -> bool:
    normalized = question.casefold()
    return any(term in normalized for term in EMERGENCY_TERMS)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/reports")
def create_report(file: UploadFile = File(...)):
    """Upload a lab report (image or PDF) -> extracted values, Nepali summary + tips, audio."""
    tts.cleanup_old_audio()
    data = file.file.read()
    if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"File too large (max {MAX_UPLOAD_MB} MB)")

    try:
        images, pages_read, pages_total = ingest.to_images(data, file.content_type)
    except ValueError:
        logger.exception("report_ingest_failed")
        raise HTTPException(415, "Unsupported or unreadable report file")

    try:
        extracted = gemma.extract_report(images)
    except Exception:
        logger.exception("report_extraction_failed")
        raise HTTPException(502, "Could not read the report")

    patient = extracted.get("patient") or {}
    patient_sex = patient.get("sex") if isinstance(patient, dict) else None
    tests = flagging.flag_all(extracted["tests"], patient_sex)
    if not tests:
        raise HTTPException(422, "No test results found. Try a clearer photo or a different page.")

    try:
        summary = gemma.summarize_nepali(tests)
    except Exception:
        logger.exception("report_summary_failed")
        raise HTTPException(502, "Could not write the Nepali summary")

    # Code decides urgency as well; the model's flag can only raise it, never lower it.
    see_doctor = flagging.needs_doctor_soon(tests) or summary["see_doctor_soon"]

    audio_url = None
    try:
        audio_url = tts.synthesize(tts.tts_text(summary["summary_ne"], summary["tips_ne"]))
    except Exception:
        logger.exception("report_audio_failed")

    record = {
        "extracted_json": {"patient": extracted.get("patient"), "report_date": extracted.get("report_date"), "tests": tests},
        "nepali_summary": summary["summary_ne"],
        "tips_json": summary["tips_ne"],
        "see_doctor_soon": see_doctor,
        "audio_url": audio_url,
    }
    try:
        report_id = db.save_report(record)
    except Exception:
        logger.exception("report_persistence_failed")
        raise HTTPException(500, "Could not save the report")

    return {
        "report_id": report_id,
        "tests": tests,
        "summary_ne": summary["summary_ne"],
        "tips_ne": summary["tips_ne"],
        "see_doctor_soon": see_doctor,
        "audio_url": audio_url,
        "tests_skipped": extracted.get("tests_skipped", 0),
        "pages_read": pages_read,
        "pages_total": pages_total,
        "disclaimer_ne": DISCLAIMER_NE,
        "disclaimer_en": DISCLAIMER_EN,
    }


@app.post("/api/reports/{report_id}/chat")
def chat(report_id: str, body: ChatRequest):
    report = db.get_report(report_id)
    if not report:
        raise HTTPException(404, "Report not found")
    question = body.question.strip()
    if not question:
        raise HTTPException(400, "Empty question")
    if _contains_emergency_term(question):
        return {"answer": EMERGENCY_CHAT_RESPONSE_NE, "disclaimer_ne": DISCLAIMER_NE}

    history = db.get_messages(report_id, CHAT_HISTORY_LIMIT)
    tests = report["extracted_json"]["tests"]
    try:
        answer = gemma.chat_answer(tests, history, question)
    except Exception:
        logger.exception("chat_model_failed")
        raise HTTPException(502, "Chat failed")

    db.add_message(report_id, "user", question)
    db.add_message(report_id, "assistant", answer)
    return {"answer": answer, "disclaimer_ne": DISCLAIMER_NE}
