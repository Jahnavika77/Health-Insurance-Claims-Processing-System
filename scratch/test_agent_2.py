import os
import sys
import json
import logging
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.document_validator import DocumentValidator
from agents.document_parser import DocumentParser
from services.ocr import extract_text_from_image
from app.config import POLICY

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("TestAgent2")

def test_agent_2_pipeline():
    load_dotenv()
    
    # Initialize agents
    validator = DocumentValidator(POLICY)
    parser = DocumentParser()
    
    # Define test files
    files = [
        "mock_documents/generated/prescription.jpg",
        "mock_documents/generated/hospital_bill.pdf"
    ]
    
    # Phase 1: OCR
    print("\n--- Phase 1: OCR ---")
    document_texts = []
    for f in files:
        if not os.path.exists(f):
            logger.error(f"File not found: {f}")
            continue
        logger.info(f"Processing OCR for {f}...")
        text = extract_text_from_image(f)
        document_texts.append(text)
        print(f"DEBUG: Extracted text length: {len(text)}")

    # Phase 2: Classification (from Agent 1)
    print("\n--- Phase 2: Classification (Agent 1) ---")
    # We use a dummy category to get classification results
    valid_res = validator.validate("CONSULTATION", document_texts)
    classified_docs = valid_res.get("details", {}).get("classified_docs", [])
    
    # Phase 3: Parsing (Agent 2)
    print("\n--- Phase 3: Parsing (Agent 2) ---")
    parsed_docs = parser.parse(document_texts, classified_docs)
    
    # Print Results
    print("\n" + "="*50)
    print("AGENT 2 OUTPUT (STRUCTURED DATA)")
    print("="*50)
    for i, doc in enumerate(parsed_docs):
        print(f"\nDocument {i+1} ({doc['doc_type']}):")
        print(json.dumps(doc['extracted_data'], indent=2))
    print("="*50 + "\n")

if __name__ == "__main__":
    test_agent_2_pipeline()
