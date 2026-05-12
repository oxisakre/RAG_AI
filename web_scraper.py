import os
import time
import hashlib
import requests
import psycopg2
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

DOMAINS = [
    {"base_url": "https://www.sanoanimal.de",   "quelle_typ": "Sanoanimal_Web"},
    {"base_url": "https://www.okapi-online.de", "quelle_typ": "OKAPI_Web"},
]

DB_CONFIG = {
    "dbname":   os.getenv("DB_NAME", "sanoanimal"),
    "user":     os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "password"),
    "host":     os.getenv("DB_HOST", "localhost"),
    "port":     os.getenv("DB_PORT", "5432"),
}

gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SanoAnimalBot/1.0)"}

SKIP_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg",
                   ".mp4", ".mp3", ".zip", ".doc", ".docx", ".webp"}
SKIP_PATTERNS   = ["/cart", "/checkout", "/account", "/login",
                   "/wp-admin", "/wp-json", "/feed", "?add-to-cart"]
MIN_TEXT_LENGTH = 150   # chars — páginas más cortas son nav/404/etc
MAX_TEXT_CHARS  = 8000  # truncate antes de embedear (límite de tokens Gemini)
SLEEP_BETWEEN_EMBEDS = 0.7  # ~85 RPM, free tier es 100 RPM


# ── Utilidades ───────────────────────────────────────────────────────────────

def md5(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def is_valid_url(url: str, domain: str) -> bool:
    parsed = urlparse(url)
    if parsed.netloc != domain:
        return False
    if any(url.endswith(ext) for ext in SKIP_EXTENSIONS):
        return False
    if any(pat in url for pat in SKIP_PATTERNS):
        return False
    return True


# ── Descubrimiento de URLs ────────────────────────────────────────────────────

def fetch_sitemap_urls(sitemap_url: str) -> list[str]:
    """Descarga un sitemap.xml y devuelve todas las <loc>."""
    try:
        r = requests.get(sitemap_url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return []
        soup = BeautifulSoup(r.content, "lxml-xml")
        # Sitemap index → recursivo
        nested = [sm.find("loc").text.strip()
                  for sm in soup.find_all("sitemap") if sm.find("loc")]
        if nested:
            urls = []
            for sub in nested:
                urls.extend(fetch_sitemap_urls(sub))
            return urls
        # Sitemap regular
        return [loc.text.strip() for loc in soup.find_all("loc")]
    except Exception as e:
        print(f"    Error fetching sitemap {sitemap_url}: {e}")
        return []


def discover_urls(base_url: str) -> list[str]:
    """Intenta sitemap.xml; si no hay, crawlea recursivamente."""
    domain = urlparse(base_url).netloc

    for candidate in [f"{base_url}/sitemap.xml", f"{base_url}/sitemap_index.xml"]:
        urls = fetch_sitemap_urls(candidate)
        if urls:
            valid = [u for u in urls if is_valid_url(u, domain)]
            print(f"  Sitemap: {candidate} → {len(urls)} URLs totales, {len(valid)} válidas")
            return valid

    # Fallback: crawler recursivo
    print("  Sin sitemap, usando crawler recursivo (máx. 500 páginas)...")
    return crawl_recursive(base_url, domain)


def crawl_recursive(base_url: str, domain: str, max_pages: int = 500) -> list[str]:
    visited, queue, found = set(), [base_url], []
    while queue and len(found) < max_pages:
        url = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)
        if not is_valid_url(url, domain):
            continue
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            if r.status_code != 200 or "text/html" not in r.headers.get("Content-Type", ""):
                continue
            found.append(url)
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.find_all("a", href=True):
                full = urljoin(url, a["href"]).split("#")[0].split("?")[0]
                if full not in visited:
                    queue.append(full)
            time.sleep(0.5)
        except Exception:
            pass
    print(f"  Crawler: {len(found)} páginas encontradas")
    return found


# ── Extracción de texto ───────────────────────────────────────────────────────

def extract_text(html: str, url: str) -> tuple[str, str]:
    """Devuelve (titulo, texto_limpio) de una página HTML."""
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "nav", "footer", "header",
                     "aside", "form", "iframe", "noscript"]):
        tag.decompose()

    title = soup.title.string.strip() if soup.title else url

    main = (
        soup.find("main") or
        soup.find("article") or
        soup.find(id="content") or
        soup.find(class_="content") or
        soup.find(class_="entry-content") or
        soup.body
    )
    raw = main.get_text(separator="\n", strip=True) if main else ""

    lines = [l.strip() for l in raw.splitlines() if len(l.strip()) > 30]
    return title, "\n".join(lines)


