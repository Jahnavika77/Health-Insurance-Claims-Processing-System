import logging
from typing import List, Dict, Any
from datetime import datetime

logger = logging.getLogger("PolicyChecker")

class PolicyChecker:
    def __init__(self, policy: Dict[str, Any]):
        self.policy = policy

    def check(self, claim_data: Dict[str, Any], extracted_docs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Main entry point for Agent 3.
        Applies policy rules to the extracted data.
        """
        results = []
        member_id = claim_data.get("member_id")
        category = claim_data.get("claim_category", "").upper()
        treatment_date_str = claim_data.get("treatment_date")
        claimed_amount = claim_data.get("claimed_amount", 0.0)

        # 1. Basic Policy Info
        cat_policy = self.policy.get("opd_categories", {}).get(category.lower(), {})
        if not cat_policy:
            return {"status": "FAILED", "reason": f"Category {category} not covered by policy."}

        # 2. Waiting Period Check
        waiting_period_res = self._check_waiting_period(member_id, treatment_date_str, extracted_docs)
        results.append({"rule": "WAITING_PERIOD", **waiting_period_res})
        if waiting_period_res["status"] == "FAIL":
            return {"status": "FAILED", "message": f"WAITING_PERIOD: {waiting_period_res['reason']}", "policy_checks": results}

        # 3. Exclusion Check
        exclusion_res = self._check_exclusions(category, extracted_docs)
        results.append({"rule": "EXCLUSION_CHECK", **exclusion_res})
        if exclusion_res["status"] == "FAIL":
            return {"status": "FAILED", "message": f"EXCLUSION: {exclusion_res['reason']}", "policy_checks": results}

        # 4. Pre-Auth Check
        pre_auth_res = self._check_pre_auth(category, extracted_docs)
        results.append({"rule": "PRE_AUTH_CHECK", **pre_auth_res})
        if pre_auth_res["status"] == "FAIL":
            return {"status": "FAILED", "message": f"PRE_AUTH: {pre_auth_res['reason']}", "policy_checks": results}

        # 5. Financial Calculations (Sub-limits, Copay, Network Discount)
        financials = self._calculate_financials(category, claimed_amount, claim_data.get("hospital_name"))
        results.append({"rule": "FINANCIAL_CALCULATION", **financials})

        return {
            "status": "SUCCESS",
            "policy_checks": results
        }

    def _check_waiting_period(self, member_id: str, treatment_date_str: str, extracted_docs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Checks if the treatment falls within any waiting periods."""
        member = next((m for m in self.policy.get("members", []) if m["member_id"] == member_id), None)
        if not member:
            return {"status": "FAIL", "reason": f"Member ID [{member_id}] not found in our records. Please verify your ID or contact HR."}

        join_date = datetime.strptime(member["join_date"], "%Y-%m-%d")
        treatment_date = datetime.strptime(treatment_date_str, "%Y-%m-%d")
        days_since_joining = (treatment_date - join_date).days

        # Initial 30-day waiting period
        initial_wait = self.policy["waiting_periods"]["initial_waiting_period_days"]
        if days_since_joining < initial_wait:
            return {
                "status": "FAIL", 
                "reason": f"Initial waiting period of {initial_wait} days not met. Member joined {member['join_date']}.",
                "days_remaining": initial_wait - days_since_joining
            }

        # Specific conditions (Diagnosis based)
        extracted_diagnosis = ""
        for doc in extracted_docs:
            if doc["doc_type"] == "PRESCRIPTION":
                extracted_diagnosis = str(doc["extracted_data"].get("diagnosis", "")).lower()
                break

        if extracted_diagnosis:
            specific_waits = self.policy["waiting_periods"]["specific_conditions"]
            for condition, wait_days in specific_waits.items():
                if condition in extracted_diagnosis:
                    if days_since_joining < wait_days:
                        return {
                            "status": "FAIL",
                            "reason": f"Waiting period for {condition.title()} ({wait_days} days) not met.",
                            "days_remaining": wait_days - days_since_joining
                        }

        return {"status": "PASS", "message": "All waiting periods cleared."}

    def _check_exclusions(self, category: str, extracted_docs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Checks if the treatment or condition is explicitly excluded."""
        general_exclusions = self.policy.get("exclusions", {}).get("conditions", [])
        
        # Merge all diagnoses and line items for checking
        found_content = []
        for doc in extracted_docs:
            data = doc["extracted_data"]
            if "diagnosis" in data: found_content.append(str(data["diagnosis"]).lower())
            if "line_items" in data:
                for item in data["line_items"]:
                    found_content.append(str(item.get("description", "")).lower())

        for exc in general_exclusions:
            exc_lower = exc.lower()
            if any(exc_lower in content for content in found_content):
                return {"status": "FAIL", "reason": f"Exclude condition/treatment found: {exc}"}

        # Category specific exclusions (e.g. Dental)
        if category == "DENTAL":
            dental_exc = self.policy.get("exclusions", {}).get("dental_exclusions", [])
            for exc in dental_exc:
                if any(exc.lower() in content for content in found_content):
                    return {"status": "FAIL", "reason": f"Excluded dental procedure: {exc}"}

        return {"status": "PASS", "message": "No exclusions triggered."}

    def _check_pre_auth(self, category: str, extracted_docs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Checks if pre-authorization was required but missing."""
        cat_policy = self.policy.get("opd_categories", {}).get(category.lower(), {})
        if not cat_policy.get("requires_pre_auth") and "pre_auth_threshold" not in cat_policy:
            return {"status": "PASS", "message": "Pre-auth not required for this category."}

        # Check for high-value tests
        high_value_tests = cat_policy.get("high_value_tests_requiring_pre_auth", [])
        threshold = cat_policy.get("pre_auth_threshold", 999999)
        
        for doc in extracted_docs:
            if doc["doc_type"] == "HOSPITAL_BILL":
                items = doc["extracted_data"].get("line_items", [])
                for item in items:
                    desc = str(item.get("description", "")).lower()
                    amt = float(item.get("amount", 0))
                    
                    # Check if test name matches high value list
                    if any(test.lower() in desc for test in high_value_tests):
                        if amt > threshold:
                            return {
                                "status": "FAIL", 
                                "reason": f"Pre-authorization required for {desc} above ₹{threshold}.",
                                "required": True
                            }

        return {"status": "PASS", "message": "Pre-auth checks passed."}

    def _calculate_financials(self, category: str, claimed_amount: float, hospital_name: str = None) -> Dict[str, Any]:
        """Calculates approved amount after discounts, copay and sub-limits."""
        cat_policy = self.policy.get("opd_categories", {}).get(category.lower(), {})
        
        # 1. Network Discount
        discount_amt = 0.0
        final_amt = claimed_amount
        is_network = hospital_name in self.policy.get("network_hospitals", [])
        
        if is_network:
            discount_pct = cat_policy.get("network_discount_percent", 0)
            discount_amt = claimed_amount * (discount_pct / 100)
            final_amt = claimed_amount - discount_amt

        # 2. Copay
        copay_pct = cat_policy.get("copay_percent", 0)
        copay_amt = final_amt * (copay_pct / 100)
        final_amt -= copay_amt

        # 3. Sub-limit
        sub_limit = cat_policy.get("sub_limit", 999999)
        exceeds_sublimit = False
        if final_amt > sub_limit:
            final_amt = sub_limit
            exceeds_sublimit = True

        return {
            "status": "PASS",
            "calculations": {
                "claimed_amount": claimed_amount,
                "network_discount": discount_amt,
                "after_discount": claimed_amount - discount_amt,
                "copay_deducted": copay_amt,
                "after_copay": claimed_amount - discount_amt - copay_amt,
                "sub_limit": sub_limit,
                "exceeds_sublimit": exceeds_sublimit,
                "final_approved_amount": final_amt
            }
        }
