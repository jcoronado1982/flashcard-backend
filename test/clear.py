import json
import os # Necesario para renombrar archivos de forma segura

# --- Configuración de Archivos ---
BASIC_FILE = '1-basic.json'
INTERMEDIATE_FILE = '2-intermediate.json'
ADVANCED_FILE = '3-advanced.json'
# ---------------------------------

def clean_json_file(file_to_clean, names_to_exclude_set):
    """
    Limpia un archivo JSON de duplicados internos y superposiciones externas.
    Sobrescribe el archivo original de forma segura.
    Devuelve un conjunto de los nombres únicos que quedaron en el archivo.
    """
    clean_list = []
    seen_names = set() # Para duplicados internos
    internal_dupes = 0
    external_dupes = 0
    total_read = 0
    
    # --- Paso 1: Leer y filtrar ---
    try:
        with open(file_to_clean, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if not isinstance(data, list):
             print(f"Error: El archivo '{file_to_clean}' no contiene una lista JSON. Abortando este archivo.")
             return None

        total_read = len(data)
        
        for item in data:
            if not isinstance(item, dict) or 'name' not in item:
                continue # Ignorar items no válidos
            
            name = item['name']
            
            # 1. ¿Está en la lista de exclusión (superposición)?
            if name in names_to_exclude_set:
                external_dupes += 1
                continue
            
            # 2. ¿Es un duplicado interno que ya hemos visto?
            if name in seen_names:
                internal_dupes += 1
                continue
                
            # Si está limpio, añadirlo
            clean_list.append(item)
            seen_names.add(name)

    except FileNotFoundError:
        print(f"Error: No se encontró el archivo '{file_to_clean}'.")
        return None
    except json.JSONDecodeError:
        print(f"Error: El archivo '{file_to_clean}' está mal formateado o vacío.")
        return None
    except Exception as e:
        print(f"Error al leer '{file_to_clean}': {e}")
        return None
    
    # --- Paso 2: Guardar de forma segura ---
    temp_file = file_to_clean + ".tmp"
    try:
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(clean_list, f, indent=2, ensure_ascii=False)
        
        # Si la escritura fue exitosa, reemplazar el original
        os.remove(file_to_clean)
        os.rename(temp_file, file_to_clean)
        
        print(f"--- Limpieza de '{file_to_clean}' completa ---")
        print(f"Items leídos: {total_read}")
        print(f"Duplicados internos eliminados: {internal_dupes}")
        print(f"Superposiciones (externas) eliminadas: {external_dupes}")
        print(f"Total de items únicos guardados: {len(clean_list)}")
        print("-" * 30)
        
        return seen_names # Devolver el conjunto de nombres limpios

    except Exception as e:
        print(f"Error al guardar el archivo '{file_to_clean}': {e}")
        # Si falló el guardado, intentar limpiar el temporal si existe
        if os.path.exists(temp_file):
            os.remove(temp_file)
        return None

def run_full_cleaning_process():
    """
    Ejecuta el proceso de limpieza en los tres archivos en orden:
    1. Limpia Basic (internos)
    2. Limpia Intermediate (internos + vs Basic)
    3. Limpia Advanced (internos + vs Basic + vs Intermediate)
    """
    
    print("Iniciando proceso de limpieza de archivos JSON...\n")

    # 1. Limpiar Archivo Básico (solo duplicados internos)
    # El conjunto de exclusión está vacío
    clean_basic_names = clean_json_file(BASIC_FILE, set())
    if clean_basic_names is None:
        print("Error crítico al procesar '1-basic.json'. Abortando.")
        return

    # 2. Limpiar Archivo Intermedio
    # Excluir todo lo que ya está en el básico limpio
    clean_intermediate_names = clean_json_file(INTERMEDIATE_FILE, clean_basic_names)
    if clean_intermediate_names is None:
        print("Error crítico al procesar '2-intermediate.json'. Abortando.")
        return

    # 3. Limpiar Archivo Avanzado
    # Crear un conjunto unificado de exclusión (Básico + Intermedio)
    all_previous_names = clean_basic_names.union(clean_intermediate_names)
    clean_advanced_names = clean_json_file(ADVANCED_FILE, all_previous_names)
    if clean_advanced_names is None:
        print("Error crítico al procesar '3-advanced.json'.")
        return

    print("\n¡Éxito! Los 3 archivos han sido limpiados y sobrescritos.")
    print(f"Total Básico: {len(clean_basic_names)} items")
    print(f"Total Intermedio: {len(clean_intermediate_names)} items")
    print(f"Total Avanzado: {len(clean_advanced_names)} items")

# --- Ejecutar el script ---
if __name__ == "__main__":
    run_full_cleaning_process()