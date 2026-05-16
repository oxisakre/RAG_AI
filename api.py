from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from rag_pipeline_gemini import query_therapeutencheck
from datetime import date, datetime
import os
import json

# ── Daily counter (shared across all users, resets at midnight) ──
_daily = {"date": None, "count": 0}

def increment_counter():
    today = date.today().isoformat()
    if _daily["date"] != today:
        _daily["date"] = today
        _daily["count"] = 0
    _daily["count"] += 1
    return _daily["count"]

def get_counter():
    today = date.today().isoformat()
    if _daily["date"] != today:
        return 0
    return _daily["count"]

app = FastAPI(title="Sanoanimal RAG API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

HTML_FILE  = os.path.join(os.path.dirname(__file__), "therapeutencheck (1).html")
LOG_FILE   = os.path.join(os.path.dirname(__file__), "queries.log")

def log_query(question: str, answer: str, status: str = "ok"):
    entry = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "question": question,
        "answer": answer[:500] if answer else "",
        "status": status
    }
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

@app.get("/")
def serve_frontend():
    return FileResponse(HTML_FILE, media_type="text/html")

class QueryRequest(BaseModel):
    question: str

@app.post("/ask")
def ask_rag(request: QueryRequest):
    print(f"Nueva petición recibida: {request.question}")
    try:
        resultado = query_therapeutencheck(request.question)
        count = increment_counter()
        log_query(request.question, resultado["answer"])
        return {
            "status": "success",
            "question": request.question,
            "answer": resultado["answer"],
            "model": resultado["model"],
            "questions_today": count,
            "daily_limit": resultado["daily_limit"]
        }
    except Exception as e:
        err = str(e)
        if "429" in err or "RESOURCE_EXHAUSTED" in err:
            print(f"[QUOTA] Rate limit alcanzado: {err[:500]}")
            log_query(request.question, "", "quota_exceeded")
            raise HTTPException(status_code=429, detail="API quota exceeded. Please try again in a few minutes.")
        if "503" in err or "UNAVAILABLE" in err or "timed out" in err.lower() or "timeout" in err.lower():
            print(f"[UNAVAILABLE] Modelo no disponible temporalmente: {err[:200]}")
            log_query(request.question, "", "unavailable")
            raise HTTPException(status_code=503, detail="Model temporarily unavailable. Please try again in a few seconds.")
        print(f"[ERROR] {err}")
        log_query(request.question, "", "error")
        raise HTTPException(status_code=500, detail="Internal server error.")


@app.get("/history", response_class=HTMLResponse)
def query_history():
    if not os.path.exists(LOG_FILE):
        return "<p>No queries yet.</p>"
    with open(LOG_FILE, encoding="utf-8") as f:
        entries = [json.loads(l) for l in f if l.strip()]
    entries.reverse()
    rows = ""
    for e in entries[:100]:
        color = "#2d4a2d" if e["status"] == "ok" else "#c0392b"
        rows += f"""<tr>
            <td style='color:#888;white-space:nowrap'>{e['ts']}</td>
            <td><b style='color:{color}'>{e['question']}</b></td>
            <td style='font-size:12px;color:#444'>{e['answer'][:200]}{'…' if len(e['answer'])>200 else ''}</td>
            <td style='color:{color}'>{e['status']}</td>
        </tr>"""
    return f"""<!DOCTYPE html><html><head><meta charset='utf-8'>
    <title>Sanoanimal — Query History</title>
    <style>body{{font-family:sans-serif;padding:24px;background:#f5f0e4}}
    table{{border-collapse:collapse;width:100%}}
    th{{background:#2d4a2d;color:#fff;padding:8px 12px;text-align:left}}
    td{{padding:8px 12px;border-bottom:1px solid #ddd;vertical-align:top}}
    tr:hover td{{background:#eee}}</style></head>
    <body><h2>Query History (last 100)</h2>
    <p>Total logged: {len(entries)}</p>
    <table><tr><th>Timestamp</th><th>Question</th><th>Answer (preview)</th><th>Status</th></tr>
    {rows}</table></body></html>"""