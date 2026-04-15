import os
import json
import re
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import google.generativeai as genai
from sqlalchemy import Column, Integer, String, Text, ForeignKey, create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

# --- DATABASE SETUP ---
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./mindlens.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Analysis(Base):
    __tablename__ = "analyses"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String)
    text = Column(Text)
    score = Column(Integer)
    summary = Column(Text)
    biases = relationship("BiasRecord", back_populates="parent")

class BiasRecord(Base):
    __tablename__ = "bias_records"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String)
    bias_name = Column(String)
    explanation = Column(Text)
    reframe = Column(Text)
    analysis_id = Column(Integer, ForeignKey("analyses.id"))
    parent = relationship("Analysis", back_populates="biases")

# Create tables if they don't exist
Base.metadata.create_all(bind=engine)

# Fix missing columns automatically (safe to run every time)
with engine.connect() as conn:
    try:
        conn.execute(text("ALTER TABLE bias_records ADD COLUMN reframe TEXT"))
        conn.commit()
        print("✅ Added missing 'reframe' column")
    except:
        print("✅ 'reframe' column already exists, skipping")

# --- GEMINI SETUP ---
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash-8b")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def serve_index():
    return FileResponse('index.html')

class AnalyzeRequest(BaseModel):
    username: str
    text: str

@app.post("/analyze")
async def analyze(request: AnalyzeRequest):
    db = SessionLocal()
    try:
        print(f"Step 1: received text from {request.username}")

        prompt = f"""
        Analyze the following text for cognitive biases: "{request.text}"
        Return ONLY a JSON object with this structure:
        {{
            "score": (0-100 objectivity score),
            "summary": "short summary",
            "biases": [
                {{"name": "Bias Name", "explanation": "why", "reframe": "how to fix"}}
            ]
        }}
        """

        print("Step 2: calling Gemini...")
        response = model.generate_content(prompt)

        clean_json = re.sub(r'```json|```', '', response.text).strip()
        data = json.loads(clean_json)
        print("Step 3: Gemini response received and parsed")

        new_analysis = Analysis(
            username=request.username,
            text=request.text,
            score=data.get('score', 0),
            summary=data.get('summary', '')
        )
        db.add(new_analysis)
        db.commit()
        db.refresh(new_analysis)

        for b in data.get('biases', []):
            new_bias = BiasRecord(
                username=request.username,
                bias_name=b.get('name', 'Unknown'),
                explanation=b.get('explanation', ''),
                reframe=b.get('reframe', ''),
                analysis_id=new_analysis.id
            )
            db.add(new_bias)

        db.commit()
        print("Step 4: Saved to database successfully")
        return data

    except Exception as e:
        print(f"ERROR: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.get("/history/{username}")
async def get_history(username: str):
    db = SessionLocal()
    try:
        results = db.query(Analysis).filter(Analysis.username == username).order_by(Analysis.id.desc()).all()
        history = []
        for r in results:
            history.append({
                "text": r.text,
                "text_preview": r.text[:80] + "..." if len(r.text) > 80 else r.text,
                "score": r.score,
                "summary": r.summary,
                "biases": [{"name": b.bias_name, "explanation": b.explanation, "reframe": b.reframe} for b in r.biases]
            })
        return history
    finally:
        db.close()

@app.get("/profile/{username}")
async def get_profile(username: str):
    db = SessionLocal()
    try:
        analyses = db.query(Analysis).filter(Analysis.username == username).all()
        if not analyses:
            return {"total_analyses": 0, "average_score": 0, "bias_dna": "No analyses yet.", "top_biases": []}

        total = len(analyses)
        avg_score = round(sum(a.score for a in analyses) / total)

        bias_counts = {}
        for a in analyses:
            for b in a.biases:
                bias_counts[b.bias_name] = bias_counts.get(b.bias_name, 0) + 1

        top_biases = sorted([{"name": k, "count": v} for k, v in bias_counts.items()], key=lambda x: -x["count"])[:5]
        bias_dna = ", ".join([b["name"] for b in top_biases]) if top_biases else "No patterns yet."

        return {
            "total_analyses": total,
            "average_score": avg_score,
            "bias_dna": bias_dna,
            "top_biases": top_biases
        }
    finally:
        db.close()

@app.get("/compare/{username}")
async def compare(username: str):
    db = SessionLocal()
    try:
        user_analyses = db.query(Analysis).filter(Analysis.username == username).all()
        all_analyses = db.query(Analysis).all()

        if len(user_analyses) < 2 or len(all_analyses) < 5:
            return {"enough_data": False}

        user_avg = round(sum(a.score for a in user_analyses) / len(user_analyses))
        global_avg = round(sum(a.score for a in all_analyses) / len(all_analyses))

        if user_avg > global_avg:
            verdict = f"🏆 You reason better than average! Your score ({user_avg}) beats the global avg ({global_avg})."
        elif user_avg < global_avg:
            verdict = f"📈 Room to grow! Your score ({user_avg}) is below the global avg ({global_avg})."
        else:
            verdict = f"⚖️ You're exactly at the global average ({global_avg}). Keep going!"

        return {"enough_data": True, "user_avg": user_avg, "global_avg": global_avg, "verdict": verdict}
    finally:
        db.close()

@app.get("/global-insights")
async def global_insights():
    db = SessionLocal()
    try:
        all_analyses = db.query(Analysis).all()
        if not all_analyses:
            return {"total_analyses": 0, "avg_global_score": 0, "most_common_biases": [], "most_dangerous_biases": []}

        total = len(all_analyses)
        avg_score = round(sum(a.score for a in all_analyses) / total)

        bias_counts = {}
        bias_scores = {}
        for a in all_analyses:
            for b in a.biases:
                bias_counts[b.bias_name] = bias_counts.get(b.bias_name, 0) + 1
                if b.bias_name not in bias_scores:
                    bias_scores[b.bias_name] = []
                bias_scores[b.bias_name].append(a.score)

        most_common = sorted([{"name": k, "count": v} for k, v in bias_counts.items()], key=lambda x: -x["count"])[:5]
        most_dangerous = sorted([
            {"name": k, "avg_score": round(sum(v) / len(v))}
            for k, v in bias_scores.items()
        ], key=lambda x: x["avg_score"])[:5]

        return {
            "total_analyses": total,
            "avg_global_score": avg_score,
            "most_common_biases": most_common,
            "most_dangerous_biases": most_dangerous
        }
    finally:
        db.close()