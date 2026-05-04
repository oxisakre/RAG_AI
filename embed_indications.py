import psycopg2
import google.generativeai as genai
import os

# Configurar API Key. Asignar la variable de entorno antes de la ejecución.
# Linux/Mac: export GEMINI_API_KEY="tu_clave"
# Windows: set GEMINI_API_KEY="tu_clave"
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

# Ajustar credenciales de acceso a Docker/PostgreSQL
DB_CONFIG = {
    "dbname": "sanoanimal",
    "user": "postgres", 
    "password": "password", 
    "host": "localhost",
    "port": "5432"
}

def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    # Seleccionar registros que poseen texto generado pero carecen de vector
    cur.execute("""
        SELECT id, text_for_embedding 
        FROM therapeutencheck.indikationen 
        WHERE text_for_embedding IS NOT NULL AND embedding IS NULL
    """)
    records = cur.fetchall()

    for record_id, text in records:
        # Generar vector con el modelo de 768 dimensiones
        response = genai.embed_content(
            model="models/text-embedding-004",
            content=text,
            task_type="retrieval_document"
        )
        embedding_vector = response['embedding']

        # Actualizar registro con el vector correspondiente
        cur.execute(
            "UPDATE therapeutencheck.indikationen SET embedding = %s::vector WHERE id = %s",
            (embedding_vector, record_id)
        )

    conn.commit()
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()