import os
import sys
import json
import logging
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.policy_checker import PolicyChecker
from app.config import POLICY

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("TestAgent3")

def test_policy_checker():
    checker = PolicyChecker(POLICY)
    
    print("\n--- Test Case 1: Vikram Joshi (Waiting Period) ---")
    # Vikram joined 2024-09-01. Claim on 2024-10-15 (44 days). 
    # Diabetes needs 90 days.
    claim_1 = {
        "member_id": "EMP005",
        "claim_category": "CONSULTATION",
        "claimed_amount": 3000,
        "treatment_date": "2024-10-15",
        "hospital_name": "Local Clinic"
    }
    docs_1 = [
        {
            "doc_type": "PRESCRIPTION",
            "extracted_data": {"diagnosis": "Type 2 Diabetes Mellitus"}
        }
    ]
    res_1 = checker.check(claim_1, docs_1)
    print(json.dumps(res_1, indent=2))

    print("\n--- Test Case 2: Rajesh Kumar (Clean Consultation, Network Discount, Copay) ---")
    # Rajesh joined 2024-04-01. Claim 2024-11-01.
    # Category: Consultation. Network: Apollo Hospitals (20% discount). Copay: 10%.
    # Amount: 1500 -> 1200 (discount) -> 1080 (copay)
    claim_2 = {
        "member_id": "EMP001",
        "claim_category": "CONSULTATION",
        "claimed_amount": 1500,
        "treatment_date": "2024-11-01",
        "hospital_name": "Apollo Hospitals"
    }
    docs_2 = [
        {
            "doc_type": "PRESCRIPTION",
            "extracted_data": {"diagnosis": "Viral Fever"}
        }
    ]
    res_2 = checker.check(claim_2, docs_2)
    print(json.dumps(res_2, indent=2))

if __name__ == "__main__":
    test_policy_checker()
