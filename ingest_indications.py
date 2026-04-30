import os
import pandas as pd
import psycopg2
from psycopg2 import sql
from psycopg2.extras import execute_values
from dotenv import load_dotenv

load_dotenv()

def ingest_indications():
    file_path = "data/indikationen_therapie_matrix.xlsx"
    sheet_name = "Indikationen → Therapie"
    
    try:
        print(f"--- Leyendo Excel: {sheet_name} ---")
        df = pd.read_excel(file_path, sheet_name=sheet_name)
        
        mapping = {
            "Indikation / Symptomkomplex": "indikation",
            "Organsystem": "organsystem",
            "Schweregrad": "schweregrad",
            "First-Line Therapie": "first_line_therapie",
            "First-Line Wirkstoff (Dosierung)": "first_line_wirkstoff",
            "Second-Line / Reserve": "second_line_reserve",
            "Begleittherapie / Supportiv": "begleittherapie",
            "OKAPI-Produkte / Phytotherapie": "okapi_produkte",
            "Kontraindizierte Wirkstoffe": "kontraindizierte_wirkstoffe",
            "Monitoring / Kontrolle": "monitoring",
            "Prognose": "prognose",
            "Evidenzbasis": "evidenzbasis"
        }
        
        df_db = df.rename(columns=mapping)
        df_db = df_db[list(mapping.values())]
        df_db = df_db.where(pd.notnull(df_db), None)

        conn = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            database=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD")
        )
        cur = conn.cursor()

        # Verificar search_path activo
        cur.execute("SELECT current_database();")
        print(f"DB activa en Python: {cur.fetchone()[0]}")

        cur.execute("""
            SELECT attname FROM pg_attribute
            JOIN pg_class ON attrelid = pg_class.oid
            JOIN pg_namespace ON relnamespace = pg_namespace.oid
            WHERE nspname = 'therapeutencheck'
            AND relname = 'indikationen'
            AND attnum > 0 AND NOT attisdropped
            ORDER BY attnum
        """)
        print("Columnas reales:", [r[0] for r in cur.fetchall()])
        

        for idx, row in df_db.iterrows():
            columns = row.index.tolist()
            values = row.values.tolist()

            columns.append("quellen")
            raw_source = df.loc[idx, "Quelle"] if "Quelle" in df.columns else None
            values.append([raw_source] if raw_source else None)

            insert_query = sql.SQL(
                "INSERT INTO therapeutencheck.indikationen ({cols}) VALUES ({vals})"
            ).format(
                cols=sql.SQL(", ").join(map(sql.Identifier, columns)),
                vals=sql.SQL(", ").join([sql.Placeholder()] * len(columns))
            )

            # Descomentar para debug si vuelve a fallar:
            print(cur.mogrify(insert_query, values).decode())

            cur.execute(insert_query, values)

        conn.commit()
        cur.close()
        conn.close()
        print("Datos cargados exitosamente.")

    except Exception as e:
        print(f"Error: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()

if __name__ == "__main__":
    ingest_indications()