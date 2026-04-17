import streamlit as st
from supabase import create_client, Client
import re

# --- CONFIGURACIÓN DE CONEXIÓN ---

@st.cache_resource
def get_supabase_client() -> Client:
    """Retorna el cliente de Supabase configurado. Usamos cache para optimizar conexiones."""
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

# --- 1. MÓDULO DE BÚSQUEDA DE INVESTIGACIÓN (RAG OMNIDIRECCIONAL) ---

def search_research_data(tablas_seleccionadas, keywords_raw):
    """Búsqueda RAG omnidireccional en todas las columnas (incluyendo JSONB)."""
    supabase = get_supabase_client()
    contexto_encontrado = []
    
    lista_keywords = [k.strip() for k in keywords_raw.split(",") if k.strip()]
    if not lista_keywords: return []

    for tabla in tablas_seleccionadas:
        try:
            # Exploración: Descubrimos qué columnas tiene la tabla
            sample = supabase.table(tabla).select("*").limit(1).execute()
            if not sample.data: continue
                
            columnas = sample.data[0].keys()
            condiciones_or = []
            
            # Creamos la condición para buscar cada keyword en CADA columna
            for kw in lista_keywords:
                for col in columnas:
                    # Ignoramos metadatos del sistema
                    if col.lower() not in ["id", "uuid", "user_id", "created_at", "updated_at"]:
                        # ::text permite buscar dentro de JSONB sin que la BD colapse
                        condiciones_or.append(f'"{col}"::text.ilike.%{kw}%')
                        
            if not condiciones_or: continue
            
            # Unimos todas las condiciones (OR)
            filtro_or = ",".join(condiciones_or)
            
            # Ejecutamos la búsqueda limitando a 10 resultados para no saturar la memoria de la IA
            response = supabase.table(tabla).select("*").or_(filtro_or).limit(10).execute()
            
            if response.data:
                contexto_encontrado.append({
                    "tabla": tabla,
                    "resultados": response.data
                })
        except Exception as e:
            # Fallo silencioso controlado para no romper el chat si una tabla da error
            pass
            
    return contexto_encontrado

# --- NUEVO: BUSCADOR EXACTO DE CORPUS CON ESCUDO ANTIMETADATOS ---
def search_corpus_exact(tablas_seleccionadas, termino_busqueda):
    """Busca un término detectando automáticamente la columna de texto y bloqueando fechas/IDs."""
    supabase = get_supabase_client()
    resultados_totales = []
    
    if not termino_busqueda: return []

    columnas_ignoradas = ["id", "uuid", "user_id", "created_at", "updated_at", "fecha_creacion", "fecha", "time"]
    patron_fecha = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}')
    patron_uuid = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)

    for tabla in tablas_seleccionadas:
        try:
            sample = supabase.table(tabla).select("*").limit(1).execute()
            if not sample.data: continue 
                
            fila_prueba = sample.data[0]
            columnas_validas = []
            
            for col_name, col_value in fila_prueba.items():
                if col_name.lower() in columnas_ignoradas: continue
                if not isinstance(col_value, str): continue
                if patron_fecha.match(col_value) or patron_uuid.match(col_value): continue
                columnas_validas.append(col_name)
            
            if not columnas_validas: continue 
            
            posibles_nombres = ["Texto", "texto", "Contenido", "contenido", "text", "Traduccion", "traduccion", "Original", "original"]
            columna_objetivo = next((k for k in columnas_validas if k in posibles_nombres), None)
            
            if not columna_objetivo:
                columna_objetivo = max(columnas_validas, key=lambda k: len(fila_prueba.get(k, "")))
            
            response = supabase.table(tabla).select("*").ilike(columna_objetivo, f"%{termino_busqueda}%").limit(50).execute()
            
            if response.data:
                resultados_totales.append({
                    "tabla": tabla,
                    "columna_usada": columna_objetivo, 
                    "resultados": response.data
                })
        except Exception as e:
            st.error(f"Error interno en tabla {tabla}: {str(e)}")
            
    return resultados_totales

# --- 2. GESTIÓN DE PROYECTOS (TESIS / MONOGRAFÍAS) ---

def get_user_projects(user_id):
    supabase = get_supabase_client()
    try:
        res = supabase.table("proyectos_a").select("*").eq("user_id", user_id).execute()
        return res.data
    except Exception as e:
        st.error(f"Error al cargar los proyectos: {str(e)}")
        return []

def create_new_project(user_id, nombre_tesis):
    supabase = get_supabase_client()
    nuevo_proy = {
        "user_id": user_id, "nombre": nombre_tesis, "estructura": {}, "prompts_maestros": {},    
        "contenido_redactado": {}, "fichas": [], "fuentes_primarias": [], 
        "repositorio_indices": [], "estructura_activa": {}, "prompts_inteligentes": {}, "bibliografia": ""
    }
    try:
        return supabase.table("proyectos_a").insert(nuevo_proy).execute()
    except Exception as e:
        error_msg = str(e)
        if hasattr(e, 'details') and e.details: error_msg = f"{e.details}"
        elif hasattr(e, 'message') and e.message: error_msg = f"{e.message}"
        st.error(f"Fallo en la base de datos al insertar: {error_msg}")
        raise e 

def update_project_data(project_id, data_dict):
    supabase = get_supabase_client()
    return supabase.table("proyectos_a").update(data_dict).eq("id", project_id).execute()

# --- 3. GESTIÓN DE PERFILES ---

def get_user_profile(user_id):
    supabase = get_supabase_client()
    try:
        res = supabase.table("perfiles").select("*").eq("id", user_id).single().execute()
        return res.data
    except Exception as e:
        st.error(f"Error al obtener el perfil: {str(e)}")
        return None
