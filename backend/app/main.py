import os
import json
import uuid
import asyncio
import logging
from threading import Lock
from typing import List
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load .env variables
load_dotenv()

# Internal imports
from agents.document_validator import DocumentValidator
from agents.document_parser import DocumentParser
from agents.policy_checker import PolicyChecker
from agents.fraud_detector import FraudDetector
from agents.decision_engine import DecisionEngine
from agents.trace_builder import TraceBuilder
from services.ocr import extract_text_from_image
from app.config import POLICY
from database.db import init_db, get_history, save_claim

# Setup beautiful logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("PlumPipeline")

app = FastAPI(title="Plum Claims Engine")

# Enable CORS for the dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Agents
validator = DocumentValidator(POLICY)
parser = DocumentParser()
policy_checker = PolicyChecker(POLICY)
fraud_detector = FraudDetector(POLICY)
decision_engine = DecisionEngine(POLICY)
trace_builder = TraceBuilder()

# Ensure needed directories exist
UPLOAD_DIR = "uploads"
TRACE_DIR = "traces"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(TRACE_DIR, exist_ok=True)

# Initialize DB
init_db()

JOBS = {}
JOBS_LOCK = Lock()


def _get_job(job_id: str):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        return dict(job) if job else None


def _list_inflight_history(member_id: str, exclude_job_id: str = ""):
    """
    Build transient claim history from jobs still running for the same member.
    This helps fraud checks remain deterministic even before DB persistence.
    """
    inflight_history = []
    with JOBS_LOCK:
        for jid, job in JOBS.items():
            if jid == exclude_job_id:
                continue
            if job.get("status") != "RUNNING":
                continue
            if job.get("member_id") != member_id:
                continue
            inflight_history.append({
                "claim_id": f"INFLIGHT-{jid[:8]}",
                "member_id": member_id,
                "date": job.get("treatment_date"),
                "amount": float(job.get("claimed_amount", 0.0)),
                "verdict": "PENDING",
                "trace": None
            })
    return inflight_history


def _update_job(job_id: str, **fields):
    with JOBS_LOCK:
        if job_id in JOBS:
            JOBS[job_id].update(fields)


def _set_running_step(job_id: str, step_idx: int):
    _update_job(job_id, status="RUNNING", current_step=step_idx)


