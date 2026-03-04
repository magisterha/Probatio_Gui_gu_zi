import streamlit as st
from supabase import create_client, Client
import google.generativeai as genai
import json

# --- 1. CONFIGURACIÓN E INICIALIZACIÓN ---
st.set_page_config(
    page_title="Investigador de Sinología AI", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# Inicializar conexión a Supabase y Gemini
try:
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    model = genai.GenerativeModel('gemini-2.0-flash')
except Exception as e:
    st.error(f"Error de conexión: {e}")
    st.stop()

# --- 2. GESTIÓN DEL ESTADO DE LA SESIÓN ---
# Esto permite que la app "recuerde" en qué proyecto estás trabajando
if "user" not in st.session_state:
    st.session_state.user = None
if "current_project" not in st.session_state:
    st.session_state.current_project = None
if "active_tab" not in st.session_state:
    st.session_state.active_tab = "Ideas"

# --- 3. FUNCIONES DE APOYO (LÓGICA DE NEGOCIO) ---

def render_sidebar_auth():
    """Maneja el login y la selección de proyectos en la barra lateral."""
    with st.sidebar:
        st.title("🏯 Panel de Investigador")
        
        if not st.session_state.user:
            st.subheader("Acceso")
            with st.form("login_form"):
                email = st.text_input("Correo electrónico")
                password = st.text_input("Contraseña", type="password")
                if st.form_submit_button("Entrar"):
                    try:
                        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                        st.session_state.user = res.user
                        st.success("¡Bienvenido!")
                        st.rerun()
                    except Exception as e:
                        st.error("Error de acceso.")
        else:
            st.write(f"Conectado como: **{st.session_state.user.email}**")
            
            # Selector de Proyectos (de la tabla 'proyectos')
            res = supabase.table("proyectos").select("*").eq("user_id", st.session_state.user.id).execute()
            proyectos = res.data
            
            nombres_proy = [p['nombre'] for p in proyectos] if proyectos else []
            proy_sel = st.selectbox("Mis Proyectos / Tesis", ["-- Nuevo Proyecto --"] + nombres_proy)
            
            if proy_sel == "-- Nuevo Proyecto --":
                with st.expander("Crear Proyecto"):
                    nuevo_nombre = st.text_input("Título de la Tesis/Monografía")
                    if st.button("Crear"):
                        # Insertar en Supabase
                        new_p = {"nombre": nuevo_nombre, "user_id": st.session_state.user.id, "estructura": {}}
                        supabase.table("proyectos").insert(new_p).execute()
                        st.rerun()
            else:
                st.session_state.current_project = next(p for p in proyectos if p['nombre'] == proy_sel)

            if st.button("Cerrar Sesión"):
                st.session_state.user = None
                st.rerun()

# --- 4. COMPONENTES DE LAS FASES (UI) ---

def phase_a_ideas():
    st.header("1. Lluvia de Ideas y Conceptos")
    st.markdown("Usa este chat para pivotar el tema de tu investigación.")
    # (Aquí iría la lógica de chat que ya tenías)
    st.chat_input("Escribe tu idea aquí...")

def phase_b_structure():
    st.header("2. Estructura de la Monografía")
    # Filtros para evitar el "ruido"
    col1, col2 = st.columns(2)
    with col1:
        tablas = st.multiselect("Bases de datos de referencia:", 
                                ["戰國策", "Xunzi", "Mencio", "Analectas", "Glosas 鬼谷子"])
    with col2:
        kws = st.text_input("Palabras clave (separadas por comas)")
    
    if st.button("Generar Índice Académico"):
        st.info("La IA está analizando las fuentes para proponer capítulos...")
        # Llamada a Gemini con rol de Metodólogo

def phase_c_prompts():
    st.header("3. Generador de Prompts Maestros")
    if not st.session_state.current_project or not st.session_state.current_project.get('estructura'):
        st.warning("Primero define la estructura en la Fase 2.")
    else:
        st.write("Configura las instrucciones para cada sección de tu tesis.")

def phase_d_writing():
    st.header("4. Redacción del Documento")
    st.markdown("Aquí se genera el texto siguiendo el orden de una tesis doctoral.")
    # El output aquí NO es chat, es un contenedor de texto limpio.
    with st.container(border=True):
        st.write("*El borrador aparecerá aquí conforme ejecutes los prompts maestros.*")

# --- 5. CUERPO PRINCIPAL ---

def main():
    render_sidebar_auth()
    
    if not st.session_state.user:
        st.title("Bienvenido al Asistente de Investigación en Sinología")
        st.info("Por favor, inicia sesión en la barra lateral para gestionar tus proyectos de investigación.")
        return

    if st.session_state.current_project:
        st.title(f"PROYECTO: {st.session_state.current_project['nombre']}")
        
        # Tabs que replican la lógica de una tesis
        tab_ideas, tab_struct, tab_prompts, tab_write = st.tabs([
            "💡 Ideas", "🏗️ Estructura", "✍️ Prompts Maestros", "📜 Redacción"
        ])

        with tab_ideas: phase_a_ideas()
        with tab_struct: phase_b_structure()
        with tab_prompts: phase_c_prompts()
        with tab_write: phase_d_writing()
    else:
        st.warning("Selecciona un proyecto en la barra lateral para comenzar.")

if __name__ == "__main__":
    main()
