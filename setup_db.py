import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

print("Preparando la inyección del esquema...")

try:
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )
    cur = conn.cursor()

    # Buscamos el archivo, atajando la maña de Windows con los .txt
    archivo_sql = 'therapeutencheck_schema.sql'
    if not os.path.exists(archivo_sql):
        if os.path.exists(archivo_sql + '.txt'):
            archivo_sql += '.txt'
        else:
            raise FileNotFoundError("No encuentro el archivo SQL en esta carpeta.")

    # Leemos el archivo y lo ejecutamos todo de una
    with open(archivo_sql, 'r', encoding='utf-8') as f:
        esquema = f.read()

    print(f"Leyendo archivo '{archivo_sql}' y creando tablas...")
    cur.execute(esquema)
    conn.commit()  # Guardamos los cambios definitivamente

    cur.close()
    conn.close()
    print("✅ ¡Éxito! El esquema médico se inyectó correctamente en PostgreSQL.")

except Exception as e:
    print("❌ Error:")
    print(e)