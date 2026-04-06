from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import google.generativeai as genai
import json
import re
import os
from database import SessionLocal, AnalysisModel

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

        # Save to database
        db = SessionLocal()
        new_analysis = AnalysisModel(
            text=req.text[:500],
            score=result["score"],
            summary=result["summary"],
            bias_count=len(result["biases"])
        )
        db.add(new_analysis)
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