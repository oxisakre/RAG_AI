import pandas as pd

# Usamos el nombre exacto del archivo Excel
ruta_archivo = "data/wirkstoffe_equiden_v2.xlsx"

try:
    print(f"Intentando abrir el Excel: {ruta_archivo}...\n")
    
    # Al poner sheet_name=None, le decimos a pandas que lea TODAS las pestañas
    excel_completo = pd.read_excel(ruta_archivo, sheet_name=None)
    
    print("✅ ¡Archivo leído con éxito!")
    print("Estas son las pestañas que encontramos adentro:\n")
    
    # Imprimimos los nombres de las pestañas
    for nombre_pestana in excel_completo.keys():
        print(f" 📑 {nombre_pestana}")

except FileNotFoundError:
    print("❌ Error: No se encontró el archivo. Verificá que esté en la carpeta 'data'.")
except Exception as e:
    print(f"❌ Ocurrió un error inesperado: {e}")