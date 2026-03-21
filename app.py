import streamlit as st
from supabase import create_client, Client
import json
import uuid

# Módulos personalizados (Backend)
from modules.database import search_research_data, get_user_projects, create_new_project, update_project_data
from modules.ai_engine import (
    chat_with_ideas, extraer_ficha_de_idea, refinar_ficha_con_ia, generar_indice_desde_fichas, 
    evaluar_y_crear_prompt_inteligente, execute_final_writing, generar_bibliografia_global
)
from modules.export_utils import generar_documento_word

st.set_page_config(page_title="Investigador de Sinología AI", layout="wide")

try:
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception as e:
    st.error(f"Error crítico: No se pudo conectar a Supabase. {e}")
    st.stop()

# Estilos CSS
st.markdown("""
    <style>
    .ficha { background-color: #f8f9fa; padding: 15px; border-left: 4px solid #4CAF50; border-radius: 5px; margin-bottom: 5px; color: black; }
    .document-box { background-color: #ffffff; padding: 40px; border: 1px solid #ccc; font-family: 'Times New Roman', Times, serif; line-height: 1.8; color: black; box-shadow: 2px 2px 5px rgba(0,0,0,0.1); }
    </style>
    """, unsafe_allow_html=True)

# Estado de la Sesión
if "user" not in st.session_state: st.session_state.user = None
if "current_project" not in st.session_state: st.session_state.current_project = None
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "fichas" not in st.session_state: st.session_state.fichas = []
if "categorias" not in st.session_state: st.session_state.categorias = ["Ideas Generales", "Conceptos Xùngǔ", "Metodología", "Citas/Fuentes"]
if "active_chat_id" not in st.session_state: st.session_state.active_chat_id = None

# --- BARRA LATERAL ---
with st.sidebar:
    st.title("Arquitectura de Tesis")
    if not st.session_state.user:
        
        # 1. Leer credenciales guardadas en secrets.toml
        creds = st.secrets.get("credenciales", {})
        saved_email = creds.get("email", "")
        saved_pw = creds.get("password", "")
        auto_login = creds.get("auto_login", False)
        
        # 2. Intentar Auto-Login invisible
        if auto_login and saved_email and saved_pw:
            try:
                res = supabase.auth.sign_in_with_password({"email": saved_email, "password": saved_pw})
                st.session_state.user = {"id": res.user.id, "email": res.user.email}
                st.rerun()
            except Exception:
                pass 
                
        # 3. Mostrar el formulario
        if not st.session_state.user:
            with st.form("login"):
                email = st.text_input("Email", value=saved_email)
                pw = st.text_input("Contraseña", type="password", value=saved_pw)
                if st.form_submit_button("Entrar"):
                    try:
                        res = supabase.auth.sign_in_with_password({"email": email, "password": pw})
                        st.session_state.user = {"id": res.user.id, "email": res.user.email}
                        st.rerun()
                    except Exception:
                        st.error("Credenciales incorrectas.")
    else:
        st.write(f"Investigador: **{st.session_state.user['email']}**")
        proyectos = get_user_projects(st.session_state.user['id'])
        nombres = [p['nombre'] for p in proyectos] if proyectos else []
        sel = st.selectbox("Monografías", ["-- Nuevo --"] + nombres)
        
        if sel == "-- Nuevo --":
            with st.form("new_proj"):
                nuevo_n = st.text_input("Título")
                if st.form_submit_button("Crear Proyecto"):
                    create_new_project(st.session_state.user['id'], nuevo_n)
                    st.rerun()
        else:
            p_seleccionado = next(p for p in proyectos if p['nombre'] == sel)
            
            if st.session_state.current_project is None or st.session_state.current_project['id'] != p_seleccionado['id']:
                st.session_state.current_project = p_seleccionado
                st.session_state.fichas = p_seleccionado.get('fichas', []) or []
                st.session_state.active_chat_id = None 
                st.rerun()
        
        st.divider()
        
        if st.button("💾 Guardar Fichas en la Nube", type="primary"):
            try:
                respuesta = update_project_data(st.session_state.current_project['id'], {"fichas": st.session_state.fichas})
                if hasattr(respuesta, 'error') and respuesta.error:
                    st.error(f"Error al guardar: {respuesta.error.message}")
                else:
                    st.success("Progreso guardado correctamente.")
            except Exception as e:
                st.error(f"⚠️ Error. Verifica las columnas en Supabase. Detalles: {e}")
            
        if st.button("Cerrar Sesión"):
            supabase.auth.sign_out()
            st.session_state.user = None
            st.session_state.current_project = None
            st.session_state.fichas = []
            st.session_state.active_chat_id = None
            st.rerun()

