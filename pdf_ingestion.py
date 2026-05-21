import os
import hashlib
import time
import psycopg2
import fitz  # PyMuPDF
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────

PDF_FOLDER = os.path.join(os.path.dirname(__file__), "pdfs")

DB_CONFIG = {
    "dbname":   os.getenv("DB_NAME", "sanoanimal"),
    "user":     os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "password"),
    "host":     os.getenv("DB_HOST", "localhost"),
    "port":     os.getenv("DB_PORT", "5432"),
}

gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

MIN_CHUNK_CHARS  = 100    # skip pages/chunks with almost no text
MAX_CHUNK_CHARS  = 3000   # split long pages into smaller chunks
CHUNK_OVERLAP    = 200    # overlap between chunks to preserve context
SLEEP_BETWEEN    = 0.8    # seconds between embedding calls (~75 RPM)


# ── Helpers ───────────────────────────────────────────────────────────────────

def md5(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def split_text(text: str, max_chars: int = MAX_CHUNK_CHARS, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split long text into overlapping chunks."""
    if len(text) <= max_chars:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = start + max_chars
        chunk = text[start:end]
        # Try to cut at a sentence boundary
        last_period = chunk.rfind(". ")
        if last_period > max_chars // 2:
            chunk = chunk[:last_period + 1]
        chunks.append(chunk.strip())
        start += len(chunk) - overlap
    return [c for c in chunks if len(c) >= MIN_CHUNK_CHARS]


def embed_text(text: str) -> list[float]:
    for attempt in range(5):
        try:
            response = gemini_client.models.embed_content(
                model="gemini-embedding-001",
                contents=text,
                config=types.EmbedContentConfig(
                    output_dimensionality=768,
                    task_type="RETRIEVAL_DOCUMENT"
                )
            )
            return response.embeddings[0].values
        except Exception as e:
            if "429" in str(e) and attempt < 4:
                wait = 15 * (attempt + 1)
                print(f"\n    Rate limit, waiting {wait}s...")
                time.sleep(wait)
            else:
                raise


# ── Core processing ───────────────────────────────────────────────────────────

def process_pdf(filepath: str, conn) -> tuple[int, int, int]:
    """Process a single PDF. Returns (new, skipped_duplicate, skipped_short)."""
    filename = os.path.basename(filepath)
    print(f"\n{'='*60}")
    print(f"Processing: {filename}")

    doc = fitz.open(filepath)
    cur = conn.cursor()
    new_count = dup_count = short_count = 0

    for page_num in range(len(doc)):
        page = doc[page_num]
        raw_text = page.get_text("text").strip()

        if len(raw_text) < MIN_CHUNK_CHARS:
            short_count += 1
            continue

        chunks = split_text(raw_text)

        for chunk_idx, chunk_text in enumerate(chunks):
            label = f"page {page_num + 1}" + (f" chunk {chunk_idx + 1}" if len(chunks) > 1 else "")
            content_hash = md5(filename + str(page_num) + str(chunk_idx) + chunk_text)

            # Check for duplicate
            cur.execute(
                "SELECT id FROM therapeutencheck.pdf_dokumente WHERE content_hash = %s",
                (content_hash,)
            )
            if cur.fetchone():
                print(f"  [{label}] → already ingested, skipping")
                dup_count += 1
                continue

            # Embed and insert
            print(f"  [{label}] {len(chunk_text)} chars → embedding...", end="", flush=True)
            vector = embed_text(chunk_text)

            cur.execute("""
                INSERT INTO therapeutencheck.pdf_dokumente
                    (filename, page_num, chunk_text, embedding, content_hash)
                VALUES (%s, %s, %s, %s::vector, %s)
            """, (filename, page_num + 1, chunk_text, vector, content_hash))
            conn.commit()
            print(" ✓")
            new_count += 1
            time.sleep(SLEEP_BETWEEN)

    doc.close()
    cur.close()
    print(f"  Result: {new_count} new · {dup_count} duplicate · {short_count} short pages skipped")
    return new_count, dup_count, short_count


def main():
    if not os.path.exists(PDF_FOLDER):
        os.makedirs(PDF_FOLDER)
        print(f"Created folder: {PDF_FOLDER}")
        print("Place your PDF files in the 'pdfs/' folder and run again.")
        return

    pdf_files = [f for f in os.listdir(PDF_FOLDER) if f.lower().endswith(".pdf")]

    if not pdf_files:
        print(f"No PDF files found in {PDF_FOLDER}")
        print("Place your PDF files there and run again.")
        return

    print(f"Found {len(pdf_files)} PDF file(s): {', '.join(pdf_files)}")

    conn = psycopg2.connect(**DB_CONFIG)
    try:
        total_new = total_dup = total_short = 0
        for filename in pdf_files:
            filepath = os.path.join(PDF_FOLDER, filename)
            n, d, s = process_pdf(filepath, conn)
            total_new += n
            total_dup += d
            total_short += s

        print(f"\n{'='*60}")
        print(f"TOTAL: {total_new} new chunks · {total_dup} duplicates · {total_short} short pages skipped")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
