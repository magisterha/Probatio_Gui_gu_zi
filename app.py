import streamlit as st
from supabase import create_client, Client
import json

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
    execute_section_writing
)

# --- 1. CONFIGURACIÓN DE PÁGINA Y BASE DE DATOS ---
st.set_page_config(
    page_title="Investigador de Sinología AI",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inicializar Supabase aquí para manejar la autenticación en la barra lateral
try:
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception as e:
    st.error(f"Error crítico: No se pudo conectar a Supabase. Verifica tus secrets. {e}")
    st.stop()

# Estilo CSS para que el output (Fase D) parezca una monografía real
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

# --- 3. BARRA LATERAL (AUTENTICACIÓN Y PROYECTOS) ---
with st.sidebar:
    st.title("Arquitectura de Tesis")
    
    if not st.session_state.user:
        st.subheader("Acceso Investigador")
        
        # Pestañas para gestionar la cuenta
        tab_login, tab_registro, tab_recuperar = st.tabs(["Entrar", "Registro", "Recuperar"])
        
        # PESTAÑA 1: INICIAR SESIÓN
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
                        st.error("Credenciales incorrectas o error de red.")
        
        # PESTAÑA 2: CREAR CUENTA
        with tab_registro:
            with st.form("register_form"):
                reg_email = st.text_input("Nuevo Email")
                reg_pw = st.text_input("Contraseña (mín. 6 caracteres)", type="password")
                if st.form_submit_button("Crear Cuenta"):
                    try:
                        res = supabase.auth.sign_up({"email": reg_email, "password": reg_pw})
                        st.success("¡Cuenta creada exitosamente! Ya puedes iniciar sesión.")
                    except Exception as e:
                        st.error(f"Error al registrar: {e}")
                        
        # PESTAÑA 3: RECUPERAR CONTRASEÑA
        with tab_recuperar:
            with st.form("recover_form"):
                rec_email = st.text_input("Email de tu cuenta")
                if st.form_submit_button("Enviar enlace de recuperación"):
                    try:
                        supabase.auth.reset_password_email(rec_email)
                        st.success("Si el correo está registrado, recibirás las instrucciones.")
                    except Exception as e:
                        st.error(f"Error: {e}")
    else:
        # --- USUARIO CONECTADO ---
        st.write(f"Investigador: **{st.session_state.user['email']}**")
        st.divider()
        
        # Gestión de Proyectos
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
                        st.warning("El título no puede estar vacío.")
        else:
            # Asignamos el proyecto actual basándonos en la selección
            st.session_state.current_project = next(p for p in proyectos if p['nombre'] == sel)
        
        st.divider()
        if st.button("Cerrar Sesión"):
            supabase.auth.sign_out()
            st.session_state.user = None
            st.session_state.current_project = None
            st.session_state.chat_history = [] # Limpiar historial al salir
            st.rerun()

# --- 4. CUERPO PRINCIPAL (LAS 4 FASES DE INVESTIGACIÓN) ---

if not st.session_state.user:
    st.title("Plataforma de Autoría Asistida")
    st.info("👈 Por favor, inicia sesión o crea una cuenta en la barra lateral para acceder a tu área de trabajo.")
elif not st.session_state.current_project:
    st.title("Área de Trabajo")
    st.info("👈 Selecciona un proyecto existente o crea uno nuevo en la barra lateral para comenzar.")
else:
    st.title(f"📖 {st.session_state.current_project['nombre']}")
    
    # Navegación principal de la tesis
    tab1, tab2, tab3, tab4 = st.tabs([
        "💡 A. Lluvia de Ideas", 
        "🏗️ B. Estructura", 
        "✍️ C. Prompts Maestros", 
        "📜 D. Redacción Final"
    ])

    # --- FASE A: CHAT DE IDEAS ---
    with tab1:
        st.subheader("Exploración Conceptual")
        st.markdown("Utiliza este espacio para debatir ideas generales, por ejemplo, la influencia de los rituales en la corte de Pekín o el concepto de Ren.")
        
        # Mostrar historial
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
            kws = st.text_input("Palabras clave (separadas por comas, ej: virtud, gobierno)", placeholder="virtud, ren, ritual")
        
        enfoque = st.text_area("Enfoque metodológico principal de la tesis:", placeholder="Ej: Analizar la evolución semántica del concepto de virtud...")
        
        if st.button("Diseñar Índice Académico", type="primary"):
            if not tablas_seleccionadas or not kws.strip():
                st.warning("Selecciona al menos una fuente y define palabras clave para evitar ruido en la IA.")
            else:
                with st.spinner("Revisando fuentes en Supabase y estructurando capítulos..."):
                    contexto = search_research_data(tablas_seleccionadas, kws)
                    nueva_estructura = generate_research_structure(contexto, enfoque)
                    
                    if nueva_estructura:
                        update_project_data(st.session_state.current_project['id'], {"estructura": nueva_estructura})
                        st.session_state.current_project['estructura'] = nueva_estructura
                        st.success("¡Estructura generada y guardada con éxito!")
                        st.rerun()
                    else:
                        st.error("Hubo un problema generando la estructura. Revisa los datos de entrada.")
            
        # Mostrar la estructura actual si existe
        est = st.session_state.current_project.get('estructura')
        if est and isinstance(est, dict):
            st.divider()
            st.markdown(f"### Índice Propuesto: {est.get('titulo_tesis', 'Sin Título')}")
            for cap in est.get('capitulos', []):
                with st.expander(f"Capítulo {cap.get('nro', '')}: {cap.get('titulo', '')}"):
                    st.write(f"**Objetivo:** {cap.get('objetivo', '')}")
                    for sub in cap.get('subpuntos', []):
                        st.markdown(f"- {sub}")

    # --- FASE C: PROMPTS MAESTROS ---
    with tab3:
        st.subheader("Ingeniería de Instrucciones (Prompts Maestros)")
        est = st.session_state.current_project.get('estructura')
        
        if not est or not isinstance(est, dict) or 'capitulos' not in est:
            st.warning("⚠️ Necesitas generar y guardar una estructura en la Fase B antes de crear los prompts.")
        else:
            st.markdown("Genera múltiples instrucciones para cada capítulo consultando tus **Fuentes Secundarias** para obtener mejores propuestas de investigación.")
            for cap in est['capitulos']:
                cap_id = str(cap['nro'])
                with st.expander(f"Configuración: Capítulo {cap_id} - {cap['titulo']}"):
                    
                    # 1. Input para buscar en la base de datos antes de generar el prompt
                    kws_secundarias = st.text_input(
                        f"Palabras clave para consultar Fuentes Secundarias (Cap. {cap_id}):", 
                        value=cap.get('titulo', ''), 
                        key=f"kw_sec_{cap_id}"
                    )
                    
                    # 2. Botón para generar una NUEVA variante de prompt
                    if st.button(f"➕ Generar variante de Prompt (Cap. {cap_id})", key=f"btn_p_{cap_id}"):
                        with st.spinner("Consultando literatura secundaria y diseñando instrucciones..."):
                            # Consultamos la BD usando la función importada en el backend
                            ctx_secundario = search_research_data(["Fuentes secundarias"], kws_secundarias)
                            
                            # Generamos el prompt enriquecido
                            pm = create_master_prompt_for_section(cap, ctx_secundario)
                            
                            # Lógica para guardar múltiples prompts (como lista)
                            prompts_actuales = st.session_state.current_project.get('prompts_maestros') or {}
                            
                            # Retrocompatibilidad: Si antes era un string, lo convertimos a lista
                            if cap_id in prompts_actuales and isinstance(prompts_actuales[cap_id], str):
                                prompts_actuales[cap_id] = [prompts_actuales[cap_id]]
                            elif cap_id not in prompts_actuales:
                                prompts_actuales[cap_id] = []
                                
                            prompts_actuales[cap_id].append(pm)
                            
                            # Guardamos en base de datos y sesión
                            update_project_data(st.session_state.current_project['id'], {"prompts_maestros": prompts_actuales})
                            st.session_state.current_project['prompts_maestros'] = prompts_actuales
                            st.rerun()
                    
                    # 3. Mostrar y editar los prompts generados
                    prompts_lista = st.session_state.current_project.get('prompts_maestros', {}).get(cap_id, [])
                    if isinstance(prompts_lista, str): prompts_lista = [prompts_lista] # Retrocompatibilidad
                    
                    if prompts_lista:
                        st.markdown("#### Variantes generadas:")
                        for i, p_actual in enumerate(prompts_lista):
                            # Permitir edición de cada variante
                            nuevo_texto = st.text_area(f"Variante {i+1}:", value=p_actual, height=200, key=f"txt_p_{cap_id}_{i}")
                            prompts_lista[i] = nuevo_texto
                            
                        # Botón para guardar las ediciones manuales
                        if st.button(f"💾 Guardar ediciones manuales (Cap. {cap_id})", key=f"save_p_{cap_id}"):
                            prompts_actuales = st.session_state.current_project.get('prompts_maestros') or {}
                            prompts_actuales[cap_id] = prompts_lista
                            update_project_data(st.session_state.current_project['id'], {"prompts_maestros": prompts_actuales})
                            st.session_state.current_project['prompts_maestros'] = prompts_actuales
                            st.success("Cambios guardados.")

    # --- FASE D: REDACCIÓN FINAL ---
    with tab4:
        st.subheader("Borrador del Documento")
        prompts = st.session_state.current_project.get('prompts_maestros')
        
        if not prompts:
            st.warning("⚠️ No hay prompts maestros generados. Ve a la Fase C.")
        else:
            st.markdown("Selecciona un capítulo, la variante de prompt que deseas usar y las fuentes que la IA debe leer estrictamente.")
            
            col_a, col_b = st.columns(2)
            with col_a:
                cap_keys = list(prompts.keys())
                cap_sel = st.selectbox("Capítulo a redactar:", [f"Capítulo {k}" for k in cap_keys])
                nro_cap = cap_sel.split(" ")[1]
                
                # NUEVO: Selección de la variante del prompt maestro
                variantes_disponibles = prompts.get(nro_cap, [])
                if isinstance(variantes_disponibles, str): variantes_disponibles = [variantes_disponibles]
                
                if variantes_disponibles:
                    opciones_var = [f"Variante {i+1}" for i in range(len(variantes_disponibles))]
                    var_sel = st.selectbox("Prompt maestro a utilizar:", opciones_var)
                    idx_var = opciones_var.index(var_sel)
                    prompt_seleccionado = variantes_disponibles[idx_var]
                else:
                    prompt_seleccionado = None
                    st.error("No hay prompts generados para este capítulo.")

            with col_b:
                tablas_d = st.multiselect(
                    "Bases de datos para este capítulo específico:", 
                    ["戰國策", "Xunzi", "Mencio", "JSON de investigación", "Glosas de 鬼谷子", "Fuentes secundarias", "Analectas de Confucio"],
                    key="tablas_d"
                )
                kws_d = st.text_input("Keywords para la redacción:", key="kws_d")
            
            if st.button(f"Ejecutar Redacción Académica ({cap_sel})", type="primary"):
                if not prompt_seleccionado:
                    st.error("Debes generar al menos una variante de prompt en la Fase C.")
                elif not tablas_d or not kws_d.strip():
                    st.error("Por favor, selecciona al menos una base de datos y palabras clave para fundamentar el texto.")
                else:
                    with st.spinner("Redactando siguiendo lógica de monografía (sin formato chat)..."):
                        ctx_redaccion = search_research_data(tablas_d, kws_d) 
                        # Usamos la variante específica seleccionada
                        texto = execute_section_writing(prompt_seleccionado, ctx_redaccion)
                        
                        cont_actual = st.session_state.current_project.get('contenido_redactado') or {}
                        cont_actual[nro_cap] = texto
                        update_project_data(st.session_state.current_project['id'], {"contenido_redactado": cont_actual})
                        st.session_state.current_project['contenido_redactado'] = cont_actual
                        st.rerun()

            # VISUALIZACIÓN DEL DOCUMENTO
            st.divider()
            documento = st.session_state.current_project.get('contenido_redactado', {})
            
            if documento:
                st.markdown("### 📑 Vista de Lectura")
                # Aquí inyectamos el div con la clase CSS definida arriba para que luzca como papel/documento
                st.markdown("<div class='document-box'>", unsafe_allow_html=True)
                
                # Ordenar los capítulos numéricamente para la lectura
                for n in sorted(documento.keys(), key=lambda x: int(x)):
                    txt = documento[n]
                    st.markdown(f"<h2>Capítulo {n}</h2>", unsafe_allow_html=True)
                    st.markdown(txt)
                    st.markdown("<hr>", unsafe_allow_html=True)
                    
                st.markdown("</div>", unsafe_allow_html=True)
            else:
                st.info("El borrador está vacío. Ejecuta la redacción de un capítulo para verlo aquí.")