if not st.session_state.current_project:
    st.info("👈 Selecciona o crea un proyecto en la barra lateral para empezar.")
    st.stop()

# --- NAVEGACIÓN PRINCIPAL ---
st.title(f"📖 {st.session_state.current_project['nombre']}")
tab1, tab2, tab3, tab4 = st.tabs([
    "💡 A. Entorno de Ideas (Puzzle)", 
    "🏗️ B/C. Organizador de Índices", 
    "⚙️ D. Evaluador de Prompts", 
    "📜 E. Redacción y Exportación"
])

# --- FASE A: CHAT, REFLEXIONES Y TABLERO KANBAN ---
with tab1:
    st.subheader("1. Conversación, Reflexiones y Fichas")
    
    st.markdown("**Configuración del Entorno de Ideas (Para Nuevas Conversaciones):**")
    col_ctrl1, col_ctrl2 = st.columns(2)
    with col_ctrl1:
        estilo_citacion_a = st.selectbox("Estilo de Citación:", ["APA 7", "Chicago (Notas y Bibliografía)", "Harvard", "MLA"], key="estilo_a")
    with col_ctrl2:
        tablas_a = st.multiselect("Bases de datos para consultar en vivo:", ["戰國策", "Xunzi", "Mencio", "JSON de investigación", "Glosas de 鬼谷子", "Fuentes secundarias", "Analectas de Confucio"], key="tablas_a")
        kws_a = st.text_input("Palabras clave para filtrar las fuentes (Opcional):", key="kws_a")

    st.divider()
    col_inputs, col_tablero = st.columns([1, 1.2])
    
    with col_inputs:
        subtab_chat, subtab_manual = st.tabs(["💬 Entorno de Charla", "✍️ Reflexión Manual"])
        
        with subtab_chat:
            st.markdown("**Conversación Activa:**")
            opciones_chat = {"✨ Nueva Conversación (Creará ficha automática)": None}
            for f in st.session_state.fichas:
                titulo_corto = f['texto'][:40] + "..." if len(f['texto']) > 40 else f['texto']
                opciones_chat[f"📄 Ficha: {titulo_corto}"] = f['id']
            
            nombres_opciones = list(opciones_chat.keys())
            ids_opciones = list(opciones_chat.values())
            
            idx_actual = ids_opciones.index(st.session_state.active_chat_id) if st.session_state.active_chat_id in ids_opciones else 0
                
            seleccion = st.selectbox("Selecciona un chat previo o inicia uno nuevo:", nombres_opciones, index=idx_actual, label_visibility="collapsed")
            nuevo_id_activo = opciones_chat[seleccion]
            
            if nuevo_id_activo != st.session_state.active_chat_id:
                st.session_state.active_chat_id = nuevo_id_activo
                st.rerun()

            ficha_activa = next((f for f in st.session_state.fichas if f['id'] == st.session_state.active_chat_id), None) if st.session_state.active_chat_id else None
            historial_actual = ficha_activa.get("chat_history", []) if ficha_activa else []
            
            chat_container = st.container(height=400)
            with chat_container:
                for msg in historial_actual:
                    with st.chat_message(msg["role"]): st.write(msg["content"])
            
            if ficha_activa and len(historial_actual) > 0:
                if st.button("🔄 Sintetizar/Actualizar Ficha con este chat", use_container_width=True):
                    with st.spinner("Releyendo conversación y actualizando ficha..."):
                        chat_text = "\n".join([f"{m['role']}: {m['content']}" for m in historial_actual])
                        # Usamos el RAG anclado para actualizar
                        ctx_rag = ficha_activa.get('contexto_fijado', None)
                        nuevos_datos = extraer_ficha_de_idea(chat_text, estilo_citacion_a, ctx_rag)
                        
                        ficha_activa['texto'] = nuevos_datos.get("texto", ficha_activa['texto'])
                        ficha_activa['cita_pie'] = nuevos_datos.get("cita_pie", ficha_activa.get('cita_pie', ''))
                        ficha_activa['referencia_bib'] = nuevos_datos.get("referencia_bib", ficha_activa.get('referencia_bib', ''))
                        st.success("¡Ficha actualizada!")
                        st.rerun()

            # --- INPUT DEL USUARIO Y ANCLAJE DE CONTEXTO ---
            if prompt := st.chat_input("Discute ideas con la IA..."):
                historial_actual.append({"role": "user", "content": prompt})
                with st.spinner("Procesando consulta y anclando fuentes..."):
                    
                    # 1. EL ANCLAJE DE RAG: Decidimos qué datos pasar a la IA
                    if st.session_state.active_chat_id is None:
                        # Chat Nuevo: Buscamos en toda la base de datos viva
                        contexto_rag_a = search_research_data(tablas_a, kws_a) if tablas_a else None
                    else:
                        # Chat Existente: Recuperamos las fuentes congeladas de esta ficha
                        contexto_rag_a = ficha_activa.get('contexto_fijado', None)

                    # 2. Llamada a la IA con el contexto anclado
                    res = chat_with_ideas(historial_actual[:-1], prompt, contexto_rag_a)
                    historial_actual.append({"role": "assistant", "content": res})
                    
                    # 3. Guardado en la Ficha
                    if st.session_state.active_chat_id is None:
                        chat_text = f"user: {prompt}\nassistant: {res}"
                        datos_ficha = extraer_ficha_de_idea(chat_text, estilo_citacion_a, contexto_rag_a)
                        nuevo_id = str(uuid.uuid4())[:8]
                        st.session_state.fichas.append({
                            "id": nuevo_id, 
                            "texto": datos_ficha.get("texto", "Texto no extraído"), 
                            "cita_pie": datos_ficha.get("cita_pie", ""),
                            "referencia_bib": datos_ficha.get("referencia_bib", ""),
                            "categoria": "Ideas Generales",
                            "chat_history": historial_actual,
                            # AQUI CONGELAMOS EL CONTEXTO EN LA MEMORIA DE LA FICHA
                            "contexto_fijado": contexto_rag_a 
                        })
                        st.session_state.active_chat_id = nuevo_id 
                    else:
                        ficha_activa['chat_history'] = historial_actual

                st.rerun()

        with subtab_manual:
            st.markdown("Introduce tus propias ideas sin intervención de la IA.")
            with st.form("form_nota_manual"):
                txt_manual = st.text_area("Texto de tu reflexión (Requerido):")
                cita_manual = st.text_input("Nota al pie (Opcional):", placeholder="Ej: Smith, 2020, p. 45")
                bib_manual = st.text_input("Referencia Bibliográfica (Opcional):")
                cat_manual = st.selectbox("Categoría:", st.session_state.categorias)
                
                if st.form_submit_button("➕ Añadir al Tablero", type="primary"):
                    if txt_manual.strip():
                        st.session_state.fichas.append({
                            "id": str(uuid.uuid4())[:8], "texto": txt_manual, 
                            "cita_pie": cita_manual, "referencia_bib": bib_manual, "categoria": cat_manual,
                            "chat_history": [],
                            "contexto_fijado": None # Las manuales no tienen RAG anclado
                        })
                        st.success("Reflexión añadida.")
                        st.rerun()
                    else:
                        st.error("El texto no puede estar vacío.")

    with col_tablero:
        st.markdown("### 🧩 Tablero de Fichas (Puzzle)")
        n_cat = st.text_input("Añadir nueva categoría:", placeholder="Ej: Argumentos a favor...")
        if st.button("Crear Categoría") and n_cat:
            if n_cat not in st.session_state.categorias:
                st.session_state.categorias.append(n_cat)
                st.rerun()
                
        for cat in st.session_state.categorias:
            fichas_cat = [f for f in st.session_state.fichas if f['categoria'] == cat]
            with st.expander(f"📁 {cat} ({len(fichas_cat)} fichas)", expanded=True):
                for f in fichas_cat:
                    es_activa = f['id'] == st.session_state.active_chat_id
                    borde_color = "#FF9800" if es_activa else "#4CAF50" 
                    
                    with st.container():
                        st.markdown(f"<div class='ficha' style='border-left: 4px solid {borde_color};'><b>Nota:</b> {f['texto']}</div>", unsafe_allow_html=True)
                        st.caption(f"📝 {f.get('cita_pie', 'Sin cita')}")
                        st.caption(f"📚 {f.get('referencia_bib', 'Sin bibliografía')}")
                        
                        col_btn1, col_btn2 = st.columns(2)
                        with col_btn1:
                            if st.button("💬 Abrir en Chat", key=f"abrir_{f['id']}", use_container_width=True):
                                st.session_state.active_chat_id = f['id']
                                st.rerun()
                        with col_btn2:
                            with st.expander("⚙️ Opciones de ficha"):
                                nueva_cat = st.selectbox("Mover ficha a:", st.session_state.categorias, index=st.session_state.categorias.index(cat), key=f"sel_{f['id']}")
                                if nueva_cat != cat:
                                    f['categoria'] = nueva_cat; st.rerun()
                                st.divider()
                                st.markdown("**✏️ Edición Manual**")
                                e_txt = st.text_area("Texto:", f['texto'], key=f"etxt_{f['id']}")
                                e_cit = st.text_input("Cita:", f.get('cita_pie', ''), key=f"ecit_{f['id']}")
                                e_bib = st.text_input("Bib:", f.get('referencia_bib', ''), key=f"ebib_{f['id']}")
                                if st.button("💾 Guardar Edición", key=f"save_{f['id']}"):
                                    f['texto'] = e_txt; f['cita_pie'] = e_cit; f['referencia_bib'] = e_bib; st.rerun()
                                st.divider()
                                st.markdown("**✨ Refinar con IA**")
                                instruccion = st.text_area("¿Qué debe mejorar la IA?", key=f"inst_{f['id']}")
                                if st.button("Ejecutar Refinamiento", key=f"ref_{f['id']}"):
                                    if instruccion.strip():
                                        with st.spinner("Refinando..."):
                                            # Al refinar, también usamos el RAG anclado
                                            ctx_rag = f.get('contexto_fijado', None)
                                            mejora = refinar_ficha_con_ia(f['texto'], instruccion, estilo_citacion_a, ctx_rag)
                                            f['texto'] = mejora.get("texto", f['texto'])
                                            f['cita_pie'] = mejora.get("cita_pie", f.get('cita_pie', ''))
                                            f['referencia_bib'] = mejora.get("referencia_bib", f.get('referencia_bib', ''))
                                            st.rerun()
                                if st.button("🗑️ Eliminar Ficha", key=f"del_{f['id']}"):
                                    if st.session_state.active_chat_id == f['id']: st.session_state.active_chat_id = None
                                    st.session_state.fichas.remove(f); st.rerun()
                        st.markdown("---")

