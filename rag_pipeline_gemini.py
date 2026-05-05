import psycopg2
from google import genai
from google.genai import types
import os
from dotenv import load_dotenv

load_dotenv()

# Inicialización de cliente único para embedding e inferencia
gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

DB_CONFIG = {
    "dbname": os.getenv("DB_NAME", "sanoanimal"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "password"),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432")
}

def query_therapeutencheck(question: str) -> dict:
    # 1. Vectorización de la consulta
    response_emb = gemini_client.models.embed_content(
        model="gemini-embedding-001",
        contents=question,
        config=types.EmbedContentConfig(
            output_dimensionality=768,
            task_type="RETRIEVAL_QUERY"
        )
    )
    question_embedding = response_emb.embeddings[0].values

    # 2. Búsqueda Semántica en PostgreSQL
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    cur.execute("""
        SELECT id, indikation, first_line_therapie, first_line_wirkstoff, okapi_produkte, 
               1 - (embedding <=> %s::vector) AS similarity
        FROM therapeutencheck.indikationen
        WHERE embedding IS NOT NULL
        ORDER BY similarity DESC
        LIMIT 3
    """, (question_embedding,))
    
    results = cur.fetchall()
    
    # 3. Ensamblaje del Contexto
    context_parts = []
    for row in results:
        context_parts.append(
            f"[Source: indikationen | Similitud: {row[5]:.2f}] Indikation: {row[1]} | "
            f"Therapie: {row[2]} | Wirkstoff: {row[3]} | OKAPI: {row[4]}"
        )
    
    context_text = "\n---\n".join(context_parts)
    
    # 4. Generación de respuesta con Gemini (Reemplazo de Claude)
    system_instruction = """You are the Sanoanimal Therapeutencheck — a veterinary pharmacology assistant specifically for equine medicine. You answer questions from horse therapists about medications, dosages, drug interactions, poisonous plants, and treatment protocols.

CRITICAL RULES:
1. ALWAYS base your answer on the retrieved context provided below. If the context doesn't contain relevant information, say so — do NOT make up information.
2. Structure every answer in TWO clearly separated sections:
   a) "Sanoanimal Praxis-Einordnung"
   b) "Fakten — Wissenschaftliche Literatur"
3. Answer in the same language as the question.
4. Always cite the source table."""

    prompt = f"""Question from therapist: {question}

--- RETRIEVED CONTEXT FROM DATABASE ---
{context_text}"""

    response_gen = gemini_client.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.2
        )
    )
    
    cur.close()
    conn.close()
    
    return {
        "answer": response_gen.text,
        "context": results
    }

if __name__ == "__main__":
    test_question = "What treatment options do I have for a horse with severe colic?"
    print("Ejecutando pipeline RAG con Gemini API...")
    result = query_therapeutencheck(test_question)
    print("\n--- Answer ---\n")
    print(result["answer"])