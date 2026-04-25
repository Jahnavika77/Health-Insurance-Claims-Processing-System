import os
from sqlalchemy import create_engine, Column, String, Float, DateTime, Integer, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# DATABASE_URL should be in .env: postgresql://user:password@localhost/dbname
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost/claims_db")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class ClaimHistory(Base):
    __tablename__ = "claim_history"

    id = Column(Integer, primary_key=True, index=True)
    claim_id = Column(String, unique=True, index=True)
    member_id = Column(String, index=True)
    treatment_date = Column(String)
    amount = Column(Float)
    verdict = Column(String)
    trace = Column(JSON) # Optional: Store full trace
    created_at = Column(DateTime, default=datetime.utcnow)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_history(member_id: str = ""):
    db = SessionLocal()
    try:
        query = db.query(ClaimHistory)
        if member_id:
            query = query.filter(ClaimHistory.member_id == member_id)
        claims = query.order_by(ClaimHistory.created_at.desc()).all()
        return [
            {
                "claim_id": c.claim_id,
                "member_id": c.member_id,
                "date": c.treatment_date,
                "amount": c.amount,
                "verdict": c.verdict,
                "created_at": c.created_at.isoformat(),
                "trace": c.trace
            } for c in claims
        ]
    finally:
        db.close()

def save_claim(claim_data: dict, trace_data: dict):
    db = SessionLocal()
    try:
        new_claim = ClaimHistory(
            claim_id=claim_data["claim_id"],
            member_id=claim_data["member_id"],
            treatment_date=claim_data["date"],
            amount=claim_data["amount"],
            verdict=claim_data["verdict"],
            trace=trace_data
        )
        db.add(new_claim)
        db.commit()
    finally:
        db.close()