# --- FASE B/C: ORGANIZADOR DE ÍNDICES Y REPOSITORIO ---
with tab2:
    st.subheader("Organización de Ideas mediante IA")
    if st.button("🧠 Generar Nuevo Índice desde Fichas", type="primary"):
        with st.spinner("Analizando fichas e infiriendo estructura..."):
            nuevo_indice = generar_indice_desde_fichas(st.session_state.fichas)
            repositorio = st.session_state.current_project.get('repositorio_indices', [])
            nuevo_indice['version'] = f"V{len(repositorio)+1} - {st.session_state.current_project['nombre']}"
            repositorio.append(nuevo_indice)
            
            update_project_data(st.session_state.current_project['id'], {"repositorio_indices": repositorio, "estructura_activa": nuevo_indice})
            st.session_state.current_project['repositorio_indices'] = repositorio
            st.session_state.current_project['estructura_activa'] = nuevo_indice
            st.rerun()

    st.divider()
    st.subheader("📚 Repositorio de Versiones")
    repositorio = st.session_state.current_project.get('repositorio_indices', [])
    
    if repositorio:
        opciones_v = [r['version'] for r in repositorio]
        v_sel = st.selectbox("Selecciona la versión de la estructura para trabajar:", opciones_v, index=len(opciones_v)-1)
        indice_activo = next(r for r in repositorio if r['version'] == v_sel)
        st.session_state.current_project['estructura_activa'] = indice_activo
        
        st.markdown(f"### Índice Activo: {indice_activo.get('titulo_tesis', '')}")
        for cap in indice_activo.get('capitulos', []):
            with st.expander(f"Capítulo {cap.get('nro')}: {cap.get('titulo')}"):
                st.write(f"**Objetivo:** {cap.get('objetivo')}")
                st.write("**Fichas vinculadas por la IA:**")
                for fid in cap.get('fichas_asociadas', []):
                    ficha_real = next((f for f in st.session_state.fichas if f['id'] == fid), None)
                    if ficha_real: st.info(ficha_real['texto'])
    else:
        st.info("No hay índices guardados. Genera uno usando el botón superior.")

