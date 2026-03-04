import streamlit as st
from supabase import create_client, Client

# --- CONFIGURACIÓN DE CONEXIÓN ---

@st.cache_resource
def get_supabase_client() -> Client:
    """Retorna el cliente de Supabase configurado. Usamos cache para optimizar conexiones."""
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
            condiciones = ",".join([f'"Palabras Clave".ilike.%{kw}%' for kw in lista_keywords])
            
            response = query.or_(condiciones).execute()
            
            if response.data:
                contexto_encontrado.append({
                    "tabla": tabla,
                    "resultados": response.data
                })
        except Exception as e:
            st.error(f"Error consultando la tabla {tabla}: {str(e)}")
            
    return contexto_encontrado

# --- 2. GESTIÓN DE PROYECTOS (TESIS / MONOGRAFÍAS) ---
# ATENCIÓN: Ahora apuntamos a la tabla 'proyectos_a'

def get_user_projects(user_id):
    """Recupera todos los proyectos de un usuario desde la nueva tabla proyectos_a."""
    supabase = get_supabase_client()
    try:
        res = supabase.table("proyectos_a").select("*").eq("user_id", user_id).execute()
        return res.data
    except Exception as e:
        st.error(f"Error al cargar los proyectos: {str(e)}")
        return []

def create_new_project(user_id, nombre_tesis):
    """Crea un nuevo registro de proyecto con estructura vacía en proyectos_a."""
    supabase = get_supabase_client()
    
    nuevo_proy = {
        "user_id": user_id,
        "nombre": nombre_tesis,
        "estructura": {},          
        "prompts_maestros": {},    
        "contenido_redactado": {}  
    }
    
    try:
        return supabase.table("proyectos_a").insert(nuevo_proy).execute()
    except Exception as e:
        # Extraemos el mensaje real de la API si existe
        error_msg = str(e)
        if hasattr(e, 'details') and e.details:
            error_msg = f"{e.details}"
        elif hasattr(e, 'message') and e.message:
            error_msg = f"{e.message}"
            
        st.error(f"Fallo en la base de datos al insertar: {error_msg}")
        raise e 

def update_project_data(project_id, data_dict):
    """
    Actualiza cualquier campo del proyecto en proyectos_a.
    """
    supabase = get_supabase_client()
    try:
        return supabase.table("proyectos_a").update(data_dict).eq("id", project_id).execute()
    except Exception as e:
        st.error(f"Error al actualizar los datos del proyecto: {str(e)}")
        return None

# --- 3. GESTIÓN DE PERFILES ---

def get_user_profile(user_id):
    """Obtiene datos adicionales del investigador."""
    supabase = get_supabase_client()
    try:
        res = supabase.table("perfiles").select("*").eq("id", user_id).single().execute()
        return res.data
    except Exception as e:
        st.error(f"Error al obtener el perfil del usuario: {str(e)}")
        return None