def _process_claim_job(
    job_id: str,
    member_id: str,
    claim_category: str,
    claimed_amount: float,
    treatment_date: str,
    file_paths: List[str]
):
    print("\n" + "=" * 80)
    logger.info(f"🚀 INCOMING CLAIM: Member {member_id} | Category: {claim_category} | Job: {job_id}")
    print("=" * 80)

    try:
        document_texts = []

        # --- PHASE 1: OCR ---
        for file_path in file_paths:
            logger.info(f"📄 OCR-ing File: {os.path.basename(file_path)}")
            text = extract_text_from_image(file_path)
            document_texts.append(text)

        # --- PHASE 2: VALIDATION (Agent 1) ---
        _set_running_step(job_id, 0)
        logger.info("⚖️  [Agent 1] Validating documents...")
        valid_res = validator.validate(claim_category, document_texts)

        if valid_res["status"] == "FAILED":
            logger.error(f"❌ Validation Failed: {valid_res['message']}")
            _update_job(
                job_id,
                status="FAILED",
                current_step=0,
                result={
                    "status": "VALIDATION_FAILED",
                    "failed_step": 0,
                    "error_message": valid_res["message"]
                }
            )
            return

        # --- PHASE 3: PARSING (Agent 2) ---
        _set_running_step(job_id, 1)
        logger.info("🔍 [Agent 2] Parsing structured data...")
        classified_docs = valid_res.get("details", {}).get("classified_docs", [])
        parsed_docs = parser.parse(document_texts, classified_docs)
        logger.info("✅ Extraction Successful.")

        # --- PHASE 4: POLICY CHECKING (Agent 3) ---
        _set_running_step(job_id, 2)
        logger.info("📄 [Agent 3] Applying policy rules...")
        claim_metadata = {
            "member_id": member_id,
            "claim_category": claim_category,
            "claimed_amount": claimed_amount,
            "treatment_date": treatment_date
        }
        policy_res = policy_checker.check(claim_metadata, parsed_docs)

        if policy_res.get("status") == "FAILED":
            logger.error(f"❌ Policy Check Failed: {policy_res['message']}")
            _update_job(
                job_id,
                status="FAILED",
                current_step=2,
                result={
                    "status": "VALIDATION_FAILED",
                    "failed_step": 2,
                    "error_message": policy_res["message"]
                }
            )
            return

        logger.info("✅ Policy Checks Completed.")

        # --- PHASE 5: FRAUD DETECTION (Agent 4) ---
        _set_running_step(job_id, 3)
        logger.info("🕵️  [Agent 4] Running fraud detection...")
        db_history = get_history(member_id)
        inflight_history = _list_inflight_history(member_id, exclude_job_id=job_id)
        history = db_history + inflight_history
        fraud_res = fraud_detector.detect(claim_metadata, parsed_docs, history)
        logger.info(f"✅ Fraud Check: Score {fraud_res['fraud_score']}")

        # --- PHASE 6: FINAL DECISION (Agent 5) ---
        _set_running_step(job_id, 4)
        logger.info("🏁 [Agent 5] Making final decision...")
        decision_res = decision_engine.decide(policy_res, fraud_res)
        logger.info(f"✅ Verdict: {decision_res['verdict']} | Approved: ₹{decision_res['approved_amount']}")

        # --- PHASE 7: TRACE BUILDING (Agent 6) ---
        logger.info("📄 [Agent 6] Assembling final trace...")
        claim_id = f"CLM-{uuid.uuid4().hex[:8].upper()}"
        final_trace = trace_builder.build_trace(
            claim_id, member_id, claim_category,
            valid_res, parsed_docs, policy_res, fraud_res, decision_res
        )

        save_claim({
            "claim_id": claim_id, "member_id": member_id,
            "date": treatment_date, "amount": claimed_amount, "verdict": decision_res["verdict"]
        }, final_trace)

        logger.info(f"✅ Pipeline Complete for {claim_id}.")
        print("=" * 80 + "\n")

        _update_job(
            job_id,
            status="SUCCESS",
            current_step=None,
            result={
                "status": "SUCCESS",
                "claim_id": claim_id,
                "verdict": decision_res["verdict"],
                "approved_amount": decision_res["approved_amount"],
                "reason": decision_res["reason"],
                "trace": final_trace
            }
        )
    except Exception as exc:
        logger.exception(f"❌ Pipeline crashed for job {job_id}: {exc}")
        failed_step = (_get_job(job_id) or {}).get("current_step", 0)
        _update_job(
            job_id,
            status="FAILED",
            result={
                "status": "VALIDATION_FAILED",
                "failed_step": failed_step,
                "error_message": "Pipeline failed unexpectedly. Please retry."
            }
        )


@app.get("/history")
async def get_all_history():
    return get_history("")

@app.post("/submit-claim")
async def submit_claim(
    member_id: str = Form(...),
    claim_category: str = Form(...),
    claimed_amount: float = Form(...),
    treatment_date: str = Form(...),
    files: List[UploadFile] = File(...)
):
    file_paths = []
    for file in files:
        file_id = str(uuid.uuid4())[:8]
        file_path = os.path.join(UPLOAD_DIR, f"{file_id}_{file.filename}")
        with open(file_path, "wb") as f:
            f.write(await file.read())
        file_paths.append(file_path)

    job_id = str(uuid.uuid4())
    with JOBS_LOCK:
        JOBS[job_id] = {
            "status": "RUNNING",
            "current_step": 0,
            "result": None,
            "member_id": member_id,
            "treatment_date": treatment_date,
            "claimed_amount": claimed_amount
        }

    asyncio.create_task(
        asyncio.to_thread(
            _process_claim_job,
            job_id=job_id,
            member_id=member_id,
            claim_category=claim_category,
            claimed_amount=claimed_amount,
            treatment_date=treatment_date,
            file_paths=file_paths
        )
    )

    return {"status": "ACCEPTED", "job_id": job_id}


@app.get("/claim-status/{job_id}")
async def claim_status(job_id: str):
    job = _get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
