import os
import json
import uuid
import logging
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
    print("\n" + "="*80)
    logger.info(f"🚀 INCOMING CLAIM: Member {member_id} | Category: {claim_category}")
    print("="*80)

    document_texts = []
    
    # --- PHASE 1: OCR ---
    for file in files:
        file_id = str(uuid.uuid4())[:8]
        file_path = os.path.join(UPLOAD_DIR, f"{file_id}_{file.filename}")
        with open(file_path, "wb") as f:
            f.write(await file.read())
        logger.info(f"📄 OCR-ing File: {file.filename}")
        text = extract_text_from_image(file_path)
        document_texts.append(text)

    # --- PHASE 2: VALIDATION (Agent 1) ---
    logger.info("⚖️  [Agent 1] Validating documents...")
    valid_res = validator.validate(claim_category, document_texts)

    if valid_res["status"] == "FAILED":
        logger.error(f"❌ Validation Failed: {valid_res['message']}")
        return {
            "status": "VALIDATION_FAILED",
            "failed_step": 0,
            "error_message": valid_res["message"]
        }

    # --- PHASE 3: PARSING (Agent 2) ---
    logger.info("🔍 [Agent 2] Parsing structured data...")
    classified_docs = valid_res.get("details", {}).get("classified_docs", [])
    parsed_docs = parser.parse(document_texts, classified_docs)
    logger.info("✅ Extraction Successful.")
    
    # --- PHASE 4: POLICY CHECKING (Agent 3) ---
    logger.info("📄 [Agent 3] Applying policy rules...")
    claim_metadata = {
        "member_id": member_id, "claim_category": claim_category,
        "claimed_amount": claimed_amount, "treatment_date": treatment_date
    }
    policy_res = policy_checker.check(claim_metadata, parsed_docs)

    if policy_res.get("status") == "FAILED":
        logger.error(f"❌ Policy Check Failed: {policy_res['message']}")
        return {
            "status": "VALIDATION_FAILED",
            "failed_step": 2,
            "error_message": policy_res["message"]
        }

    logger.info("✅ Policy Checks Completed.")
    
    # --- PHASE 5: FRAUD DETECTION (Agent 4) ---
    logger.info("🕵️  [Agent 4] Running fraud detection...")
    history = get_history(member_id)
    fraud_res = fraud_detector.detect(claim_metadata, parsed_docs, history)
    logger.info(f"✅ Fraud Check: Score {fraud_res['fraud_score']}")
    
    # --- PHASE 6: FINAL DECISION (Agent 5) ---
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
    print("="*80 + "\n")

    return {
        "status": "SUCCESS",
        "claim_id": claim_id,
        "verdict": decision_res["verdict"],
        "approved_amount": decision_res["approved_amount"],
        "reason": decision_res["reason"],
        "trace": final_trace
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)