import os
import json
import re
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse # Import for HTML
from pydantic import BaseModel
import google.generativeai as genai
from sqlalchemy import Column, Integer, String, Text, ForeignKey, create_engine
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

Base.metadata.create_all(bind=engine)

# --- GEMINI SETUP ---
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-3.1-flash-lite-preview")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 1. YE HAI VO FIX: Jo tumhara interface wapas layega ---
@app.get("/")
async def serve_index():
    return FileResponse('index.html')

class AnalyzeRequest(BaseModel):
    username: str
    text: str

# --- 2. ANALYZE ROUTE ---
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

# --- 3. HISTORY ROUTE ---
@app.get("/history/{username}")
async def get_history(username: str):
    db = SessionLocal()
    try:
        results = db.query(Analysis).filter(Analysis.username == username).order_by(Analysis.id.desc()).all()
        history = []
        for r in results:
            history.append({
                "text": r.text,
                "score": r.score,
                "summary": r.summary,
                "biases": [{"name": b.bias_name, "explanation": b.explanation, "reframe": b.reframe} for b in r.biases]
            })
        return history
    finally:
        db.close()