import os
import uuid
import logging
from typing import List
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from dotenv import load_dotenv

# Load .env variables
load_dotenv()

# Internal imports
from agents.document_validator import DocumentValidator
from agents.document_parser import DocumentParser
from services.ocr import extract_text_from_image
from app.config import POLICY

# Setup beautiful logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("PlumPipeline")

app = FastAPI(title="Plum Claims Engine")

# Initialize Agents
validator = DocumentValidator(POLICY)
parser = DocumentParser()

# Ensure uploads directory exists
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

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
        
        # Save file
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
            "error_message": valid_res["message"],
            "details": valid_res.get("details", {})
        }

    # --- PHASE 3: PARSING (Agent 2) ---
    logger.info("🔍 [Agent 2] Parsing structured data...")
    classified_docs = valid_res.get("details", {}).get("classified_docs", [])
    parsed_docs = parser.parse(document_texts, classified_docs)

    logger.info("✅ Extraction Successful.")
    print("="*80 + "\n")

    return {
        "status": "SUCCESS",
        "message": "Documents validated and parsed successfully.",
        "member_id": member_id,
        "category": claim_category,
        "validation_summary": valid_res.get("details", {}),
        "extracted_data": parsed_docs
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)