from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import google.generativeai as genai
import json
import re
import os
from collections import Counter
from database import SessionLocal, AnalysisModel, BiasRecordModel

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-3.1-flash-lite-preview")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class TextRequest(BaseModel):
    text: str


def parse_json_response(text: str) -> dict:
    cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", text).strip()
    return json.loads(cleaned)


@app.get("/")
def read_index():
    return FileResponse("index.html")


@app.post("/analyze")
def analyze(req: TextRequest):
    try:
        print("Step 1: received text")

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

        # Save analysis to database
        db = SessionLocal()
        new_analysis = AnalysisModel(
            text=req.text[:500],
            score=result["score"],
            summary=result["summary"],
            bias_count=len(result["biases"])
        )
        db.add(new_analysis)
        db.commit()
        db.refresh(new_analysis)

        # Save each individual bias
        for bias in result["biases"]:
            bias_record = BiasRecordModel(
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


@app.get("/history")
def history():
    try:
        db = SessionLocal()
        analyses = db.query(AnalysisModel).order_by(
            AnalysisModel.id.desc()
        ).limit(10).all()
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


@app.get("/profile")
def profile():
    try:
        db = SessionLocal()

        # Get all analyses
        analyses = db.query(AnalysisModel).all()
        total_analyses = len(analyses)

        if total_analyses == 0:
            db.close()
            return {
                "total_analyses": 0,
                "average_score": 0,
                "top_biases": [],
                "bias_dna": "No analyses yet. Start analyzing text to build your bias profile.",
                "improvement_tip": ""
            }

        # Average score
        avg_score = round(sum(a.score for a in analyses) / total_analyses, 1)

        # Count all biases
        all_biases = db.query(BiasRecordModel).all()
        bias_names = [b.bias_name for b in all_biases]
        bias_counts = Counter(bias_names)
        top_biases = [
            {"name": name, "count": count}
            for name, count in bias_counts.most_common(5)
        ]

        db.close()

        # Generate bias DNA description
        if top_biases:
            top_bias_names = [b["name"] for b in top_biases[:3]]
            bias_dna = f"Your thinking is most influenced by: {', '.join(top_bias_names)}."
        else:
            bias_dna = "No biases detected yet — great critical thinking!"

        # Improvement tip based on top bias
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