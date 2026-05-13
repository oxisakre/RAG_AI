import psycopg2
from google import genai
from google.genai import types
import os
import time
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

DB_CONFIG = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT")
}

TABLES = [
    "therapeutencheck.wirkstoffe",
    "therapeutencheck.giftpflanzen",
    "therapeutencheck.wechselwirkungen",
]

def embed_table(cur, conn, table):
    cur.execute(f"""
        SELECT id, text_for_embedding 
        FROM {table}
        WHERE text_for_embedding IS NOT NULL AND embedding IS NULL
    """)
    rows = cur.fetchall()
    print(f"{table}: {len(rows)} filas a vectorizar")

    for row_id, text in rows:
        for attempt in range(5):
            try:
                response = client.models.embed_content(
                    model="gemini-embedding-001",
                    contents=text,
                    config=types.EmbedContentConfig(
                        output_dimensionality=768,
                        task_type="RETRIEVAL_DOCUMENT"
                    )
                )
                break
            except Exception as e:
                if "429" in str(e) and attempt < 4:
                    wait = 15 * (attempt + 1)
                    print(f"  Rate limit, esperando {wait}s...")
                    time.sleep(wait)
                else:
                    raise
        vector = response.embeddings[0].values
        cur.execute(
            f"UPDATE {table} SET embedding = %s::vector WHERE id = %s",
            (vector, row_id)
        )
        conn.commit()
        print(f"  Vectorizado: {row_id}")
        time.sleep(1.2)

def embed_medikamente(cur, conn):
    """Medikamente necesita JOIN con wirkstoffe para obtener el nombre del wirkstoff."""
    cur.execute("""
        SELECT m.id,
            'Medication: ' || m.handelsname ||
            ' | Active ingredient: ' || w.wirkstoff_inn ||
            ' | Class: ' || w.wirkstoffklasse ||
            ' | Approval: ' || m.zulassungsstatus ||
            ' | Dosage (horse): ' || COALESCE(m.dosierung_pferd, '') ||
            ' | Route: ' || COALESCE(m.applikationsweg, '') ||
            ' | Indication: ' || COALESCE(m.anwendung, '') ||
            ' | Effects: ' || COALESCE(m.wirkung, '') ||
            ' | Side effects: ' || COALESCE(m.nebenwirkungen, '') ||
            ' | Prescription: ' || COALESCE(m.rezeptpflicht, '') ||
            ' | FEI doping: ' || COALESCE(m.fei_dopingstatus, '') ||
            ' | Withdrawal: ' || COALESCE(m.wartezeit, '') AS text_to_embed
        FROM therapeutencheck.medikamente m
        JOIN therapeutencheck.wirkstoffe w ON w.id = m.wirkstoff_id
        WHERE m.embedding IS NULL
    """)
    rows = cur.fetchall()
    print(f"therapeutencheck.medikamente: {len(rows)} filas a vectorizar")

    for row_id, text in rows:
        for attempt in range(5):
            try:
                response = client.models.embed_content(
                    model="gemini-embedding-001",
                    contents=text,
                    config=types.EmbedContentConfig(
                        output_dimensionality=768,
                        task_type="RETRIEVAL_DOCUMENT"
                    )
                )
                break
            except Exception as e:
                if "429" in str(e) and attempt < 4:
                    wait = 15 * (attempt + 1)
                    print(f"  Rate limit, esperando {wait}s...")
                    time.sleep(wait)
                else:
                    raise
        vector = response.embeddings[0].values
        cur.execute(
            "UPDATE therapeutencheck.medikamente SET embedding = %s::vector WHERE id = %s",
            (vector, row_id)
        )
        conn.commit()
        print(f"  Vectorizado: {row_id}")
        time.sleep(1.2)
    print("✓ therapeutencheck.medikamente completada")


def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    for table in TABLES:
        embed_table(cur, conn, table)
        print(f"✓ {table} completada")

    embed_medikamente(cur, conn)

    cur.close()
    conn.close()
    print("\n✓ Todas las tablas vectorizadas.")

if __name__ == "__main__":
    main()