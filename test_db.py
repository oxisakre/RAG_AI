import os
import psycopg2
from dotenv import load_dotenv

# 1. Cargar las variables secretas del archivo .env
load_dotenv()

def test_connection():
    print("Intentando conectar a la base de datos 'sanoanimal'...\n")
    try:
        # 2. Conectarse a PostgreSQL usando las credenciales del .env
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            database=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD")
        )
        
        # 3. Crear un cursor (nuestro mensajero para ejecutar SQL)
        cur = conn.cursor()
        
        # 4. Preguntarle a la base de datos qué tablas existen en el esquema de Carsten
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'therapeutencheck'
            ORDER BY table_name;
        """)
        
        tablas = cur.fetchall()
        
        print("✅ ¡Conexión exitosa a PostgreSQL!")
        print(f"Se encontraron {len(tablas)} tablas en el esquema 'therapeutencheck':\n")
        
        for tabla in tablas:
            print(f" 📄 {tabla[0]}")
            
        # 5. Ser prolijos y cerrar la puerta al salir
        cur.close()
        conn.close()
        print("\nConexión cerrada correctamente.")

    except Exception as e:
        print("❌ Error al intentar conectar:")
        print(e)

if __name__ == "__main__":
    test_connection()