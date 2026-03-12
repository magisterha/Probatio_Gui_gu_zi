import streamlit as st
from supabase import create_client, Client
import json
import time

# Importaciones de nuestros módulos personalizados (Backend)
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
    refine_prompt_into_subprompts,
    execute_section_writing
)

# --- 1. CONFIGURACIÓN DE PÁGINA Y BASE DE DATOS ---
st.set_page_config(
    page_title="Investigador de Sinología AI",
    layout="wide",
    initial_sidebar_state="expanded"
)

try:
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception as e:
    st.error(f"Error crítico: No se pudo conectar a Supabase. {e}")
    st.stop()

st.markdown("""
    <style>
    .document-box {
        background-color: #ffffff;
        padding: 40px;
        border-radius: 5px;
        border: 1px solid #cccccc;
        font-family: 'Times New Roman', Times, serif;
        line-height: 1.8;
        color: #000000;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
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

# --- 3. BARRA LATERAL ---
with st.sidebar:
    st.title("Arquitectura de Tesis")
    
    if not st.session_state.user:
        st.subheader("Acceso Investigador")
        tab_login, tab_registro, tab_recuperar = st.tabs(["Entrar", "Registro", "Recuperar"])
        
        with tab_login:
            with st.form("login_form"):
                email = st.text_input("Email")
                pw = st.text_input("Contraseña", type="password")
                if st.form_submit_button("Iniciar Sesión"):
                    try:
                        res = supabase.auth.sign_in_with_password({"email": email, "password": pw})
                        st.session_state.user = {"id": res.user.id, "email": res.user.email}
                        st.success("Acceso concedido.")
                        st.rerun()
                    except Exception as e:
                        st.error("Credenciales incorrectas.")
        
        with tab_registro:
            with st.form("register_form"):
                reg_email = st.text_input("Nuevo Email")
                reg_pw = st.text_input("Contraseña (mín. 6 caracteres)", type="password")
                if st.form_submit_button("Crear Cuenta"):
                    try:
                        res = supabase.auth.sign_up({"email": reg_email, "password": reg_pw})
                        st.success("Cuenta creada exitosamente.")
                    except Exception as e:
                        st.error(f"Error: {e}")
                        
        with tab_recuperar:
            with st.form("recover_form"):
                rec_email = st.text_input("Email de tu cuenta")
                if st.form_submit_button("Recuperar"):
                    try:
                        supabase.auth.reset_password_email(rec_email)
                        st.success("Instrucciones enviadas.")
                    except Exception as e:
                        st.error(f"Error: {e}")
    else:
        st.write(f"Investigador: **{st.session_state.user['email']}**")
        st.divider()
        
        proyectos = get_user_projects(st.session_state.user['id'])
        nombres = [p['nombre'] for p in proyectos] if proyectos else []
        
        sel = st.selectbox("Mis Monografías", ["-- Nuevo Proyecto --"] + nombres)
        
        if sel == "-- Nuevo Proyecto --":
            with st.form("new_proj_form"):
                nuevo_n = st.text_input("Título provisional")
                if st.form_submit_button("Crear Proyecto"):
                    if nuevo_n.strip():
                        create_new_project(st.session_state.user['id'], nuevo_n)
                        st.success("Proyecto creado.")
                        st.rerun()
        else:
            st.session_state.current_project = next(p for p in proyectos if p['nombre'] == sel)
        
        st.divider()
        if st.button("Cerrar Sesión"):
            supabase.auth.sign_out()
            st.session_state.user = None
            st.session_state.current_project = None
            st.session_state.chat_history = []
            st.rerun()

# --- 4. CUERPO PRINCIPAL (LAS 5 FASES DE INVESTIGACIÓN) ---

if not st.session_state.user:
    st.title("Plataforma de Autoría Asistida")
    st.info("👈 Por favor, inicia sesión para acceder a tu área de trabajo.")
elif not st.session_state.current_project:
    st.title("Área de Trabajo")
    st.info("👈 Selecciona o crea un proyecto en la barra lateral.")
else:
    st.title(f"📖 {st.session_state.current_project['nombre']}")
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "💡 A. Ideas", 
        "🏗️ B. Estructura", 
        "✍️ C. Prompts Maestros", 
        "🔬 D. Refinador",
        "📜 E. Redacción Final"
    ])

    # --- FASE A: CHAT DE IDEAS ---
    with tab1:
        st.subheader("Exploración Conceptual")
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])
        
        if prompt := st.chat_input("Escribe tu idea de investigación aquí..."):
            st.session_state.chat_history.append({"role": "user", "content": prompt})
            with st.chat_message("user"): 
                st.write(prompt)
            
            with st.chat_message("assistant"):
                with st.spinner("Analizando..."):
                    res = chat_with_ideas(st.session_state.chat_history, prompt)
                    st.write(res)
                    st.session_state.chat_history.append({"role": "assistant", "content": res})

    # --- FASE B: ESTRUCTURA ---
    with tab2:
        st.subheader("Arquitectura de la Monografía")
        col1, col2 = st.columns(2)
        with col1:
            tablas_seleccionadas = st.multiselect(
                "Bases de datos bibliográficas a incluir:", 
                ["戰國策", "Xunzi", "Mencio", "JSON de investigación", "Glosas de 鬼谷子", "Fuentes secundarias", "Analectas de Confucio"],
                default=["Analectas de Confucio"]
            )
        with col2:
            kws = st.text_input("Palabras clave (separadas por comas)", placeholder="virtud, ren")
        
        enfoque = st.text_area("Enfoque metodológico principal de la tesis:")
        
        if st.button("Diseñar Índice Académico", type="primary"):
            if not tablas_seleccionadas or not kws.strip():
                st.warning("Selecciona al menos una fuente y define palabras clave.")
            else:
                with st.spinner("Estructurando capítulos..."):
                    contexto = search_research_data(tablas_seleccionadas, kws)
                    nueva_estructura = generate_research_structure(contexto, enfoque)
                    if nueva_estructura:
                        update_project_data(st.session_state.current_project['id'], {"estructura": nueva_estructura})
                        st.session_state.current_project['estructura'] = nueva_estructura
                        st.success("Estructura generada!")
                        st.rerun()
            
        est = st.session_state.current_project.get('estructura')
        
        if est and isinstance(est, dict) and 'capitulos' in est:
            st.divider()
            st.markdown("### ✏️ Editor Interactivo del Índice")
            
            with st.form("form_edicion_estructura"):
                nuevo_titulo_tesis = st.text_input("Título General de la Tesis:", value=est.get('titulo_tesis', ''))
                capitulos_editados = []
                
                for i, cap in enumerate(est.get('capitulos', [])):
                    nro = cap.get('nro', i+1)
                    with st.expander(f"Capítulo {nro}: {cap.get('titulo', 'Sin Título')}"):
                        edit_titulo = st.text_input(f"Título del Capítulo {nro}", value=cap.get('titulo', ''), key=f"titulo_{i}")
                        edit_objetivo = st.text_area(f"Objetivo del Capítulo {nro}", value=cap.get('objetivo', ''), key=f"obj_{i}")
                        subpuntos_actuales = "\n".join(cap.get('subpuntos', []))
                        edit_subpuntos = st.text_area("Subpuntos (uno por línea)", value=subpuntos_actuales, height=150, key=f"subs_{i}")
                        
                        capitulos_editados.append({
                            "nro": nro,
                            "titulo": edit_titulo,
                            "objetivo": edit_objetivo,
                            "subpuntos": [linea.strip() for linea in edit_subpuntos.split('\n') if linea.strip()]
                        })

                if st.form_submit_button("💾 Guardar Estructura", type="primary"):
                    estructura_actualizada = {
                        "titulo_tesis": nuevo_titulo_tesis,
                        "introduccion": est.get('introduccion', ''),
                        "capitulos": capitulos_editados
                    }
                    update_project_data(st.session_state.current_project['id'], {"estructura": estructura_actualizada})
                    st.session_state.current_project['estructura'] = estructura_actualizada
                    st.success("Guardado correctamente.")
                    st.rerun()

    # --- FASE C: PROMPTS MAESTROS ---
    with tab3:
        st.subheader("Ingeniería de Instrucciones (Prompts Maestros)")
        est = st.session_state.current_project.get('estructura')
        
        if not est or 'capitulos' not in est:
            st.warning("⚠️ Genera una estructura en la Fase B primero.")
        else:
            for cap in est['capitulos']:
                cap_id = str(cap['nro'])
                with st.expander(f"Configuración: Capítulo {cap_id} - {cap['titulo']}"):
                    kws_secundarias = st.text_input(f"Palabras clave para Fuentes Secundarias (Cap. {cap_id}):", value=cap.get('titulo', ''), key=f"kw_sec_{cap_id}")
                    
                    if st.button(f"➕ Generar variante de Prompt", key=f"btn_p_{cap_id}"):
                        with st.spinner("Diseñando instrucciones..."):
                            ctx_secundario = search_research_data(["Fuentes secundarias"], kws_secundarias)
                            pm = create_master_prompt_for_section(cap, ctx_secundario)
                            
                            prompts_actuales = st.session_state.current_project.get('prompts_maestros') or {}
                            if cap_id in prompts_actuales and isinstance(prompts_actuales[cap_id], str):
                                prompts_actuales[cap_id] = [prompts_actuales[cap_id]]
                            elif cap_id not in prompts_actuales:
                                prompts_actuales[cap_id] = []
                                
                            prompts_actuales[cap_id].append(pm)
                            update_project_data(st.session_state.current_project['id'], {"prompts_maestros": prompts_actuales})
                            st.session_state.current_project['prompts_maestros'] = prompts_actuales
                            st.rerun()
                    
                    prompts_lista = st.session_state.current_project.get('prompts_maestros', {}).get(cap_id, [])
                    if isinstance(prompts_lista, str): prompts_lista = [prompts_lista]
                    
                    if prompts_lista:
                        st.markdown("#### Variantes generadas:")
                        for i, p_actual in enumerate(prompts_lista):
                            col_txt, col_btn = st.columns([11, 1])
                            
                            with col_txt:
                                nuevo_texto = st.text_area(f"Variante {i+1}:", value=p_actual, height=150, key=f"txt_p_{cap_id}_{i}")
                                prompts_lista[i] = nuevo_texto
                                
                            with col_btn:
                                st.write("") 
                                st.write("")
                                if st.button("🗑️", key=f"del_p_{cap_id}_{i}", help="Eliminar esta variante"):
                                    prompts_lista.pop(i)
                                    prompts_actuales = st.session_state.current_project.get('prompts_maestros') or {}
                                    prompts_actuales[cap_id] = prompts_lista
                                    update_project_data(st.session_state.current_project['id'], {"prompts_maestros": prompts_actuales})
                                    st.session_state.current_project['prompts_maestros'] = prompts_actuales
                                    st.success("Variante eliminada.")
                                    st.rerun()

                        if st.button(f"💾 Guardar ediciones", key=f"save_p_{cap_id}"):
                            prompts_actuales = st.session_state.current_project.get('prompts_maestros') or {}
                            prompts_actuales[cap_id] = prompts_lista
                            update_project_data(st.session_state.current_project['id'], {"prompts_maestros": prompts_actuales})
                            st.session_state.current_project['prompts_maestros'] = prompts_actuales
                            st.success("Cambios guardados.")

    # --- FASE D: REFINADOR DE PROMPTS ---
    with tab4:
        st.subheader("Subdivisión y Refinamiento RAG")
        est = st.session_state.current_project.get('estructura')
        prompts = st.session_state.current_project.get('prompts_maestros')
        
        if not est or not prompts:
            st.warning("⚠️ Requiere estructura (Fase B) y Prompts Maestros (Fase C).")
        else:
            st.markdown("Convierte tu Prompt Maestro en múltiples **Sub-prompts** cruzados con tu base de datos para lograr la máxima profundidad.")
            
            col_r1, col_r2 = st.columns(2)
            with col_r1:
                cap_keys_ref = list(prompts.keys())
                cap_sel_ref = st.selectbox("Selecciona Capítulo a refinar:", [f"Capítulo {k}" for k in cap_keys_ref])
                nro_cap_ref = cap_sel_ref.split(" ")[1]
                
                cap_data = next((c for c in est['capitulos'] if str(c['nro']) == nro_cap_ref), None)
                
                variantes_disp = prompts.get(nro_cap_ref, [])
                if isinstance(variantes_disp, str): variantes_disp = [variantes_disp]
                
                if variantes_disp:
                    var_sel_ref = st.selectbox("Prompt maestro base:", [f"Variante {i+1}" for i in range(len(variantes_disp))])
                    prompt_base = variantes_disp[int(var_sel_ref.split(" ")[1]) - 1]
                else:
                    prompt_base = None

            with col_r2:
                tablas_rag = st.multiselect(
                    "Bases de datos RAG para informar el refinamiento:", 
                    ["戰國策", "Xunzi", "Mencio", "JSON de investigación", "Glosas de 鬼谷子", "Fuentes secundarias", "Analectas de Confucio"],
                    key="tablas_rag"
                )
                kws_rag = st.text_input("Palabras clave para extraer RAG:", key="kws_rag")

            if st.button("✂️ Generar Sub-prompts Específicos", type="primary"):
                if not prompt_base or not cap_data:
                    st.error("Faltan datos base.")
                else:
                    with st.spinner("Fragmentando e inyectando contexto RAG..."):
                        contexto_rag = search_research_data(tablas_rag, kws_rag) if tablas_rag and kws_rag else None
                        resultado_refinado = refine_prompt_into_subprompts(cap_data, prompt_base, contexto_rag)
                        
                        prompts_refinados = st.session_state.current_project.get('prompts_refinados') or {}
                        prompts_refinados[nro_cap_ref] = resultado_refinado.get('sub_prompts', [])
                        
                        update_project_data(st.session_state.current_project['id'], {"prompts_refinados": prompts_refinados})
                        st.session_state.current_project['prompts_refinados'] = prompts_refinados
                        st.success("¡Sub-prompts generados con éxito!")
                        st.rerun()

            prefs = st.session_state.current_project.get('prompts_refinados', {}).get(nro_cap_ref, [])
            if prefs:
                st.markdown("#### Lista de Sub-prompts a ejecutar en la Fase E:")
                for i, p in enumerate(prefs):
                    st.info(f"**Sección {i+1}:** {p}")

    # --- FASE E: REDACCIÓN FINAL (MULTISECCIÓN) ---
    with tab5:
        st.subheader("Construcción del Borrador por Secciones")
        prefs_globales = st.session_state.current_project.get('prompts_refinados')
        
        if not prefs_globales:
            st.warning("⚠️ No hay sub-prompts generados. Ve a la Fase D.")
        else:
            st.markdown("Para lograr la máxima extensión, la IA redactará el capítulo sección por sección. Asegúrate de proporcionar las bases de datos relevantes.")
            
            col_e1, col_e2 = st.columns(2)
            with col_e1:
                cap_keys_e = list(prefs_globales.keys())
                cap_sel_e = st.selectbox("Capítulo a construir:", [f"Capítulo {k}" for k in cap_keys_e])
                nro_cap_e = cap_sel_e.split(" ")[1]
                sub_prompts_actuales = prefs_globales[nro_cap_e]

            with col_e2:
                tablas_e = st.multiselect(
                    "Bases de datos para la redacción final:", 
                    ["戰國策", "Xunzi", "Mencio", "JSON de investigación", "Glosas de 鬼谷子", "Fuentes secundarias", "Analectas de Confucio"],
                    key="tablas_e"
                )
                kws_e = st.text_input("Keywords para la redacción:", key="kws_e")

            if st.button(f"🚀 Ejecutar Redacción Completa (Secuencial) - Cap {nro_cap_e}", type="primary"):
                if not tablas_e or not kws_e.strip():
                    st.error("Selecciona bases de datos y keywords.")
                else:
                    texto_acumulado = ""
                    contexto_redaccion = search_research_data(tablas_e, kws_e)
                    
                    progress_bar = st.progress(0)
                    total_subs = len(sub_prompts_actuales)
                    
                    for idx, sp in enumerate(sub_prompts_actuales):
                        with st.spinner(f"Redactando sección {idx+1} de {total_subs}..."):
                            fragmento = execute_section_writing(sp, contexto_redaccion)
                            texto_acumulado += f"\n\n{fragmento}\n\n"
                            progress_bar.progress((idx + 1) / total_subs)
                            time.sleep(1)
                    
                    cont_actual = st.session_state.current_project.get('contenido_redactado') or {}
                    cont_actual[nro_cap_e] = texto_acumulado
                    update_project_data(st.session_state.current_project['id'], {"contenido_redactado": cont_actual})
                    st.session_state.current_project['contenido_redactado'] = cont_actual
                    st.success("¡Capítulo completado!")
                    st.rerun()

            st.divider()
            documento = st.session_state.current_project.get('contenido_redactado', {})
            
            if documento:
                st.markdown("### 📑 Vista de Lectura")
                st.markdown("<div class='document-box'>", unsafe_allow_html=True)
                
                for n in sorted(documento.keys(), key=lambda x: int(x)):
                    txt = documento[n]
                    st.markdown(f"<h2>Capítulo {n}</h2>", unsafe_allow_html=True)
                    st.markdown(txt)
                    st.markdown("<hr>", unsafe_allow_html=True)
                    
                st.markdown("</div>", unsafe_allow_html=True)
