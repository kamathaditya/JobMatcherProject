"""
FastAPI service that accepts a job‑posting form + PDF résumés,
scores them with Gemini 2.0 Flash, and returns JSON for the UI.

Endpoints
---------
POST /api/match      ←  front‑end uploads form‑data here
GET  /api/download/{id}  ←  serves winning résumé for download
"""

from __future__ import annotations
from dotenv import load_dotenv; load_dotenv()

import os, io, json, uuid, pathlib, tempfile, re
from typing import List, Dict

import pdfplumber
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from google import genai

# ─────────────────────────── configuration
API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    raise RuntimeError("Set GOOGLE_API_KEY in .env or as an env‑var")

client      = genai.Client(api_key=API_KEY)
MODEL_NAME  = "gemini-2.0-flash"
TMP_DIR     = pathlib.Path(tempfile.gettempdir()) / "best_resume_dl"
TMP_DIR.mkdir(exist_ok=True)

# ─────────────────────────── FastAPI app
app = FastAPI(title="Resume Matcher API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # dev‑only; tighten for prod
    allow_methods=["POST"],
    allow_headers=["*"],
)

# ─────────────────────────── helpers
def _read_pdf_bytes(b: bytes) -> str:
    with pdfplumber.open(io.BytesIO(b)) as pdf:
        return "\n".join(p.extract_text() or "" for p in pdf.pages)

def _candidate_name(fname: str) -> str:
    return pathlib.Path(fname).stem.replace("_", " ").replace("-", " ")

_fence_re = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.S)
def _strip_fence(txt: str) -> str:
    m = _fence_re.search(txt)
    return m.group(1).strip() if m else txt.strip()

def _build_prompt(job: Dict, resumes: List[Dict]) -> str:
    sys_msg = (
        "You are an experienced technical recruiter. Compare each resume to the job description, "
        "title, qualification and preference. Score each resume from 1 (poor fit) to 10 (perfect fit). "
        "After scoring, select the single best resume_id based on the scores. Provide the best resume "
        "with the resume_id, name of the person and give me a brief description of why that is the best "
        "match. Respond with JSON ONLY in this schema (no markdown, no code fences):\n\n"
        "{\n  \"scores\": [\n    {\"resume_id\": int, \"candidate_name\": str, \"score\": int, \"reasons\": str}\n  ],"
        "\n  \"best_resume_id\": int, \"candidate_name\": str, \n  \"reason\": str\n}"
    )
    user_msg = json.dumps({"job_posting": job, "resumes": resumes}, ensure_ascii=False)
    return f"{sys_msg}\n\n{user_msg}"

# ─────────────────────────── /api/match
@app.post("/api/match")
async def match(
    role: str           = Form(...),
    description: str    = Form(...),
    qualifications: str = Form(""),
    preferences: str    = Form(""),
    resumes: List[UploadFile] = File(...),
):
    # 1) job dict
    job = {
        "title": role,
        "description": description,
        "qualifications": qualifications.splitlines(),
        "preferences": preferences.splitlines(),
    }

    # 2) extract résumé text
    res_list: List[Dict] = []
    for idx, uf in enumerate(resumes):
        if uf.content_type != "application/pdf":
            raise HTTPException(400, f"{uf.filename} is not a PDF")
        pdf_bytes = await uf.read()
        res_list.append(
            {
                "resume_id": idx,
                "candidate_name": _candidate_name(uf.filename),
                "text": _read_pdf_bytes(pdf_bytes),
                "raw": pdf_bytes,
                "filename": uf.filename,
            }
        )

    # 3) Gemini call
    prompt   = _build_prompt(job, [{k:v for k,v in r.items() if k!='raw'} for r in res_list])
    response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
    raw_txt  = response.text
    clean    = _strip_fence(raw_txt)

    try:
        payload = json.loads(clean)
    except json.JSONDecodeError:
        raise HTTPException(500, f"Gemini returned non‑JSON:\n{raw_txt}")

    # 4) pick winner + save for download
    win_id = payload["best_resume_id"]
    winner = next(r for r in res_list if r["resume_id"] == win_id)

    dl_name = f"{uuid.uuid4().hex}_{winner['filename']}"
    (TMP_DIR / dl_name).write_bytes(winner["raw"])

    # 5) build response for front‑end
    score = next(s["score"] for s in payload["scores"] if s["resume_id"] == win_id)
    out = {
        "candidate": payload["candidate_name"],
        "score":     score,
        "reason":    payload["reason"],
        "resumeName": winner["filename"],
        "resumeUrl": f"/api/download/{dl_name}",
    }
    return JSONResponse(out)

# ─────────────────────────── /api/download/{id}
@app.get("/api/download/{file_id}")
def download(file_id: str):
    path = TMP_DIR / file_id
    if not path.exists():
        raise HTTPException(404, "File not found")
    return FileResponse(path, media_type="application/pdf",
                        filename=path.name.split("_",1)[1])
