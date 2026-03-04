import streamlit as st
from supabase import create_client, Client
import google.generativeai as genai
import json

# --- CONFIGURACIÓN INICIAL ---
st.set_page_config(page_title="Investigador IA - Sinología", layout="wide")

# Conexión (Asegúrate de tener estas variables en secrets)
try:
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    model = genai.GenerativeModel('gemini-2.0-flash')
except Exception as e:
    st.error(f"Error de configuración: {e}")

# --- ESTADO DE LA SESIÓN ---
if "user" not in st.session_state:
    st.session_state.user = None
if "current_project" not in st.session_state:
    st.session_state.current_project = None

# --- FUNCIONES DE BASE DE DATOS ---

def login_usuario(email, password):
    # Lógica simplificada de login con Supabase
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        st.session_state.user = res.user
        return True
    except:
        return False

def cargar_proyectos():
    if st.session_state.user:
        res = supabase.table("proyectos").select("*").eq("user_id", st.session_state.user.id).execute()
        return res.data
    return []

# --- INTERFAZ DE USUARIO (FRONTEND TIPO MONOGRAFÍA) ---

def main():
    if not st.session_state.user:
        render_login()
    else:
        render_dashboard()

def render_login():
    st.title("Acceso Investigadores")
    with st.form("login"):
        email = st.text_input("Email")
        pw = st.text_input("Password", type="password")
        if st.form_submit_button("Entrar"):
            if login_usuario(email, pw):
                st.rerun()

def render_dashboard():
    # Sidebar para gestión de proyectos
    with st.sidebar:
        st.write(f"Usuario: {st.session_state.user.email}")
        proyectos = cargar_proyectos()
        nombres_proyectos = [p['nombre'] for p in proyectos]
        
        proy_sel = st.selectbox("Mis Proyectos", ["-- Seleccionar --"] + nombres_proyectos)
        if proy_sel != "-- Seleccionar --":
            st.session_state.current_project = next(p for p in proyectos if p['nombre'] == proy_sel)
        
        if st.button("Nuevo Proyecto"):
            # Lógica para insertar en tabla 'proyectos'
            pass
        
        if st.button("Cerrar Sesión"):
            st.session_state.user = None
            st.rerun()

    if st.session_state.current_project:
        st.title(f"Proyecto: {st.session_state.current_project['nombre']}")
        
        # EL NÚCLEO: Las 4 Fases de la Investigación
        tab1, tab2, tab3, tab4 = st.tabs([
            "1. Lluvia de Ideas", 
            "2. Estructura/Índice", 
            "3. Prompts Maestros", 
            "4. Redacción Académica"
        ])

        with tab1:
            render_fase_ideas()
        with tab2:
            render_fase_estructura()
        with tab3:
            render_fase_prompts()
        with tab4:
            render_fase_ejecucion()
    else:
        st.info("Selecciona o crea un proyecto para comenzar.")

# --- LÓGICA DE LAS FASES (LLAMADAS API) ---

def render_fase_ideas():
    st.subheader("Borrador de Ideas (Chat)")
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
            
    if prompt := st.chat_input("¿Sobre qué quieres pivotar tu tesis?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        # Aquí llamarías a Gemini (con el contexto de Pekín y Sinología)
        response = model.generate_content(prompt).text
        st.session_state.messages.append({"role": "assistant", "content": response})
        st.rerun()

def render_fase_estructura():
    st.subheader("Definición del Índice de la Monografía")
    # Aquí el output de la IA se parsea para crear una lista de capítulos
    # Se guarda en la columna 'estructura' (JSON) de tu tabla proyectos
    st.info("Aquí la IA sugiere capítulos basados en la fase 1.")
    if st.button("Generar Estructura Sugerida"):
        # LLAMADA TIPO B: "Genera un JSON con Capítulo, Subcapítulo y Objetivo"
        pass

def render_fase_prompts():
    st.subheader("Generador de Prompts Maestros")
    # Basado en la estructura de la fase 2, genera un prompt específico por sección
    st.markdown("> **Lógica:** Si el Cap 1 es 'Contexto en Pekín', el prompt maestro incluirá instrucciones de estilo académico y fuentes de Supabase.")

def render_fase_ejecucion():
    st.subheader("Escritura de la Tesis")
    # Aquí se ejecutan los prompts del tab 3
    # El frontend debe parecer un documento: Título, Cuerpo, Citas.
    st.write("---")
    st.markdown("## Título del Capítulo")
    st.write("Aquí aparece el texto generado en formato monográfico, no chat.")

if __name__ == "__main__":
    main()
