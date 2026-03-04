import streamlit as st
import json
from modules.database import (
    search_research_data, 
    get_user_projects, 
    create_new_project, 
    update_project_data
)
from modules.ai_engine import (
    chat_with_ideas, 
    generate_research_structure, 
    create_master_prompt_for_section, 
    execute_section_writing
)

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Investigador de Sinología AI",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilo CSS para que el output parezca una monografía y no un chat
st.markdown("""
    <style>
    .document-box {
        background-color: #f9f9f9;
        padding: 40px;
        border-radius: 10px;
        border: 1px solid #ddd;
        font-family: 'Times New Roman', Times, serif;
        line-height: 1.6;
        color: #333;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. ESTADO DE LA SESIÓN ---
if "user" not in st.session_state:
    st.session_state.user = None
if "current_project" not in st.session_state:
    st.session_state.current_project = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# --- 3. BARRA LATERAL (AUTH Y PROYECTOS) ---
with st.sidebar:
    st.title("🏯 Xùngǔ Architect")
    st.info("Sede Académica: Pekín")
    
    if not st.session_state.user:
        st.subheader("Acceso Investigador")
        with st.form("auth_form"):
            email = st.text_input("Email")
            pw = st.text_input("Password", type="password")
            if st.form_submit_button("Entrar"):
                # Aquí llamarías a supabase.auth.sign_in_with_password
                # Para este ejemplo, simulamos el éxito:
                st.session_state.user = {"id": "user_123", "email": email}
                st.rerun()
    else:
        st.write(f"Sesión: {st.session_state.user['email']}")
        
        # Gestión de Proyectos
        proyectos = get_user_projects(st.session_state.user['id'])
        nombres = [p['nombre'] for p in proyectos] if proyectos else []
        
        sel = st.selectbox("Seleccionar Proyecto", ["-- Nuevo --"] + nombres)
        
        if sel == "-- Nuevo --":
            nuevo_n = st.text_input("Nombre de la nueva tesis")
            if st.button("Crear Proyecto"):
                create_new_project(st.session_state.user['id'], nuevo_n)
                st.rerun()
        else:
            st.session_state.current_project = next(p for p in proyectos if p['nombre'] == sel)
        
        if st.button("Cerrar Sesión"):
            st.session_state.user = None
            st.session_state.current_project = None
            st.rerun()

# --- 4. CUERPO PRINCIPAL (LAS 4 FASES) ---

if not st.session_state.user:
    st.title("Plataforma de Investigación Avanzada")
    st.warning("Inicia sesión para acceder a tus borradores de tesis.")
elif not st.session_state.current_project:
    st.title("Bienvenido")
    st.info("Selecciona o crea un proyecto en la barra lateral para comenzar la investigación.")
else:
    st.title(f"Proyecto: {st.session_state.current_project['nombre']}")
    
    tab1, tab2, tab3, tab4 = st.tabs([
        "💡 A. Lluvia de Ideas", 
        "🏗️ B. Estructura", 
        "✍️ C. Prompts Maestros", 
        "📜 D. Redacción Final"
    ])

    # --- FASE A: CHAT DE IDEAS ---
    with tab1:
        st.subheader("Exploración Conceptual")
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])
        
        if prompt := st.chat_input("Discute tus ideas sobre el proyecto..."):
            st.session_state.chat_history.append({"role": "user", "content": prompt})
            with st.chat_message("user"): st.write(prompt)
            
            with st.chat_message("assistant"):
                res = chat_with_ideas(st.session_state.chat_history, prompt)
                st.write(res)
                st.session_state.chat_history.append({"role": "assistant", "content": res})

    # --- FASE B: ESTRUCTURA ---
    with tab2:
        st.subheader("Generación de la Estructura de la Tesis")
        col1, col2 = st.columns(2)
        with col1:
            tablas = st.multiselect("Bases de datos para este índice:", 
                                    ["戰國策", "Xunzi", "Mencio", "JSON de investigación", "Glosas de 鬼谷子", "Fuentes secundarias", "Analectas de Confucio"])
        with col2:
            kws = st.text_input("Keywords para filtrar (coma-separadas)")
        
        enfoque = st.text_area("Enfoque metodológico")
        
        if st.button("Diseñar Estructura Académica"):
            contexto = search_research_data(tablas, kws)
            nueva_estructura = generate_research_structure(contexto, enfoque)
            update_project_data(st.session_state.current_project['id'], {"estructura": nueva_estructura})
            st.session_state.current_project['estructura'] = nueva_estructura
            st.success("Estructura guardada correctamente.")
            st.rerun()
            
        if st.session_state.current_project.get('estructura'):
            st.json(st.session_state.current_project['estructura'])

    # --- FASE C: PROMPTS MAESTROS ---
    with tab3:
        st.subheader("Configuración de Prompts de Redacción")
        est = st.session_state.current_project.get('estructura')
        if not est:
            st.error("Crea una estructura en la Fase B primero.")
        else:
            for cap in est['capitulos']:
                with st.expander(f"Capítulo {cap['nro']}: {cap['titulo']}"):
                    if st.button(f"Generar Prompt Maestro para Cap {cap['nro']}"):
                        pm = create_master_prompt_for_section(cap, "Contexto Global")
                        # Guardar el prompt en el JSON de prompts del proyecto
                        prompts_actuales = st.session_state.current_project.get('prompts_maestros') or {}
                        prompts_actuales[str(cap['nro'])] = pm
                        update_project_data(st.session_state.current_project['id'], {"prompts_maestros": prompts_actuales})
                        st.session_state.current_project['prompts_maestros'] = prompts_actuales
                    
                    p_maestro = st.session_state.current_project.get('prompts_maestros', {}).get(str(cap['nro']), "")
                    st.text_area("Prompt Maestro:", value=p_maestro, height=150, key=f"area_{cap['nro']}")

    # --- FASE D: REDACCIÓN ---
    with tab4:
        st.subheader("Borrador de la Monografía")
        prompts = st.session_state.current_project.get('prompts_maestros')
        
        if not prompts:
            st.warning("No hay prompts maestros generados.")
        else:
            cap_sel = st.selectbox("Capítulo a redactar", [f"Cap {k}" for k in prompts.keys()])
            nro_cap = cap_sel.split(" ")[1]
            
            if st.button(f"Ejecutar Redacción de {cap_sel}"):
                with st.spinner("Redactando siguiendo lógica académica..."):
                    # Aquí pasamos los filtros de nuevo para que la redacción use datos reales
                    ctx_redaccion = search_research_data(["戰國策", "Xunzi", "Mencio", "Analectas"], "virtud, ritual") 
                    texto = execute_section_writing(prompts[nro_cap], ctx_redaccion)
                    
                    # Guardar contenido
                    cont_actual = st.session_state.current_project.get('contenido_redactado') or {}
                    cont_actual[nro_cap] = texto
                    update_project_data(st.session_state.current_project['id'], {"contenido_redactado": cont_actual})
                    st.session_state.current_project['contenido_redactado'] = cont_actual

            # VISUALIZACIÓN TIPO MONOGRAFÍA
            st.divider()
            documento = st.session_state.current_project.get('contenido_redactado', {})
            if documento:
                with st.container():
                    st.markdown(f"<div class='document-box'>", unsafe_allow_html=True)
                    for n, txt in sorted(documento.items()):
                        st.markdown(f"### Capítulo {n}")
                        st.write(txt)
                    st.markdown("</div>", unsafe_allow_html=True)
