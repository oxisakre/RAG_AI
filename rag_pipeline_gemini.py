import psycopg2
from google import genai
from google.genai import types
import os
import time
from dotenv import load_dotenv

load_dotenv()

gemini_client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY"),
    http_options=types.HttpOptions(timeout=120000)  # 120 segundos (en ms) máximo por request
)

GENERATION_MODEL = "gemini-2.5-flash-lite"
DAILY_LIMIT = 10000  # billing activo — sin límite práctico

DB_CONFIG = {
    "dbname": os.getenv("DB_NAME", "sanoanimal"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "password"),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432")
}

SYSTEM_INSTRUCTION = """You are the Sanoanimal Therapeutencheck — a specialized veterinary pharmacology assistant for equine medicine.

LANGUAGE — ABSOLUTE RULE (applies to everything you write):
Always respond in English. Always. Even if the retrieved context is in German, French, or any other language — your answer must be in English. Translate any German context into English before using it in your response. Never write a single word in German.

CRITICAL RULE 1 — OUT OF SCOPE (highest priority):
If the question is outside veterinary/equine medicine, respond with EXACTLY and ONLY this single sentence:
"This question is outside the scope of Sanoanimal Therapeutencheck."
Do NOT add any other text. Do NOT use headers. Do NOT use the two-section format.

CRITICAL RULE 2 — ZERO GUESSING (strict factuality):
Use ONLY the provided context. If the user asks about a specific drug or topic and that EXACT name is NOT in the context, state exactly:
"The available database does not contain specific information on this topic."
Do NOT assume typos. Do NOT provide information about similar-sounding drugs. Do NOT extrapolate.

RESPONSE FORMAT — for valid in-scope questions only:
Structure the answer in exactly TWO sections using these exact headers:

**SANOANIMAL PRAXIS-EINORDNUNG**
- Maximum 3 concise bullet points
- Focus on practical clinical relevance for the therapist
- Highlight warnings, contraindications, or monitoring needs
- Do NOT repeat raw data already shown in the Fakten section
- If the exact drug/topic is not found in the context, write ONLY: "No specific data available for this query." Do not reference similar drugs.

**FAKTEN — WISSENSCHAFTLICHE LITERATUR**
- Specific data only: dosages, drug classes, mechanisms, interactions
- Cite only information present in the retrieved context
- If the context lacks specific data, state exactly: "The available database does not contain specific information on this topic."
- Do NOT invent, extrapolate, or infer beyond the retrieved context

CITATIONS: At the end of the Fakten section, add a "Sources:" line listing only the sources you actually used.
- For database tables: use the table name (e.g., wirkstoffe, wechselwirkungen, indikationen).
- For web sources: each web_content entry includes a URL in the format "URL: https://...". Extract and list those exact URLs (e.g., "https://www.okapi-online.de/product.html"). Do NOT write "web_content" — write the actual URL.
- Do not cite sources inline within the text — only in the Sources line at the end.

FINAL REMINDER: Your entire response must be in English. Do not use German even if the context is in German."""


def build_context(rows):
    parts = []
    for source, content, similarity in rows:
        parts.append(f"[Source: {source} | Similarity: {similarity:.2f}]\n{content}")
    return "\n---\n".join(parts)