# --- FASE D: MOTOR DE PROMPTS INTELIGENTE ---
with tab3:
    st.subheader("Evaluación de Coherencia y Prompts")
    indice = st.session_state.current_project.get('estructura_activa')
    
    if not indice:
        st.warning("⚠️ Selecciona o genera una estructura en la Fase B/C.")
    else:
        st.write("El sistema evaluará si las notas en cada capítulo son suficientes o si debe generar texto nuevo.")
        for cap in indice.get('capitulos', []):
            cap_id = str(cap['nro'])
            with st.expander(f"⚙️ Configurar Prompt: Cap {cap_id} - {cap['titulo']}"):
                textos_notas = [f['texto'] for fid in cap.get('fichas_asociadas', []) for f in st.session_state.fichas if f['id'] == fid]
                notas_str = "\n".join(textos_notas)
                
                if st.button(f"🔍 Evaluar Notas y Generar Prompt (Cap {cap_id})"):
                    with st.spinner("Evaluando completitud..."):
                        prompt_generado = evaluar_y_crear_prompt_inteligente(cap, notas_str)
                        prompts_eval = st.session_state.current_project.get('prompts_inteligentes', {})
                        prompts_eval[cap_id] = prompt_generado
                        update_project_data(st.session_state.current_project['id'], {"prompts_inteligentes": prompts_eval})
                        st.session_state.current_project['prompts_inteligentes'] = prompts_eval
                        st.rerun()
                
                p_actual = st.session_state.current_project.get('prompts_inteligentes', {}).get(cap_id, "")
                if p_actual:
                    nuevo_p = st.text_area("Prompt Maestro Evaluado (Editable):", value=p_actual, height=150, key=f"pe_{cap_id}")
                    if st.button("💾 Guardar edición manual", key=f"save_p_{cap_id}"):
                        prompts_eval = st.session_state.current_project.get('prompts_inteligentes', {})
                        prompts_eval[cap_id] = nuevo_p
                        update_project_data(st.session_state.current_project['id'], {"prompts_inteligentes": prompts_eval})
                        st.session_state.current_project['prompts_inteligentes'] = prompts_eval
                        st.success("Guardado.")

