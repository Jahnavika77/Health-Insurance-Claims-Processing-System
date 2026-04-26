import logging
from typing import List, Dict, Any

logger = logging.getLogger("DecisionEngine")

class DecisionEngine:
    def __init__(self, policy: Dict[str, Any]):
        self.policy = policy

    def decide(self, policy_res: Dict[str, Any], fraud_res: Dict[str, Any]) -> Dict[str, Any]:
        """
        Agent 5: Decision Engine.
        Synthesizes results from Policy Checker and Fraud Detector to reach a final verdict.
        """
        policy_checks = policy_res.get("policy_checks", [])
        fraud_score = fraud_res.get("fraud_score", 0.0)
        
        verdict = "APPROVED"
        reason = "All checks passed."
        final_amount = 0.0
        rejection_reasons = []
        
        # 1. Check for Fraud/Manual Review
        if fraud_score >= 0.8 or fraud_res.get("manual_review_recommended"):
            return {
                "verdict": "MANUAL_REVIEW",
                "reason": f"High fraud score ({fraud_score}) or manual review flag triggered.",
                "approved_amount": 0.0,
                "confidence_score": 0.5
            }

        # 2. Analyze Policy Checks
        financial_calc = None
        for check in policy_checks:
            if check["status"] == "FAIL":
                verdict = "REJECTED"
                rejection_reasons.append(f"{check['rule']}: {check.get('reason', 'Check failed')}")
            
            if check["rule"] == "FINANCIAL_CALCULATION":
                financial_calc = check.get("calculations", {})

        # 3. Final Decision Logic
        if verdict == "REJECTED":
            return {
                "verdict": "REJECTED",
                "reason": " | ".join(rejection_reasons),
                "approved_amount": 0.0,
                "confidence_score": 0.9
            }

        if financial_calc:
            final_amount = financial_calc.get("final_approved_amount", 0.0)
            claimed = financial_calc.get("claimed_amount", 0.0)
            exceeds_sublimit = financial_calc.get("exceeds_sublimit", False)
            
            if exceeds_sublimit:
                verdict = "PARTIAL"
                reason = f"Partial approval: claimed amount exceeds the category sub-limit of ₹{financial_calc.get('sub_limit', 0)}. Approved ₹{final_amount}."
            elif final_amount < claimed:
                reason = "Approved after standard policy deductions (copay/network discount)."
            
        # 4. Confidence adjustment based on fraud score
        confidence = 1.0 - (fraud_score * 0.5) # Reducing confidence slightly if fraud score is > 0

        return {
            "verdict": verdict,
            "reason": reason,
            "approved_amount": final_amount,
            "confidence_score": round(confidence, 2)
        }
