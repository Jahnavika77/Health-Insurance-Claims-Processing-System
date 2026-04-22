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
        """
        parsed_results = []
        
        for i, text in enumerate(document_texts):
            doc_type = classified_docs[i].get("doc_type", "UNKNOWN")
            logger.info(f"Parsing document {i+1} (Type: {doc_type})...")
            
            parsed_data = self._extract_data(text, doc_type)
            parsed_results.append({
                "doc_type": doc_type,
                "extracted_data": parsed_data
            })
            
        return parsed_results

    def _extract_data(self, text: str, doc_type: str) -> Dict[str, Any]:
        """Uses OpenAI to extract structured fields based on document type."""
        
        prompt = f"""
        You are a medical data extraction expert. Extract structured information from the following {doc_type} text.
        
        Rules:
        1. Extract names EXACTLY as they appear.
        2. For amounts, extract only numbers.
        3. If a field is not found, return null.
        4. Provide a 'confidence' (0.0-1.0) for each field based on how clear the text was.

        Required Fields for {doc_type}:
        - patient_name
        - date (YYYY-MM-DD format if possible)
        """

        if doc_type == "PRESCRIPTION":
            prompt += """
        - doctor_name
        - doctor_registration (MCN/Registration number)
        - diagnosis (Reason for consultation)
        - medicines (List of strings)
        - tests_ordered (List of strings)
            """
        elif doc_type == "HOSPITAL_BILL":
            prompt += """
        - hospital_name
        - bill_number
        - line_items (List of objects with 'description' and 'amount')
        - total_amount
            """
        elif doc_type == "PHARMACY_BILL":
            prompt += """
        - pharmacy_name
        - medicines (List of objects with 'name', 'batch', 'expiry', 'amount')
        - total_amount
            """
        elif doc_type == "LAB_REPORT":
            prompt += """
        - lab_name
        - test_name
        - results (List of objects with 'parameter', 'value', 'unit', 'normal_range')
            """

        prompt += f"\n\nDocument Text:\n{text[:4000]}"
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                response_format={ "type": "json_object" }
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            logger.error(f"Error during data extraction: {e}")
            return {"error": str(e)}
