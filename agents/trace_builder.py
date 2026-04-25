import logging
from typing import List, Dict, Any
from datetime import datetime

logger = logging.getLogger("TraceBuilder")

class TraceBuilder:
    def __init__(self):
        pass

    def build_trace(self, 
                    claim_id: str,
                    member_id: str,
                    category: str,
                    val_res: Dict[str, Any],
                    parsing_res: List[Dict[str, Any]],
                    policy_res: Dict[str, Any],
                    fraud_res: Dict[str, Any],
                    decision_res: Dict[str, Any]) -> Dict[str, Any]:
        """
        Agent 6: Trace Builder.
        Assembles all intermediate agent outputs into a unified audit trail.
        """
        
        trace = {
            "claim_id": claim_id,
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "member_id": member_id,
                "category": category,
                "verdict": decision_res.get("verdict"),
                "approved_amount": decision_res.get("approved_amount"),
                "confidence": decision_res.get("confidence_score")
            },
            "stages": [
                {
                    "stage": 1,
                    "name": "Document Validation",
                    "status": val_res.get("status"),
                    "details": val_res.get("details", {}).get("classified_docs", [])
                },
                {
                    "stage": 2,
                    "name": "Document Parsing",
                    "status": "SUCCESS",
                    "details": parsing_res
                },
                {
                    "stage": 3,
                    "name": "Policy Checking",
                    "status": policy_res.get("status"),
                    "details": policy_res.get("policy_checks", [])
                },
                {
                    "stage": 4,
                    "name": "Fraud Detection",
                    "status": "SUCCESS",
                    "details": fraud_res
                },
                {
                    "stage": 5,
                    "name": "Decision Engine",
                    "status": "SUCCESS",
                    "details": decision_res
                }
            ]
        }
        
        return trace
