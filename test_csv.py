import pandas as pd

# Le indicamos a Python dónde está el archivo dentro de tu carpeta 'datos'
ruta_archivo = "datos/wirkstoffe_equiden_v2.xlsx - Wirkstoffe Equiden.csv"

try:
    print(f"Intentando abrir: {ruta_archivo}...\n")
    
    # pandas lee el csv
    df = pd.read_csv(ruta_archivo)
    
    print("✅ ¡Archivo leído con éxito!")
    print(f"Se encontraron {len(df)} medicamentos.\n")
    print("Estas son las columnas que tiene el archivo:")
    
    # Imprimimos los nombres de las columnas para verificar
    for columna in df.columns:
        print(f" 📄 {columna}")

except FileNotFoundError:
    print("❌ Error: No se encontró el archivo. Verificá que el nombre sea exactamente igual y esté dentro de la carpeta 'datos'.")
except Exception as e:
    print(f"❌ Ocurrió un error inesperado: {e}")