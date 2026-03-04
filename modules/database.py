import streamlit as st
from supabase import create_client, Client

# --- CONFIGURACIÓN DE CONEXIÓN ---

def get_supabase_client() -> Client:
    """Retorna el cliente de Supabase configurado."""
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

# --- 1. MÓDULO DE BÚSQUEDA DE INVESTIGACIÓN (SINOLOGÍA) ---

def search_research_data(tablas_seleccionadas, keywords_raw):
    """
    Realiza una búsqueda filtrada en las tablas de investigación 
    para evitar el 'ruido' en la IA.
    """
    supabase = get_supabase_client()
    contexto_encontrado = []
    
    # Limpiamos las palabras clave
    lista_keywords = [k.strip() for k in keywords_raw.split(",") if k.strip()]
    
    if not lista_keywords:
        return []

    for tabla in tablas_seleccionadas:
        try:
            # Iniciamos la consulta
            query = supabase.table(tabla).select("*")
            
            # Construimos el filtro OR para todas las palabras clave
            # Buscamos en la columna 'Palabras Clave' (o la columna que contenga el texto)
            # Nota: .ilike es case-insensitive
            condiciones = ",".join([f'"Palabras Clave".ilike.%{kw}%' for kw in lista_keywords])
            
            response = query.or_(condiciones).execute()
            
            if response.data:
                contexto_encontrado.append({
                    "tabla": tabla,
                    "resultados": response.data
                })
        except Exception as e:
            st.error(f"Error consultando la tabla {tabla}: {e}")
            
    return contexto_encontrado

# --- 2. GESTIÓN DE PROYECTOS (TESIS / MONOGRAFÍAS) ---

def get_user_projects(user_id):
    """Recupera todos los proyectos de un usuario."""
    supabase = get_supabase_client()
    res = supabase.table("proyectos").select("*").eq("user_id", user_id).execute()
    return res.data

def create_new_project(user_id, nombre_tesis):
    """Crea un nuevo registro de proyecto con estructura vacía."""
    supabase = get_supabase_client()
    nuevo_proy = {
        "user_id": user_id,
        "nombre": nombre_tesis,
        "estructura": {},      # JSON vacío para la Fase B
        "prompts_maestros": {}, # JSON vacío para la Fase C
        "contenido_redactado": {} # JSON vacío para la Fase D
    }
    return supabase.table("proyectos").insert(nuevo_proy).execute()

def update_project_data(project_id, data_dict):
    """
    Actualiza cualquier campo del proyecto (estructura, prompts o contenido).
    data_dict debe ser algo como {"estructura": {...}}
    """
    supabase = get_supabase_client()
    return supabase.table("proyectos").update(data_dict).eq("id", project_id).execute()

# --- 3. GESTIÓN DE PERFILES ---

def get_user_profile(user_id):
    """Obtiene datos adicionales del investigador."""
    supabase = get_supabase_client()
    res = supabase.table("perfiles").select("*").eq("id", user_id).single().execute()
    return res.data
