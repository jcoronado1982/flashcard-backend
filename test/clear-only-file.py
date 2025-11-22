import json
import os # Necesario para renombrar archivos de forma segura

# --- Configuración de Archivos ---
BASIC_FILE = '1-basic.json'
INTERMEDIATE_FILE = '2-intermediate.json'
# Usaremos un archivo temporal para seguridad
TEMP_FILE = '2-intermediate-temp.json'
# ---------------------------------

def limpiar_duplicados_en_sitio():
    
    # --- Paso 1: Cargar todos los nombres del archivo Básico ---
    try:
        with open(BASIC_FILE, 'r', encoding='utf-8') as f:
            basic_data = json.load(f)
        
        # Usamos un "set" para una búsqueda súper rápida
        basic_names = set(item['name'] for item in basic_data if 'name' in item)
        print(f"Archivo básico '{BASIC_FILE}' cargado: {len(basic_names)} sustantivos únicos encontrados.")
        
    except FileNotFoundError:
        print(f"Error: No se encontró el archivo '{BASIC_FILE}'.")
        print("Asegúrate de que el script esté en la misma carpeta que tus archivos JSON.")
        return
    except Exception as e:
        print(f"Error al leer '{BASIC_FILE}': {e}")
        return

    # --- Paso 2: Leer el archivo Intermedio y filtrar ---
    clean_intermediate_list = []
    seen_intermediate_names = set() # Para evitar duplicados DENTRO del mismo archivo
    duplicates_skipped_basic = 0
    duplicates_skipped_internal = 0
    total_items_read = 0
    
    try:
        with open(INTERMEDIATE_FILE, 'r', encoding='utf-8') as f:
            intermediate_data = json.load(f)
        
        total_items_read = len(intermediate_data)
        print(f"Procesando '{INTERMEDIATE_FILE}' (leyendo {total_items_read} items)...")

        for item in intermediate_data:
            if 'name' not in item:
                continue # Ignorar si el item no tiene 'name'
            
            name = item['name']
            
            # Comparamos:
            # 1. ¿Está en la lista básica?
            if name in basic_names:
                duplicates_skipped_basic += 1
                continue # Es un duplicado del básico, saltar
            
            # 2. ¿Es un duplicado interno que ya hemos añadido?
            if name in seen_intermediate_names:
                duplicates_skipped_internal += 1
                continue # Es un duplicado interno, saltar
                
            # Si no es duplicado, lo añadimos a la lista limpia
            clean_intermediate_list.append(item)
            seen_intermediate_names.add(name)

    except FileNotFoundError:
        print(f"Error: No se encontró el archivo '{INTERMEDIATE_FILE}'.")
        return
    except json.JSONDecodeError:
        print(f"Error: El archivo '{INTERMEDIATE_FILE}' parece estar mal formateado o vacío.")
        return
    except Exception as e:
        print(f"Error al leer '{INTERMEDIATE_FILE}': {e}")
        return

    # --- Paso 3: Guardar el nuevo archivo limpio (de forma segura) ---
    try:
        # Escribimos en un archivo temporal primero
        with open(TEMP_FILE, 'w', encoding='utf-8') as f:
            json.dump(clean_intermediate_list, f, indent=2, ensure_ascii=False)
        
        # Si todo salió bien, eliminamos el original y renombramos el temporal
        os.remove(INTERMEDIATE_FILE)
        os.rename(TEMP_FILE, INTERMEDIATE_FILE)
            
        print("\n--- ¡Éxito! ---")
        print(f"Items leídos: {total_items_read}")
        print(f"Se eliminaron {duplicates_skipped_basic} sustantivos (ya estaban en el básico).")
        print(f"Se eliminaron {duplicates_skipped_internal} duplicados internos.")
        print(f"Total de sustantivos únicos guardados: {len(clean_intermediate_list)}")
        print(f"¡El archivo '{INTERMEDIATE_FILE}' ha sido limpiado y sobrescrito!")

    except Exception as e:
        print(f"Error al guardar el archivo: {e}")

# --- Ejecutar el script ---
if __name__ == "__main__":
    limpiar_duplicados_en_sitio()