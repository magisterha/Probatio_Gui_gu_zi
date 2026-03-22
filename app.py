import streamlit as st
from supabase import create_client, Client

# --- CONFIGURACIÓN DE CONEXIÓN ---

@st.cache_resource
def get_supabase_client() -> Client:
    """Retorna el cliente de Supabase configurado. Usamos cache para optimizar conexiones."""
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

# --- 1. MÓDULO DE BÚSQUEDA DE INVESTIGACIÓN (RAG OPTIMIZADO) ---

def search_research_data(tablas_seleccionadas, keywords_raw):
    """
    Realiza una búsqueda filtrada ESTRICTAMENTE en la columna 'Palabras Clave'.
    Optimizado para bases de datos masivas.
    """
    supabase = get_supabase_client()
    contexto_encontrado = []
    
    lista_keywords = [k.strip() for k in keywords_raw.split(",") if k.strip()]
    if not lista_keywords: return []

    for tabla in tablas_seleccionadas:
        try:
            query = supabase.table(tabla).select("*")
            condiciones = ",".join([f'"Palabras Clave".ilike.%{kw}%' for kw in lista_keywords])
            response = query.or_(condiciones).limit(20).execute()
            
            if response.data:
                contexto_encontrado.append({
                    "tabla": tabla,
                    "resultados": response.data
                })
        except Exception as e:
            st.error(f"Error consultando la tabla {tabla}: {str(e)}\n¿Existe la columna 'Palabras Clave' en esta tabla?")
            
    return contexto_encontrado

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
    """Crea un nuevo registro de proyecto inicializando TODAS las columnas."""
    supabase = get_supabase_client()
    
    nuevo_proy = {
        "user_id": user_id,
        "nombre": nombre_tesis,
        "estructura": {},          
        "prompts_maestros": {},    
        "contenido_redactado": {},
        "fichas": [],
        "fuentes_primarias": [], # NUEVA COLUMNA INICIALIZADA
        "repositorio_indices": [],
        "estructura_activa": {},
        "prompts_inteligentes": {},
        "bibliografia": ""
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
        st.error(f"Error al obtener el perfil del usuario: {str(e)}")
        return None
