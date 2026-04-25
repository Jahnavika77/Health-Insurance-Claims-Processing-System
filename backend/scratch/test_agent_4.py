import os
import sys
import json
import logging
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.fraud_detector import FraudDetector
from app.config import POLICY

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("TestAgent4")

def test_fraud_detector():
    detector = FraudDetector(POLICY)
    
    print("\n--- Test Case 1: Duplicate Claim ---")
    claim_1 = {"treatment_date": "2024-11-01", "claimed_amount": 1500}
    history_1 = [{"date": "2024-11-01", "amount": 1500, "claim_id": "CLM001"}]
    docs_1 = [{"doc_type": "PRESCRIPTION", "extracted_data": {"patient_name": "Rajesh Kumar"}}]
    res_1 = detector.detect(claim_1, docs_1, history_1)
    print(json.dumps(res_1, indent=2))

    print("\n--- Test Case 2: Identity Mismatch ---")
    # One doc says Rajesh Kumar, another says Arjun Mehta
    claim_2 = {"treatment_date": "2024-11-01", "claimed_amount": 1000}
    docs_2 = [
        {"doc_type": "PRESCRIPTION", "extracted_data": {"patient_name": "Rajesh Kumar"}},
        {"doc_type": "HOSPITAL_BILL", "extracted_data": {"patient_name": "Arjun Mehta"}}
    ]
    res_2 = detector.detect(claim_2, docs_2, [])
    print(json.dumps(res_2, indent=2))

    print("\n--- Test Case 3: High Value & Frequency ---")
    # Amount > 25000 and 3rd claim today (limit is 2)
    claim_3 = {"treatment_date": "2024-10-30", "claimed_amount": 30000}
    history_3 = [
        {"date": "2024-10-30", "amount": 1200},
        {"date": "2024-10-30", "amount": 1800}
    ]
    docs_3 = [{"doc_type": "PRESCRIPTION", "extracted_data": {"patient_name": "Ravi Menon"}}]
    res_3 = detector.detect(claim_3, docs_3, history_3)
    print(json.dumps(res_3, indent=2))

if __name__ == "__main__":
    test_fraud_detector()