# ── Embedding ─────────────────────────────────────────────────────────────────

def embed_text(text: str) -> list[float]:
    truncated = text[:MAX_TEXT_CHARS]
    for attempt in range(5):
        try:
            response = gemini_client.models.embed_content(
                model="gemini-embedding-001",
                contents=truncated,
                config=types.EmbedContentConfig(
                    output_dimensionality=768,
                    task_type="RETRIEVAL_DOCUMENT"
                )
            )
            return response.embeddings[0].values
        except Exception as e:
            if "429" in str(e) and attempt < 4:
                wait = 15 * (attempt + 1)
                print(f"\n    Rate limit, esperando {wait}s...", end="")
                time.sleep(wait)
            else:
                raise


# ── Procesamiento por dominio ─────────────────────────────────────────────────

def process_domain(base_url: str, quelle_typ: str, conn) -> tuple[int, int, int]:
    """Procesa todas las páginas de un dominio. Devuelve (nuevas, actualizadas, sin_cambios)."""
    print(f"\n{'='*60}")
    print(f"Dominio: {base_url}")

    urls = discover_urls(base_url)
    if not urls:
        print("  Sin URLs encontradas.")
        return 0, 0, 0

    cur = conn.cursor()
    new_count = updated_count = skipped_count = 0

    for i, url in enumerate(urls, 1):
        print(f"  [{i:>3}/{len(urls)}] {url[:75]}", end="", flush=True)

        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code != 200:
                print(f" → HTTP {r.status_code}")
                continue
            if "text/html" not in r.headers.get("Content-Type", ""):
                print(" → no HTML")
                continue

            title, text = extract_text(r.text, url)
            if len(text) < MIN_TEXT_LENGTH:
                print(f" → muy corta ({len(text)} chars)")
                continue

            new_hash = md5(text)

            cur.execute(
                "SELECT id, content_hash FROM therapeutencheck.kuratierte_quellen WHERE url = %s",
                (url,)
            )
            existing = cur.fetchone()

            if existing:
                row_id, stored_hash = existing
                if stored_hash == new_hash:
                    print(" → sin cambios")
                    skipped_count += 1
                    continue
                # Contenido cambió → actualizar
                vector = embed_text(text)
                cur.execute("""
                    UPDATE therapeutencheck.kuratierte_quellen
                    SET titel = %s, inhalt_text = %s, content_hash = %s,
                        embedding = %s::vector, letzte_aktualisierung = NOW()
                    WHERE id = %s
                """, (title[:500], text, new_hash, vector, row_id))
                conn.commit()
                print(f" → actualizada ({len(text)} chars)")
                updated_count += 1
            else:
                # Nueva URL
                vector = embed_text(text)
                cur.execute("""
                    INSERT INTO therapeutencheck.kuratierte_quellen
                        (quelle_typ, titel, url, inhalt_text, content_hash,
                         embedding, letzte_aktualisierung, scraping_aktiv, vertrauensstufe)
                    VALUES (%s, %s, %s, %s, %s, %s::vector, NOW(), TRUE, 'Standard')
                """, (quelle_typ, title[:500], url, text, new_hash, vector))
                conn.commit()
                print(f" → nueva ({len(text)} chars)")
                new_count += 1

            time.sleep(SLEEP_BETWEEN_EMBEDS)

        except Exception as e:
            print(f" → ERROR: {e}")
            conn.rollback()
            time.sleep(2)

    cur.close()
    print(f"\n  Resultado: {new_count} nuevas · {updated_count} actualizadas · {skipped_count} sin cambios")
    return new_count, updated_count, skipped_count


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        total_new = total_updated = total_skipped = 0
        for domain in DOMAINS:
            n, u, s = process_domain(domain["base_url"], domain["quelle_typ"], conn)
            total_new += n
            total_updated += u
            total_skipped += s

        print(f"\n{'='*60}")
        print(f"TOTAL FINAL: {total_new} nuevas · {total_updated} actualizadas · {total_skipped} sin cambios")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
