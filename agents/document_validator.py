import json
import logging
from typing import List, Dict, Any
from openai import OpenAI
from dotenv import load_dotenv
import os

# Load environment variables (OPENAI_API_KEY)
load_dotenv()

logger = logging.getLogger("DocumentValidator")

class DocumentValidator:
    def __init__(self, policy: Dict[str, Any]):
        self.policy = policy
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            logger.warning("OPENAI_API_KEY not found in environment. Document classification will fail.")
        self.client = OpenAI(api_key=self.api_key)

    def validate(self, claim_category: str, document_texts: List[str]) -> Dict[str, Any]:
        """
        Two-phase validation:
        Phase 1: Classify each document (returns doc_type + confidence)
        Phase 2: Check against policy rules (required vs optional)
        """
        claim_category = claim_category.upper()
        
        # --- PHASE 1: Classify each document ---
        classified_results = []
        for text in document_texts:
            result = self._classify_document(text)
            classified_results.append(result)

        logger.info(f"Phase 1 Results: {classified_results}")

        # --- PHASE 2: Check against policy rules ---
        doc_reqs = self.policy.get("document_requirements", {}).get(claim_category, {})
        if not doc_reqs:
            return {
                "status": "FAILED",
                "message": f"Invalid claim category: {claim_category}"
            }

        required_types = doc_reqs.get("required", [])
        optional_types = doc_reqs.get("optional", [])
        
        uploaded_types = [r["doc_type"] for r in classified_results]
        uploaded_set = set(uploaded_types)

        missing_required = [req for req in required_types if req not in uploaded_set]
        present_optional = [opt for opt in optional_types if opt in uploaded_set]

        # 3. Decision
        if missing_required:
            error_msg = self._build_error_message(claim_category, required_types, uploaded_types, missing_required)
            return {
                "status": "FAILED",
                "error_type": "MISSING_REQUIRED_DOCUMENTS",
                "message": error_msg,
                "details": {
                    "classified_docs": classified_results,
                    "missing": missing_required,
                    "optional_found": present_optional
                }
            }

        return {
            "status": "SUCCESS",
            "message": "All required documents are present.",
            "details": {
                "classified_docs": classified_results,
                "optional_found": present_optional
            }
        }

    def _classify_document(self, text: str) -> Dict[str, Any]:
        """Uses OpenAI to classify document and provide confidence."""
        if not text or len(text.strip()) < 10:
            return {"doc_type": "UNKNOWN", "confidence": 0.0}

        prompt = f"""
        You are an expert medical document classifier for an Indian health insurance company.
        Analyze the provided text and classify the document into EXACTLY ONE category:

        1. PRESCRIPTION: 
           - Characteristics: Doctor's letterhead, diagnosis, "Rx" symbol, list of medicines, or orders for diagnostic tests to be done.
           - Note: A document listing tests to be performed (e.g., "Tests: CBC, MRI") is a PRESCRIPTION, not a Lab Report.

        2. HOSPITAL_BILL:
           - Characteristics: Invoice, bill number, hospital name, consultation fees, or service charges.

        3. PHARMACY_BILL:
           - Characteristics: Pharmacy name, drug license number, list of medicines with batch/expiry and prices.

        4. LAB_REPORT:
           - Characteristics: Clinical test results with values, units, and normal ranges (e.g., "Hemoglobin: 13.2 g/dL").
           - Note: Must contain actual results. If it only lists tests without results, it is a PRESCRIPTION.

        5. UNKNOWN:
           - Use this for blurry text, unreadable content, or documents that don't fit the above.

        Document Text:
        {text[:3000]}

        Return ONLY a JSON object: {{"doc_type": "CATEGORY", "confidence": 0.95}}
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                response_format={ "type": "json_object" }
            )
            result = json.loads(response.choices[0].message.content)
            result["doc_type"] = result.get("doc_type", "UNKNOWN").upper()
            logger.info(f"   ∟ Classified: {result['doc_type']} ({result['confidence']})")
            return result
        except Exception as e:
            logger.error(f"Error during document classification: {e}")
            return {"doc_type": "UNKNOWN", "confidence": 0.0}

    def _build_error_message(self, category: str, required: List[str], uploaded: List[str], missing: List[str]) -> str:
        """Builds a human-friendly actionable error message with category-specific context."""
        category_name = category.replace("_", " ").title()
        
        # Category-specific guidance
        guidance = {
            "CONSULTATION": "Needs a Prescription for treatment proof and a Hospital Bill for the consultation fee.",
            "PHARMACY": "Requires a Prescription to validate the medicines and a Pharmacy Bill for the cost.",
            "DIAGNOSTIC": "Must have a Prescription, the Lab Report/Results, and the Hospital Bill for the testing fee.",
            "DENTAL": "Requires a Hospital Bill for the dental procedure fees.",
            "VISION": "Requires a Prescription for glasses/contacts and a Hospital Bill for the examination fee.",
            "ALTERNATIVE_MEDICINE": "Needs a Prescription from a registered practitioner and a Hospital Bill."
        }

        has_unknown = "UNKNOWN" in uploaded
        detected_types = [u for u in set(uploaded) if u != "UNKNOWN"]
        duplicate_types = [t for t in set(uploaded) if uploaded.count(t) > 1 and t != "UNKNOWN"]
        
        if not detected_types and not has_unknown:
            return (f"No documents were found for your {category_name} claim. "
                    f"{guidance.get(category, '')} "
                    f"Please upload: {', '.join(required).replace('_', ' ').title()}.")

        error_parts = []
        if has_unknown:
            error_parts.append("one or more documents are blurry, unreadable, or not recognized as medical documents.")
            
        if missing:
            missing_fmt = ", ".join([m.replace("_", " ").title() for m in missing])
            error_parts.append(f"we are still missing your {missing_fmt}.")
        
        if detected_types:
            detected_fmt = ", ".join([u.replace("_", " ").title() for u in detected_types])
            error_parts.append(f"We successfully identified your {detected_fmt}.")
            
        if duplicate_types:
            dup_fmt = ", ".join([t.replace("_", " ").title() for t in duplicate_types])
            error_parts.append(f"(Note: We found multiple {dup_fmt}).")

        main_msg = f"Your {category_name} claim is incomplete: {' '.join(error_parts)}"
        footer = f"\n\nContext: {guidance.get(category, '')} Please upload clear photos of the missing documents to proceed."
        
        return main_msg + footer