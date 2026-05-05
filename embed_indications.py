import psycopg2
from google import genai
from google.genai import types
import os
from dotenv import load_dotenv

load_dotenv()

# Inicializamos el cliente (toma la API key de las variables de entorno)
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

DB_CONFIG = {
    "dbname": os.getenv("DB_NAME", "sanoanimal"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "password"),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432")
}

def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    # Buscamos las filas que tienen texto pero no tienen vector
    cur.execute("""
        SELECT id, text_for_embedding 
        FROM therapeutencheck.indikationen 
        WHERE text_for_embedding IS NOT NULL AND embedding IS NULL
    """)
    records = cur.fetchall()
    print(f"Filas a vectorizar: {len(records)}")

    for record_id, text in records:
        # Usamos el modelo nuevo y le forzamos 768 dimensiones
        response = client.models.embed_content(
            model="gemini-embedding-001",
            contents=text,
            config=types.EmbedContentConfig(
                output_dimensionality=768,
                task_type="RETRIEVAL_DOCUMENT"
            )
        )
        
        # Extraemos el vector
        embedding_vector = response.embeddings[0].values

        # Lo guardamos en PostgreSQL
        cur.execute(
            "UPDATE therapeutencheck.indikationen SET embedding = %s::vector WHERE id = %s",
            (embedding_vector, record_id)
        )
        print(f"Vectorizado: {record_id}")

    conn.commit()
    cur.close()
    conn.close()
    print("✓ Embeddings cargados con éxito.")

if __name__ == "__main__":
    main()