def query_therapeutencheck(question: str) -> dict:
    # 1. Embed the question
    response_emb = gemini_client.models.embed_content(
        model="gemini-embedding-001",
        contents=question,
        config=types.EmbedContentConfig(
            output_dimensionality=768,
            task_type="RETRIEVAL_QUERY"
        )
    )
    question_embedding = response_emb.embeddings[0].values

    # 2. Search all tables with UNION ALL
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT source, content, similarity FROM (

                SELECT
                    'indikationen' AS source,
                    'Indication: ' || indikation ||
                    ' | Organ system: ' || organsystem ||
                    ' | First-line therapy: ' || first_line_therapie ||
                    ' | First-line substance: ' || first_line_wirkstoff ||
                    COALESCE(' | OKAPI products: ' || okapi_produkte, '') ||
                    COALESCE(' | Contraindicated: ' || kontraindizierte_wirkstoffe, '') ||
                    ' | Prognosis: ' || prognose ||
                    COALESCE(' | Scientific sources: ' || array_to_string(quellen, ', '), '') AS content,
                    1 - (embedding <=> %s::vector) AS similarity
                FROM therapeutencheck.indikationen
                WHERE embedding IS NOT NULL

                UNION ALL

                SELECT
                    'wirkstoffe' AS source,
                    'Substance: ' || wirkstoff_inn ||
                    ' | Class: ' || wirkstoffklasse ||
                    ' | Category: ' || therapeutische_kategorie ||
                    ' | Mechanism: ' || wirkmechanismus ||
                    ' | Equine specifics: ' || pferd_besonderheiten ||
                    COALESCE(' | Half-life: ' || hwz_plasma, '') ||
                    COALESCE(' | Metabolism: ' || metabolismus, '') ||
                    COALESCE(' | Scientific sources: ' || array_to_string(quellen, ', '), '') AS content,
                    1 - (embedding <=> %s::vector) AS similarity
                FROM therapeutencheck.wirkstoffe
                WHERE embedding IS NOT NULL

                UNION ALL

                SELECT
                    'giftpflanzen' AS source,
                    'Plant: ' || deutscher_name ||
                    ' (' || botanischer_name || ')' ||
                    ' | Toxicity: ' || giftigkeitsstufe ||
                    ' | Toxin: ' || toxin_wirkstoff ||
                    ' | Symptoms in horse: ' || symptome_pferd ||
                    ' | Therapy: ' || therapie ||
                    ' | Toxic in hay: ' || giftig_im_heu ||
                    ' | Prognosis: ' || prognose ||
                    COALESCE(' | Scientific sources: ' || array_to_string(quellen, ', '), '') AS content,
                    1 - (embedding <=> %s::vector) AS similarity
                FROM therapeutencheck.giftpflanzen
                WHERE embedding IS NOT NULL

                UNION ALL

                SELECT
                    'wechselwirkungen' AS source,
                    'Interaction: ' || partner_a_name || ' + ' || partner_b_name ||
                    ' | Severity: ' || schweregrad ||
                    ' | Mechanism: ' || mechanismus ||
                    ' | Clinical consequence: ' || klinische_konsequenz ||
                    ' | Recommendation: ' || empfehlung ||
                    COALESCE(' | Scientific sources: ' || array_to_string(quellen, ', '), '') AS content,
                    1 - (embedding <=> %s::vector) AS similarity
                FROM therapeutencheck.wechselwirkungen
                WHERE embedding IS NOT NULL

                UNION ALL

                SELECT
                    'medikamente' AS source,
                    'Medication: ' || m.handelsname ||
                    ' | Active ingredient: ' || w.wirkstoff_inn ||
                    ' | Class: ' || w.wirkstoffklasse ||
                    ' | Approval: ' || m.zulassungsstatus ||
                    ' | Dosage (horse): ' || COALESCE(m.dosierung_pferd, '') ||
                    ' | Route: ' || COALESCE(m.applikationsweg, '') ||
                    ' | Indication: ' || COALESCE(m.anwendung, '') ||
                    ' | Side effects: ' || COALESCE(m.nebenwirkungen, '') ||
                    ' | Prescription: ' || COALESCE(m.rezeptpflicht, '') ||
                    ' | FEI doping: ' || COALESCE(m.fei_dopingstatus, '') ||
                    ' | Withdrawal: ' || COALESCE(m.wartezeit, '') AS content,
                    1 - (m.embedding <=> %s::vector) AS similarity
                FROM therapeutencheck.medikamente m
                JOIN therapeutencheck.wirkstoffe w ON w.id = m.wirkstoff_id
                WHERE m.embedding IS NOT NULL

                UNION ALL

                SELECT
                    'web_content' AS source,
                    'Web source: ' || titel ||
                    ' | URL: ' || url ||
                    ' | ' || LEFT(inhalt_text, 2000) AS content,
                    1 - (embedding <=> %s::vector) AS similarity
                FROM therapeutencheck.kuratierte_quellen
                WHERE embedding IS NOT NULL
                  AND scraping_aktiv = TRUE

            ) combined
            WHERE similarity > 0.40
            ORDER BY similarity DESC
            LIMIT 7
        """, (question_embedding, question_embedding, question_embedding, question_embedding, question_embedding, question_embedding))

        results = cur.fetchall()

        # 3. Check contraindications deterministically if a drug name is mentioned
        cur.execute("""
            SELECT wirkstoff_name, erkrankung_zustand, schwere, begruendung, konsequenz, alternative
            FROM therapeutencheck.kontraindikationen
        """)
        kontra_rows = cur.fetchall()

        cur.close()
    finally:
        conn.close()

    # 4. Assemble context
    context_text = build_context(results)

    # Add any contraindication matches as deterministic safety layer
    question_lower = question.lower()
    matched_kontra = [
        row for row in kontra_rows
        if row[0].lower() in question_lower or row[1].lower() in question_lower
    ]
    if matched_kontra:
        kontra_parts = []
        for row in matched_kontra:
            kontra_parts.append(
                f"[Source: kontraindikationen | DETERMINISTIC SAFETY CHECK]\n"
                f"Substance: {row[0]} | Condition: {row[1]} | Severity: {row[2]}\n"
                f"Reason: {row[3]} | Consequence: {row[4]}"
                + (f" | Alternative: {row[5]}" if row[5] else "")
            )
        context_text = "\n---\n".join(kontra_parts) + "\n---\n" + context_text

    # 5. Generate answer
    prompt = f"""Question from therapist: {question}

--- RETRIEVED CONTEXT FROM DATABASE ---
{context_text}"""

    for attempt in range(4):
        try:
            response_gen = gemini_client.models.generate_content(
                model=GENERATION_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    temperature=0.2
                )
            )
            break
        except Exception as e:
            err_str = str(e)
            if "503" in err_str or "UNAVAILABLE" in err_str or "timed out" in err_str.lower() or "timeout" in err_str.lower():
                if attempt < 3:
                    wait = 4 * (attempt + 1)
                    print(f"  Modelo no responde, reintentando en {wait}s... (intento {attempt+1}/3)")
                    time.sleep(wait)
                else:
                    raise
            else:
                raise

    return {
        "answer": response_gen.text,
        "context": results,
        "model": GENERATION_MODEL,
        "daily_limit": DAILY_LIMIT
    }


if __name__ == "__main__":
    questions = [
        "What treatment options do I have for a horse with acute colic?",
        "Can I give Magnesium together with Doxycycline?",
        "Is Dexamethasone safe for a horse with Cushing's disease?",
        "Which plants are dangerous in hay?",
    ]
    for q in questions:
        print(f"\n{'='*60}\nQ: {q}\n{'='*60}")
        result = query_therapeutencheck(q)
        print(result["answer"])
