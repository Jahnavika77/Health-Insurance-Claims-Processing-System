import logging
from typing import List, Dict, Any
from datetime import datetime

logger = logging.getLogger("FraudDetector")

class FraudDetector:
    def __init__(self, policy: Dict[str, Any]):
        self.policy = policy
        self.thresholds = policy.get("fraud_thresholds", {})

    def detect(self, claim_data: Dict[str, Any], extracted_docs: List[Dict[str, Any]], history: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Agent 4: Fraud Detector.
        Analyzes the current claim against history and extracted data to find anomalies.
        """
        if history is None:
            history = []

        flags = []
        score = 0.0
        
        # 1. Frequency Check (Same Day)
        treatment_date = claim_data.get("treatment_date")
        same_day_claims = [c for c in history if c.get("date") == treatment_date]
        
        limit = self.thresholds.get("same_day_claims_limit", 2)
        if len(same_day_claims) >= limit:
            flags.append(f"HIGH_FREQUENCY: {len(same_day_claims)} claims already submitted for {treatment_date}.")
            score += 0.4

        # 2. Duplicate Detection
        current_amount = claim_data.get("claimed_amount", 0.0)
        for old_claim in history:
            if (old_claim.get("date") == treatment_date and 
                abs(old_claim.get("amount", 0.0) - current_amount) < 0.01):
                flags.append("POTENTIAL_DUPLICATE: Claim with identical amount found on the same date.")
                score += 0.6
                break

        # 3. High Value Check
        hv_threshold = self.thresholds.get("high_value_claim_threshold", 25000)
        if current_amount > hv_threshold:
            flags.append(f"HIGH_VALUE_THRESHOLD: Claim amount ₹{current_amount} exceeds auto-processing limit.")
            score += 0.3

        # 4. Identity Consistency Check (Cross-document)
        names = []
        for doc in extracted_docs:
            name = doc["extracted_data"].get("patient_name")
            if name:
                names.append(name.strip().upper())
        
        if len(set(names)) > 1:
            flags.append(f"IDENTITY_MISMATCH: Multiple patient names found across documents: {list(set(names))}")
            score += 0.7

        # Cap score at 1.0
        score = min(score, 1.0)

        return {
            "fraud_score": score,
            "flags": flags,
            "manual_review_recommended": score >= self.thresholds.get("fraud_score_manual_review_threshold", 0.8)
        }
