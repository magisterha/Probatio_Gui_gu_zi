import streamlit as st
from supabase import create_client, Client
import json
import uuid

# Backend modules
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

# Session States
if "user" not in st.session_state: st.session_state.user = None
if "current_project" not in st.session_state: st.session_state.current_project = None
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "fichas" not in st.session_state: st.session_state.fichas = []
if "categorias" not in st.session_state: st.session_state.categorias = ["Ideas Generales", "Conceptos Xùngǔ", "Metodología", "Citas/Fuentes"]

# --- BARRA LATERAL ---
with st.sidebar:
    st.title("Arquitectura de Tesis")
    if not st.session_state.user:
        with st.form("login"):
            email = st.text_input("Email")
            pw = st.text_input("Contraseña", type="password")
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
            if st.session_state.current_project != p_seleccionado:
                st.session_state.current_project = p_seleccionado
                # Cargar fichas guardadas del proyecto
                st.session_state.fichas = p_seleccionado.get('fichas', [])
                st.rerun()
        
        st.divider()
        if st.button("💾 Guardar Fichas en la Nube", type="primary"):
            update_project_data(st.session_state.current_project['id'], {"fichas": st.session_state.fichas})
            st.success("Progreso guardado.")
            
        if st.button("Cerrar Sesión"):
            supabase.auth.sign_out()
            st.session_state.user = None
            st.session_state.current_project = None
            st.session_state.fichas = []
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
    
    st.markdown("**Configuración del Entorno de Ideas:**")
    col_ctrl1, col_ctrl2 = st.columns(2)
    with col_ctrl1:
        estilo_citacion_a = st.selectbox("Estilo de Citación:", ["APA 7", "Chicago (Notas y Bibliografía)", "Harvard", "MLA"], key="estilo_a")
    with col_ctrl2:
        tablas_a = st.multiselect("Bases de datos para consultar en vivo:", ["戰國策", "Xunzi", "Mencio", "JSON de investigación", "Glosas de 鬼谷子", "Fuentes secundarias", "Analectas de Confucio"], key="tablas_a")
        kws_a = st.text_input("Palabras clave para filtrar las fuentes (Opcional):", key="kws_a")

    st.divider()
    col_inputs, col_tablero = st.columns([1, 1.2])
    
    with col_inputs:
        subtab_chat, subtab_manual = st.tabs(["💬 Chat con IA", "✍️ Reflexión Manual"])
        
        with subtab_chat:
            st.markdown("Genera ideas dialogando con el tutor IA.")
            chat_container = st.container(height=400)
            with chat_container:
                for msg in st.session_state.chat_history:
                    with st.chat_message(msg["role"]): st.write(msg["content"])
            
            if prompt := st.chat_input("Discute ideas con la IA..."):
                st.session_state.chat_history.append({"role": "user", "content": prompt})
                with st.spinner("Consultando BD y procesando idea..."):
                    contexto_rag_a = search_research_data(tablas_a, kws_a) if tablas_a else None
                    res = chat_with_ideas(st.session_state.chat_history, prompt, contexto_rag_a)
                    st.session_state.chat_history.append({"role": "assistant", "content": res})
                    
                    datos_ficha = extraer_ficha_de_idea(prompt + " \n Asistente: " + res, estilo_citacion_a, contexto_rag_a)
                    st.session_state.fichas.append({
                        "id": str(uuid.uuid4())[:8], 
                        "texto": datos_ficha.get("texto", "Texto no extraído"), 
                        "cita_pie": datos_ficha.get("cita_pie", ""),
                        "referencia_bib": datos_ficha.get("referencia_bib", ""),
                        "categoria": "Ideas Generales"
                    })
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
                            "cita_pie": cita_manual, "referencia_bib": bib_manual, "categoria": cat_manual
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
                    with st.container():
                        st.markdown(f"<div class='ficha'><b>Nota:</b> {f['texto']}</div>", unsafe_allow_html=True)
                        st.caption(f"📝 {f.get('cita_pie', 'Sin cita')}")
                        st.caption(f"📚 {f.get('referencia_bib', 'Sin bibliografía')}")
                        
                        with st.expander("⚙️ Opciones de ficha"):
                            # MOVER
                            nueva_cat = st.selectbox("Mover ficha a:", st.session_state.categorias, index=st.session_state.categorias.index(cat), key=f"sel_{f['id']}")
                            if nueva_cat != cat:
                                f['categoria'] = nueva_cat
                                st.rerun()
                            st.divider()
                            # EDICIÓN MANUAL
                            st.markdown("**✏️ Edición Manual**")
                            e_txt = st.text_area("Texto:", f['texto'], key=f"etxt_{f['id']}")
                            e_cit = st.text_input("Cita:", f.get('cita_pie', ''), key=f"ecit_{f['id']}")
                            e_bib = st.text_input("Bib:", f.get('referencia_bib', ''), key=f"ebib_{f['id']}")
                            if st.button("💾 Guardar Edición", key=f"save_{f['id']}"):
                                f['texto'] = e_txt; f['cita_pie'] = e_cit; f['referencia_bib'] = e_bib
                                st.rerun()
                            st.divider()
                            # REFINAMIENTO IA
                            st.markdown("**✨ Refinar con IA**")
                            instruccion = st.text_area("¿Qué debe mejorar la IA?", key=f"inst_{f['id']}")
                            if st.button("Ejecutar Refinamiento", key=f"ref_{f['id']}"):
                                if instruccion.strip():
                                    with st.spinner("Refinando..."):
                                        ctx_rag = search_research_data(tablas_a, kws_a) if tablas_a else None
                                        mejora = refinar_ficha_con_ia(f['texto'], instruccion, estilo_citacion_a, ctx_rag)
                                        f['texto'] = mejora.get("texto", f['texto'])
                                        f['cita_pie'] = mejora.get("cita_pie", f.get('cita_pie', ''))
                                        f['referencia_bib'] = mejora.get("referencia_bib", f.get('referencia_bib', ''))
                                        st.rerun()
                            # ELIMINAR
                            if st.button("🗑️ Eliminar Ficha", key=f"del_{f['id']}"):
                                st.session_state.fichas.remove(f)
                                st.rerun()
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
