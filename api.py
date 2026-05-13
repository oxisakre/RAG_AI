from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from rag_pipeline_gemini import query_therapeutencheck

app = FastAPI(title="Sanoanimal RAG API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    question: str

@app.post("/ask")
def ask_rag(request: QueryRequest):
    print(f"Nueva petición recibida: {request.question}")
    try:
        resultado = query_therapeutencheck(request.question)
        return {
            "status": "success",
            "question": request.question,
            "answer": resultado["answer"]
        }
    except Exception as e:
        err = str(e)
        if "429" in err or "RESOURCE_EXHAUSTED" in err:
            print(f"[QUOTA] Rate limit alcanzado: {err[:200]}")
            raise HTTPException(
                status_code=429,
                detail="API quota exceeded. Please try again in a few minutes."
            )
        print(f"[ERROR] {err}")
        raise HTTPException(status_code=500, detail="Internal server error.")