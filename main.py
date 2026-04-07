from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import google.generativeai as genai
import json
import re
import os
from collections import Counter
from sqlalchemy import func, distinct
from database import SessionLocal, AnalysisModel, BiasRecordModel

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-3.1-flash-lite-preview")

limiter = Limiter(key_func=get_remote_address)

app = FastAPI()

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class TextRequest(BaseModel):
    username: str
    text: str


def parse_json_response(text: str) -> dict:
    cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", text).strip()
    return json.loads(cleaned)


@app.get("/")
def read_index():
    return FileResponse("index.html")


@app.post("/analyze")
@limiter.limit("10/minute")
def analyze(req: TextRequest, request: Request):
    try:
        print("Step 1: received text from user:", req.username)

        prompt = f"""
        You are an expert in cognitive psychology and critical thinking.

        Analyze the following text for cognitive biases:

        TEXT: {req.text}

        Identify ALL cognitive biases present. For each bias return:
        - name: the bias name
        - explanation: why this bias is present in the text
        - impact: how it affects the thinking or decision
        - reframe: how to think about it more objectively

        Also give an overall reasoning quality score from 1-10.

        Return ONLY valid JSON in this exact format:
        {{
            "score": <integer 1-10>,
            "summary": "<one sentence overall assessment>",
            "biases": [
                {{
                    "name": "<bias name>",
                    "explanation": "<why it's present>",
                    "impact": "<how it affects thinking>",
                    "reframe": "<how to think more objectively>"
                }}
            ]
        }}

        If no biases are found, return an empty biases array and a high score.
        Return only JSON, no explanation.
        """

        print("Step 2: calling Gemini...")
        response = model.generate_content(prompt)
        print("Step 3: Gemini response:", response.text)

        result = parse_json_response(response.text)
        print("Step 4: parsed result")

        db = SessionLocal()
        new_analysis = AnalysisModel(
            username=req.username,
            text=req.text[:500],
            score=result["score"],
            summary=result["summary"],
            bias_count=len(result["biases"])
        )
        db.add(new_analysis)
        db.commit()
        db.refresh(new_analysis)

        for bias in result["biases"]:
            bias_record = BiasRecordModel(
                username=req.username,
                bias_name=bias["name"],
                explanation=bias["explanation"],
                analysis_id=new_analysis.id
            )
            db.add(bias_record)
        db.commit()
        db.close()

        return result

    except Exception as e:
        print("ERROR:", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/history/{username}")
def history(username: str):
    try:
        db = SessionLocal()
        analyses = db.query(AnalysisModel).filter(
            AnalysisModel.username == username
        ).order_by(AnalysisModel.id.desc()).limit(10).all()
        db.close()

        return [
            {
                "id": a.id,
                "text_preview": a.text[:100] + "...",
                "score": a.score,
                "summary": a.summary,
                "bias_count": a.bias_count
            }
            for a in analyses
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/profile/{username}")
def profile(username: str):
    try:
        db = SessionLocal()

        analyses = db.query(AnalysisModel).filter(
            AnalysisModel.username == username
        ).all()
        total_analyses = len(analyses)

        if total_analyses == 0:
            db.close()
            return {
                "total_analyses": 0,
                "average_score": 0,
                "top_biases": [],
                "bias_dna": "No analyses yet. Start analyzing text to build your profile.",
                "improvement_tip": ""
            }

        avg_score = round(sum(a.score for a in analyses) / total_analyses, 1)

        all_biases = db.query(BiasRecordModel).filter(
            BiasRecordModel.username == username
        ).all()
        bias_names = [b.bias_name for b in all_biases]
        bias_counts = Counter(bias_names)
        top_biases = [
            {"name": name, "count": count}
            for name, count in bias_counts.most_common(5)
        ]

        db.close()

        if top_biases:
            top_bias_names = [b["name"] for b in top_biases[:3]]
            bias_dna = f"Your thinking is most influenced by: {', '.join(top_bias_names)}."
        else:
            bias_dna = "No biases detected yet — great critical thinking!"

        improvement_tip = ""
        if top_biases:
            top = top_biases[0]["name"].lower()
            if "confirmation" in top:
                improvement_tip = "Try actively seeking out views that challenge your beliefs before making decisions."
            elif "bandwagon" in top or "social" in top:
                improvement_tip = "Before following the crowd, ask yourself: what's my independent reason for this?"
            elif "availability" in top:
                improvement_tip = "Seek statistical data rather than relying on vivid or recent examples."
            elif "recency" in top:
                improvement_tip = "Look at long-term trends, not just recent events, when making decisions."
            elif "fomo" in top or "fear" in top:
                improvement_tip = "Pause before acting on urgency. Ask: would I make this decision without time pressure?"
            elif "anchor" in top:
                improvement_tip = "Question your first reference point — is it actually relevant to your decision?"
            elif "sunk" in top:
                improvement_tip = "Focus on future value, not past investment, when deciding whether to continue."
            else:
                improvement_tip = "Practice slowing down and questioning your first instinct before deciding."

        return {
            "total_analyses": total_analyses,
            "average_score": avg_score,
            "top_biases": top_biases,
            "bias_dna": bias_dna,
            "improvement_tip": improvement_tip
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/clear/{username}")
def clear_data(username: str):
    try:
        db = SessionLocal()
        db.query(BiasRecordModel).filter(BiasRecordModel.username == username).delete()
        db.query(AnalysisModel).filter(AnalysisModel.username == username).delete()
        db.commit()
        db.close()
        return {"message": f"All data cleared for {username}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/global-insights")
def global_insights():
    try:
        db = SessionLocal()

        total_analyses = db.query(AnalysisModel).count()

        if total_analyses == 0:
            db.close()
            return {
                "total_analyses": 0,
                "total_users": 0,
                "most_common_biases": [],
                "most_dangerous_biases": [],
                "avg_global_score": 0
            }

        total_users = db.query(func.count(distinct(AnalysisModel.username))).scalar()

        avg_global_score = round(
            db.query(func.avg(AnalysisModel.score)).scalar(), 1
        )

        bias_counts = db.query(
            BiasRecordModel.bias_name,
            func.count(BiasRecordModel.bias_name).label("count")
        ).group_by(BiasRecordModel.bias_name).order_by(
            func.count(BiasRecordModel.bias_name).desc()
        ).limit(10).all()

        most_common_biases = [
            {"name": b.bias_name, "count": b.count}
            for b in bias_counts
        ]

        dangerous = db.query(
            BiasRecordModel.bias_name,
            func.avg(AnalysisModel.score).label("avg_score"),
            func.count(BiasRecordModel.bias_name).label("count")
        ).join(
            AnalysisModel, BiasRecordModel.analysis_id == AnalysisModel.id
        ).group_by(
            BiasRecordModel.bias_name
        ).having(
            func.count(BiasRecordModel.bias_name) >= 1
        ).order_by(
            func.avg(AnalysisModel.score).asc()
        ).limit(5).all()

        most_dangerous_biases = [
            {
                "name": d.bias_name,
                "avg_score": round(d.avg_score, 1),
                "count": d.count
            }
            for d in dangerous
        ]

        db.close()

        return {
            "total_analyses": total_analyses,
            "total_users": total_users,
            "avg_global_score": avg_global_score,
            "most_common_biases": most_common_biases,
            "most_dangerous_biases": most_dangerous_biases
        }

    except Exception as e:
        print("ERROR:", str(e))
        raise HTTPException(status_code=500, detail=str(e))
    # --- ADD THIS TO THE VERY BOTTOM OF YOUR MAIN.PY ---

@app.get("/compare/{username}")
def compare(username: str):
    try:
        db = SessionLocal()
        
        # User stats
        user_analyses = db.query(AnalysisModel).filter(
            AnalysisModel.username == username
        ).all()
        
        if not user_analyses:
            db.close()
            return {"enough_data": False}
            
        user_avg = round(sum(a.score for a in user_analyses) / len(user_analyses), 1)
        user_total = len(user_analyses)
        
        # Global stats
        global_total = db.query(AnalysisModel).count()
        
        # Handle case where there are no global analyses
        global_avg_scalar = db.query(func.avg(AnalysisModel.score)).scalar()
        global_avg = round(global_avg_scalar, 1) if global_avg_scalar else 0.0
        
        # User top bias
        user_biases = db.query(BiasRecordModel).filter(
            BiasRecordModel.username == username
        ).all()
        user_bias_names = [b.bias_name for b in user_biases]
        user_top_bias_calc = Counter(user_bias_names).most_common(1)
        user_top_bias = user_top_bias_calc[0][0] if user_top_bias_calc else "None"
        
        # Global top bias
        global_top = db.query(
            BiasRecordModel.bias_name,
            func.count(BiasRecordModel.bias_name).label("count")
        ).group_by(BiasRecordModel.bias_name).order_by(
            func.count(BiasRecordModel.bias_name).desc()
        ).first()
        global_top_bias = global_top.bias_name if global_top else "None"
        
        db.close()
        
        # Verdict logic
        if user_avg > global_avg + 1:
            verdict = "🏆 You reason significantly better than the average MindLens user!"
            verdict_color = "green"
        elif user_avg > global_avg:
            verdict = "✅ You reason slightly better than the average MindLens user."
            verdict_color = "green"
        elif user_avg == global_avg:
            verdict = "➡️ Your reasoning is on par with the average MindLens user."
            verdict_color = "neutral"
        else:
            verdict = "📉 Your reasoning score is below the global average — keep practicing!"
            verdict_color = "red"
            
        return {
            "enough_data": True,
            "user_avg": user_avg,
            "global_avg": global_avg,
            "user_total": user_total,
            "global_total": global_total,
            "user_top_bias": user_top_bias,
            "global_top_bias": global_top_bias,
            "verdict": verdict,
            "verdict_color": verdict_color
        }
    except Exception as e:
        print("Compare ERROR:", str(e))
        raise HTTPException(status_code=500, detail=str(e))