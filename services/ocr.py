import logging
import os
import base64
from typing import Optional
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger("OCRService")

def encode_image(image_path: str) -> str:
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def extract_text_from_image(file_path: str) -> str:
    logger.info(f"🔍 Starting extraction for: {file_path}")
    
    # 1. Handle PDF (Text-based)
    if file_path.lower().endswith(".pdf"):
        try:
            import pdfplumber
            logger.info(f"📄 Extracting text from PDF via pdfplumber: {file_path}")
            text_content = ""
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    text_content += page.extract_text() or ""
            return text_content.strip()
        except Exception as e:
            logger.error(f"Error during PDF extraction: {e}")
            return ""

    # 2. Handle Images via OpenAI Vision (Replaces Tesseract)
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY not found. Cannot process images.")
        return "ERROR: API KEY MISSING"

    client = OpenAI(api_key=api_key)
    
    try:
        base64_image = encode_image(file_path)
        logger.info(f"👁️  Using OpenAI Vision to read document: {file_path}")
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Extract all readable text from this medical document. Maintain the layout structure where possible. Return ONLY the extracted text."},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        },
                    ],
                }
            ],
            max_tokens=2000,
        )
        
        extracted_text = response.choices[0].message.content.strip()
        logger.info(f"   ∟ Extracted {len(extracted_text)} characters via Vision.")
        return extracted_text

    except Exception as e:
        logger.error(f"Error during OpenAI Vision OCR: {e}")
        return ""