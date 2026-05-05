from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from rag_pipeline_gemini import query_therapeutencheck

app = FastAPI(title="Sanoanimal RAG API", version="1.0")

# --- Configuración de CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # En producción se restringe a la URL real, para desarrollo local se permite todo ("*")
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    question: str

@app.post("/ask")
def ask_rag(request: QueryRequest):
    print(f"Nueva petición recibida: {request.question}")
    
    resultado = query_therapeutencheck(request.question)
    
    return {
        "status": "success",
        "question": request.question,
        "answer": resultado["answer"]
    }