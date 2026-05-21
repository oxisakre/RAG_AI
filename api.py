from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from rag_pipeline_gemini import query_therapeutencheck
from datetime import date, datetime
import os
import json
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "dbname":   os.getenv("DB_NAME", "sanoanimal"),
    "user":     os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "password"),
    "host":     os.getenv("DB_HOST", "localhost"),
    "port":     os.getenv("DB_PORT", "5432"),
}

def get_db():
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    return conn

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
    language: str = "en"

@app.post("/ask")
def ask_rag(request: QueryRequest):
    print(f"Nueva petición recibida: {request.question}")
    try:
        resultado = query_therapeutencheck(request.question, language=request.language)
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


@app.get("/recent")
def recent_queries(limit: int = 4):
    if not os.path.exists(LOG_FILE):
        return []
    with open(LOG_FILE, encoding="utf-8") as f:
        entries = [json.loads(l) for l in f if l.strip()]
    ok_entries = [e for e in entries if e["status"] == "ok"]
    ok_entries.reverse()
    seen, unique = set(), []
    for e in ok_entries:
        if e["question"] not in seen:
            seen.add(e["question"])
            unique.append({"question": e["question"], "ts": e["ts"]})
        if len(unique) >= limit:
            break
    return unique


# ── REST API endpoints ────────────────────────────────────────────────────────

@app.get("/health")
def health():
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        conn.close()
        return {"status": "ok", "db": "connected"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"DB unavailable: {str(e)}")


@app.get("/api/v1/medications")
def list_medications():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT m.id, m.handelsname, w.wirkstoff_inn, w.wirkstoffklasse,
               m.zulassungsstatus, m.dosierung_pferd, m.applikationsweg,
               m.rezeptpflicht, m.fei_dopingstatus, m.wartezeit
        FROM therapeutencheck.medikamente m
        JOIN therapeutencheck.wirkstoffe w ON w.id = m.wirkstoff_id
        ORDER BY m.handelsname
    """)
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/v1/medications/{name}")
def get_medication(name: str):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT m.*, w.wirkstoff_inn, w.wirkstoffklasse, w.therapeutische_kategorie,
               w.wirkmechanismus, w.pferd_besonderheiten, w.hwz_plasma, w.metabolismus
        FROM therapeutencheck.medikamente m
        JOIN therapeutencheck.wirkstoffe w ON w.id = m.wirkstoff_id
        WHERE LOWER(m.handelsname) = LOWER(%s)
    """, (name,))
    row = cur.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail=f"Medication '{name}' not found.")
    return dict(row)


@app.get("/api/v1/substances")
def list_substances():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT id, wirkstoff_inn, wirkstoffklasse, therapeutische_kategorie,
               wirkmechanismus, hwz_plasma, metabolismus
        FROM therapeutencheck.wirkstoffe
        ORDER BY wirkstoff_inn
    """)
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/v1/substances/{name}")
def get_substance(name: str):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT * FROM therapeutencheck.wirkstoffe
        WHERE LOWER(wirkstoff_inn) = LOWER(%s)
    """, (name,))
    row = cur.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail=f"Substance '{name}' not found.")
    return dict(row)


@app.get("/api/v1/plants")
def list_plants():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT id, deutscher_name, botanischer_name, giftigkeitsstufe,
               toxin_wirkstoff, giftig_im_heu, prognose
        FROM therapeutencheck.giftpflanzen
        ORDER BY giftigkeitsstufe DESC, deutscher_name
    """)
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/v1/plants/{name}")
def get_plant(name: str):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT * FROM therapeutencheck.giftpflanzen
        WHERE LOWER(deutscher_name) = LOWER(%s)
           OR LOWER(botanischer_name) = LOWER(%s)
    """, (name, name))
    row = cur.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail=f"Plant '{name}' not found.")
    return dict(row)


@app.get("/api/v1/interactions")
def get_interactions(drug: str = Query(..., description="Drug name to look up interactions for")):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT * FROM therapeutencheck.wechselwirkungen
        WHERE LOWER(partner_a_name) ILIKE %s
           OR LOWER(partner_b_name) ILIKE %s
        ORDER BY schweregrad DESC
    """, (f"%{drug.lower()}%", f"%{drug.lower()}%"))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/v1/contraindications")
def get_contraindications(
    drug: str = Query(None, description="Drug name"),
    condition: str = Query(None, description="Condition/disease name")
):
    if not drug and not condition:
        raise HTTPException(status_code=400, detail="Provide 'drug' or 'condition' query parameter.")
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if drug:
        cur.execute("""
            SELECT * FROM therapeutencheck.kontraindikationen
            WHERE LOWER(wirkstoff_name) ILIKE %s
            ORDER BY schwere DESC
        """, (f"%{drug.lower()}%",))
    else:
        cur.execute("""
            SELECT * FROM therapeutencheck.kontraindikationen
            WHERE LOWER(erkrankung_zustand) ILIKE %s
            ORDER BY schwere DESC
        """, (f"%{condition.lower()}%",))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/v1/indications")
def list_indications():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT id, indikation, organsystem, first_line_therapie,
               first_line_wirkstoff, okapi_produkte, prognose
        FROM therapeutencheck.indikationen
        ORDER BY organsystem, indikation
    """)
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/v1/indications/{name}")
def get_indication(name: str):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT * FROM therapeutencheck.indikationen
        WHERE LOWER(indikation) ILIKE %s
    """, (f"%{name.lower()}%",))
    rows = cur.fetchall()
    conn.close()
    if not rows:
        raise HTTPException(status_code=404, detail=f"Indication '{name}' not found.")
    return [dict(r) for r in rows]


# ── History ───────────────────────────────────────────────────────────────────

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