# --- FASE E: REDACCIÓN FINAL Y EXPORTACIÓN ---
with tab4:
    st.subheader("Redacción y Ensamblaje Final")
    prompts_eval = st.session_state.current_project.get('prompts_inteligentes', {})
    indice = st.session_state.current_project.get('estructura_activa')
    
    if not prompts_eval or not indice:
        st.warning("⚠️ Faltan prompts generados en la Fase D.")
    else:
        col_c1, col_c2, col_c3 = st.columns(3)
        with col_c1: idioma_sel = st.selectbox("Idioma de Redacción:", ["Español", "Inglés", "Chino Mandarín", "Francés"])
        with col_c2: estilo_citacion_e = st.selectbox("Estilo de Citación:", ["APA 7", "Chicago (Notas y Bibliografía)", "Harvard", "MLA"], key="estilo_e")
        with col_c3: estilo_libre = st.text_area("Comentarios de Estilo (Opcional):", placeholder="Ej: Usa un tono conservador...")

        st.divider()
        cap_sel = st.selectbox("Selecciona capítulo a redactar:", [f"Capítulo {c['nro']}" for c in indice['capitulos']])
        nro_cap_sel = cap_sel.split(" ")[1]
        
        if st.button(f"🚀 Ejecutar Redacción ({cap_sel})", type="primary"):
            with st.spinner("Escribiendo documento académico..."):
                prompt_cap = prompts_eval.get(nro_cap_sel, "")
                cap_data = next((c for c in indice['capitulos'] if str(c['nro']) == nro_cap_sel), {})
                textos_notas = [f"Nota: {f['texto']} \nCita: {f.get('cita_pie','')} " for f in st.session_state.fichas if f['id'] in cap_data.get('fichas_asociadas', [])]
                notas_str = "\n".join(textos_notas)
                
                texto_redactado = execute_final_writing(prompt_cap, notas_str, idioma_sel, estilo_libre, estilo_citacion_e)
                
                cont_actual = st.session_state.current_project.get('contenido_redactado') or {}
                cont_actual[nro_cap_sel] = texto_redactado
                update_project_data(st.session_state.current_project['id'], {"contenido_redactado": cont_actual})
                st.session_state.current_project['contenido_redactado'] = cont_actual
                st.rerun()

        # VISUALIZACIÓN Y EXPORTACIÓN
        documento = st.session_state.current_project.get('contenido_redactado', {})
        if documento:
            st.markdown("### 📑 Vista de Lectura")
            
            if st.button("📚 Generar/Actualizar Bibliografía Final"):
                with st.spinner("Extrayendo citas y formateando bibliografía..."):
                    texto_total = "\n\n".join(documento.values())
                    biblio = generar_bibliografia_global(texto_total, estilo_citacion_e)
                    update_project_data(st.session_state.current_project['id'], {"bibliografia": biblio})
                    st.session_state.current_project['bibliografia'] = biblio
                    st.rerun()

            bibliografia_actual = st.session_state.current_project.get('bibliografia', "")

            st.markdown("<div class='document-box'>", unsafe_allow_html=True)
            for n in sorted(documento.keys(), key=lambda x: int(x)):
                st.markdown(f"<h2>Capítulo {n}</h2>", unsafe_allow_html=True)
                st.markdown(documento[n])
                st.markdown("<hr>", unsafe_allow_html=True)
            
            if bibliografia_actual:
                st.markdown("<h2>Bibliografía</h2>", unsafe_allow_html=True)
                st.markdown(bibliografia_actual)
            st.markdown("</div>", unsafe_allow_html=True)
            
            st.divider()
            archivo_word = generar_documento_word(indice.get('titulo_tesis', 'Monografía'), documento, bibliografia_actual)
            st.download_button(
                label="📥 Descargar Documento en Word (.docx)",
                data=archivo_word,
                file_name=f"{st.session_state.current_project['nombre']}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
