# Health Insurance Claims Processing System

An automated, multi-agent AI system for processing health insurance claims — built for the Plum AI Engineer assignment.

## 🏗️ Architecture

The system uses a **6-agent sequential pipeline** to process each claim:

| Agent | Name | Role |
|-------|------|------|
| 1 | Document Validator | Classifies uploads, catches wrong/missing documents early |
| 2 | Document Parser | Extracts structured JSON (patient, diagnosis, amounts, etc.) |
| 3 | Policy Checker | Applies waiting periods, exclusions, pre-auth, financial rules |
| 4 | Fraud Detector | Flags frequency anomalies, duplicates, identity mismatches |
| 5 | Decision Engine | Synthesizes all results into APPROVED / PARTIAL / REJECTED / MANUAL_REVIEW |
| 6 | Trace Builder | Assembles a full auditable trace of all agent outputs |

**AI Model**: GPT-4o-mini (OpenAI) for document classification, extraction, and OCR (Vision API).  
**Database**: PostgreSQL for claim history and traces.

> See [ARCHITECTURE.md](./ARCHITECTURE.md) for full design details, trade-offs, and scaling strategy.  
> See [CONTRACTS.md](./CONTRACTS.md) for component interface specifications.  
> See [EVAL_REPORT.md](./EVAL_REPORT.md) for test case results.

---

## 🚀 Quick Start (Local)

### Prerequisites
- Python 3.9+
- PostgreSQL running locally
- OpenAI API key

### Backend
```bash
cd backend
python -m venv env
source env/bin/activate
pip install -r requirements.txt

# Create .env file
cat > .env << EOF
OPENAI_API_KEY=your-key-here
DATABASE_URL=postgresql://user:password@localhost/claims_db
EOF

# Start the server
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Frontend
```bash
cd frontend
# Update API_BASE in app.js to http://localhost:8000
# Then serve with any static server:
python -m http.server 3000
```

Open `http://localhost:3000` in your browser.

---

## 🌐 Deployed URLs

- **Frontend**: Deployed on Render (Static Site via Nginx)
- **Backend**: Deployed on Render (Docker Web Service)
- **Database**: Render Managed PostgreSQL

---

## 📂 Project Structure

```
Health-Insurance-Claims-Processing-System/
├── ARCHITECTURE.md          # System design document
├── CONTRACTS.md             # Component interface contracts
├── EVAL_REPORT.md           # Test case evaluation results
├── README.md                # This file
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── .env                 # Environment variables (not committed)
│   ├── app/
│   │   ├── main.py          # FastAPI app, pipeline orchestration
│   │   └── config.py        # Policy loading
│   ├── agents/
│   │   ├── document_validator.py   # Agent 1
│   │   ├── document_parser.py      # Agent 2
│   │   ├── policy_checker.py       # Agent 3
│   │   ├── fraud_detector.py       # Agent 4
│   │   ├── decision_engine.py      # Agent 5
│   │   └── trace_builder.py        # Agent 6
│   ├── services/
│   │   └── ocr.py           # OpenAI Vision OCR
│   ├── database/
│   │   └── db.py            # PostgreSQL via SQLAlchemy
│   └── data/
│       ├── assignment.md
│       ├── policy_terms.json
│       ├── test_cases.json
│       └── sample_documents_guide.md
│
└── frontend/
    ├── Dockerfile
    ├── index.html
    ├── app.js
    └── style.css
```

---

## 🧪 Testing

The system has been evaluated against all 12 test cases from `test_cases.json`:

| Result | Count | Cases |
|--------|-------|-------|
| ✅ Full Pass | 5 | TC001, TC005, TC007, TC012, TC004* |
| ⚠️ Partial | 5 | TC002, TC003, TC009, TC010, TC011 |
| ❌ Fail | 2 | TC006, TC008 |

See [EVAL_REPORT.md](./EVAL_REPORT.md) for detailed analysis of each case.

---

## 📋 Key Technical Decisions

1. **Multi-agent over monolith** — Clean separation, each agent independently testable and replaceable
2. **OpenAI Vision over Tesseract** — Far better accuracy on Indian medical documents (handwritten, stamped, photographed)
3. **Async job processing** — LLM calls take 5-15s; async keeps the API responsive
4. **Policy from JSON, not code** — Zero code changes to modify coverage rules
5. **PostgreSQL over SQLite** — Production-grade, concurrent-safe persistence

---

## ⚖️ Known Limitations

1. Line-item level exclusions not supported (entire claim rejected if any excluded item found)
2. Per-claim limit (₹5,000) not enforced
3. Pipeline halts on component failure rather than degrading gracefully
4. Copay deductions cause `PARTIAL` verdict instead of `APPROVED`
5. In-memory job tracking doesn't survive process restarts