import json
import logging
import os
from typing import List, Dict, Any
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("DocumentParser")

class DocumentParser:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            logger.warning("OPENAI_API_KEY not found. Extraction will fail.")
        self.client = OpenAI(api_key=self.api_key)

    def parse(self, document_texts: List[str], classified_docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Parses multiple documents and returns structured JSON for each.
        Matches the output structure expected by the flowchart:
        - patient_name, diagnosis, doctor, amounts, dates, medicines, confidence_per_field
        """
        parsed_results = []
        
        for i, text in enumerate(document_texts):
            # Safe access to classified doc info
            if i < len(classified_docs):
                doc_info = classified_docs[i]
                doc_type = doc_info.get("doc_type", "UNKNOWN")
                classification_confidence = doc_info.get("confidence", 0.0)
            else:
                doc_type = "UNKNOWN"
                classification_confidence = 0.0

            logger.info(f"🔍 [Agent 2] Parsing document {i+1} as {doc_type}...")
            
            if doc_type == "UNKNOWN" or not text.strip():
                parsed_results.append({
                    "doc_type": doc_type,
                    "extracted_data": {},
                    "status": "SKIPPED",
                    "reason": "Unrecognized or empty document"
                })
                continue
                
            parsed_data = self._extract_data(text, doc_type)
            parsed_results.append({
                "doc_type": doc_type,
                "classification_confidence": classification_confidence,
                "extracted_data": parsed_data
            })
            
        return parsed_results

    def _extract_data(self, text: str, doc_type: str) -> Dict[str, Any]:
        """Uses OpenAI to extract structured fields based on document type for Indian medical context."""
        
        system_prompt = "You are a professional medical data extraction agent for an Indian health insurance company. Your goal is to convert unstructured medical text into precise JSON."
        
        user_prompt = f"""
        Extract the following fields from this {doc_type} document. 
        If a field is missing, set it to null.
        
        GENERAL FIELDS FOR ALL DOCUMENTS:
        1. patient_name: Full name of the patient.
        2. date: The primary date on the document (YYYY-MM-DD).
        3. hospital_or_clinic_name: Name of the medical facility.
        
        SPECIFIC FIELDS FOR {doc_type}:
        """

        if doc_type == "PRESCRIPTION":
            user_prompt += """
        - doctor_name: Name of the prescribing doctor (with prefix Dr. if present).
        - doctor_registration: Registration number (often starts with Reg No, MCN, SLMC, etc.).
        - diagnosis: Primary medical condition or reason for visit.
        - medicines: List of objects with {name, dosage, frequency, duration}.
        - tests_ordered: List of diagnostic tests requested (e.g., CBC, X-Ray).
            """
        elif doc_type == "HOSPITAL_BILL":
            user_prompt += """
        - bill_number: Invoice or Bill ID.
        - line_items: List of objects with {description, amount, quantity}.
        - total_amount: The final amount billed (number only).
        - tax_amount: Any GST or service tax mentioned.
            """
        elif doc_type == "PHARMACY_BILL":
            user_prompt += """
        - pharmacy_name: Name of the pharmacy.
        - medicines: List of objects with {name, batch_number, expiry_date, quantity, amount}.
        - total_amount: Total amount paid.
            """
        elif doc_type == "LAB_REPORT":
            user_prompt += """
        - lab_name: Name of the laboratory.
        - test_name: The name of the test performed (e.g., Blood Test, MRI).
        - results: List of objects with {parameter, value, unit, normal_range}.
            """

        user_prompt += """
        CRITICAL RULES:
        1. Extract names and IDs EXACTLY as they appear.
        2. For dates, standardize to YYYY-MM-DD.
        3. For currency/amounts, return only raw numbers (e.g., 500.0 instead of "₹500").
        4. INCLUDE a 'confidence_scores' object mapping each extracted field to a score between 0.0 and 1.0.
        
        DOCUMENT TEXT:
        """
        user_prompt += f"\n{text[:4000]}"
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0,
                response_format={ "type": "json_object" }
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            logger.error(f"Error during data extraction: {e}")
            return {"error": "Extraction failed", "details": str(e)}
