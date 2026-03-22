import streamlit as st
from supabase import create_client, Client
import json
import uuid
import re

# Módulos personalizados
from modules.database import search_research_data, search_corpus_exact, get_user_projects, create_new_project, update_project_data
from modules.ai_engine import (
    chat_with_ideas, extraer_ficha_de_idea, refinar_ficha_con_ia, generar_indice_desde_fichas, 
    evaluar_y_crear_prompt_inteligente, execute_final_writing, generar_bibliografia_global,
    chat_with_primary_source, convert_glosa_to_ficha
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
    .pergamino { background-color: #fdf6e3; padding: 20px; border: 1px solid #e0d6b8; border-radius: 5px; font-family: 'Times New Roman', Times, serif; color: #333; height: 600px; overflow-y: auto; }
    .snippet-box { background-color: #f8f9fa; padding: 15px; border-radius: 5px; border-left: 4px solid #2196F3; color: black; margin-bottom: 10px;}
    </style>
    """, unsafe_allow_html=True)

# Estado de la Sesión
if "user" not in st.session_state: st.session_state.user = None
if "current_project" not in st.session_state: st.session_state.current_project = None
if "fichas" not in st.session_state: st.session_state.fichas = []
if "fuentes" not in st.session_state: st.session_state.fuentes = []
if "categorias" not in st.session_state: st.session_state.categorias = ["Ideas Generales", "Conceptos Xùngǔ", "Metodología", "Citas/Fuentes", "Análisis de Fuentes"]
if "active_chat_id" not in st.session_state: st.session_state.active_chat_id = None
if "active_source_id" not in st.session_state: st.session_state.active_source_id = None
if "resultados_corpus" not in st.session_state: st.session_state.resultados_corpus = None
if "termino_corpus" not in st.session_state: st.session_state.termino_corpus = ""

# --- BARRA LATERAL ---
with st.sidebar:
    st.title("Arquitectura de Tesis")
    if not st.session_state.user:
        creds = st.secrets.get("credenciales", {})
        saved_email = creds.get("email", "")
        saved_pw = creds.get("password", "")
        auto_login = creds.get("auto_login", False)
        
        if auto_login and saved_email and saved_pw:
            try:
                res = supabase.auth.sign_in_with_password({"email": saved_email, "password": saved_pw})
                st.session_state.user = {"id": res.user.id, "email": res.user.email}
                st.rerun()
            except Exception: pass 
                
        if not st.session_state.user:
            with st.form("login"):
                email = st.text_input("Email", value=saved_email)
                pw = st.text_input("Contraseña", type="password", value=saved_pw)
                if st.form_submit_button("Entrar"):
                    try:
                        res = supabase.auth.sign_in_with_password({"email": email, "password": pw})
                        st.session_state.user = {"id": res.user.id, "email": res.user.email}
                        st.rerun()
                    except Exception: st.error("Credenciales incorrectas.")
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
                st.session_state.fuentes = p_seleccionado.get('fuentes_primarias', []) or []
                st.session_state.active_chat_id = None 
                st.session_state.active_source_id = None
                st.session_state.resultados_corpus = None 
                st.rerun()
        
        st.divider()
        
        if st.button("💾 Guardar Progreso en la Nube", type="primary"):
            try:
                respuesta = update_project_data(st.session_state.current_project['id'], {
                    "fichas": st.session_state.fichas,
                    "fuentes_primarias": st.session_state.fuentes
                })
                if hasattr(respuesta, 'error') and respuesta.error:
                    st.error(f"Error al guardar: {respuesta.error.message}")
                else:
                    st.success("Fichas y Fuentes guardadas correctamente.")
            except Exception as e:
                st.error(f"⚠️ Error al guardar. Detalles: {e}")
            
        if st.button("Cerrar Sesión"):
            supabase.auth.sign_out()
            for key in ["user", "current_project", "fichas", "fuentes", "active_chat_id", "active_source_id", "resultados_corpus"]:
                st.session_state[key] = None if key not in ["fichas", "fuentes"] else []
            st.rerun()

if not st.session_state.current_project:
    st.info("👈 Selecciona o crea un proyecto en la barra lateral para empezar.")
    st.stop()

# --- NAVEGACIÓN PRINCIPAL ---
st.title(f"📖 {st.session_state.current_project['nombre']}")

tab_corpus, tab_fuentes, tab_ideas, tab_indices, tab_prompts, tab_redaccion = st.tabs([
    "🔍 Buscador de Corpus",
    "📚 Fuentes Primarias y Glosas",
    "💡 A. Entorno de Ideas (Puzzle)", 
    "🏗️ B/C. Organizador de Índices", 
    "⚙️ D. Evaluador de Prompts", 
    "📜 E. Redacción y Exportación"
])

# --- NUEVO: BUSCADOR DE CORPUS (CONCORDANCIAS) ---
with tab_corpus:
    st.subheader("🔍 Herramienta de Concordancias (Corpus Lingüístico)")
    st.markdown("Busca apariciones exactas de un término en toda la base de datos y expórtalas al Laboratorio Filológico.")
    
    col_c1, col_c2, col_c3 = st.columns([2, 1.5, 1.5])
    with col_c1:
        tablas_corpus = st.multiselect("Bases de datos a explorar:", ["戰國策", "Xunzi", "Mencio", "Analectas de Confucio", "Glosas de 鬼谷子"], key="tablas_corpus")
    with col_c2:
        col_texto = st.text_input("Nombre de la columna de texto:", value="Texto", help="Asegúrate de que coincide con el nombre en Supabase (ej. Texto, Contenido...)")
    with col_c3:
        termino_busqueda = st.text_input("Término a rastrear:", placeholder="Ej. 情 o páthos")
        
    if st.button("Búsqueda Avanzada", type="primary"):
        if not tablas_corpus or not termino_busqueda:
            st.warning("Selecciona al menos una base de datos y escribe un término.")
        else:
            with st.spinner("Rastreando documentos en milisegundos..."):
                resultados = search_corpus_exact(tablas_corpus, col_texto, termino_busqueda)
                st.session_state.resultados_corpus = resultados
                st.session_state.termino_corpus = termino_busqueda

    # Mostrar resultados guardados en memoria
    if st.session_state.get("resultados_corpus"):
        st.divider()
        st.markdown(f"### 🎯 Resultados encontrados para: **{st.session_state.termino_corpus}**")
        
        for res_tabla in st.session_state.resultados_corpus:
            st.markdown(f"#### 📁 Archivo: {res_tabla['tabla']} ({len(res_tabla['resultados'])} coincidencias)")
            for idx, fila in enumerate(res_tabla['resultados']):
                
                # --- SOLUCIÓN: Búsqueda de columna a prueba de balas ---
                clave_real = next((k for k in fila.keys() if k.lower() == col_texto.lower()), col_texto)
                texto_completo = fila.get(clave_real, "")
                
                if not texto_completo:
                    texto_completo = f"[⚠️ El sistema no encontró texto en la columna '{col_texto}']"
                
                term = st.session_state.termino_corpus
                idx_find = texto_completo.lower().find(term.lower())
                
                start = max(0, idx_find - 200) if idx_find != -1 else 0
                end = min(len(texto_completo), start + len(term) + 400)
                snippet = texto_completo[start:end]
                if start > 0: snippet = "[...] " + snippet
                if end < len(texto_completo): snippet = snippet + " [...]"
                
                snippet_html = re.sub(f"({re.escape(term)})", r"<mark style='background-color: #ffeb3b; color: black; font-weight: bold; padding: 0 3px;'>\1</mark>", snippet, flags=re.IGNORECASE)
                
                with st.container():
                    st.markdown(f"<div class='snippet-box'>{snippet_html}</div>", unsafe_allow_html=True)
                    
                    if st.button(f"📝 Llevar texto completo al Laboratorio Filológico", key=f"exp_corpus_{res_tabla['tabla']}_{fila.get('id', idx)}"):
                        nuevo_id = str(uuid.uuid4())[:8]
                        titulo_fuente = f"Fragmento de {res_tabla['tabla']} (Análisis de '{term}')"
                        st.session_state.fuentes.append({
                            "id_fuente": nuevo_id, 
                            "titulo": titulo_fuente, 
                            "texto_completo": texto_completo, 
                            "chat_history": [], 
                            "notas_marginales": []
                        })
                        st.session_state.active_source_id = nuevo_id
                        st.success("¡Exportado con éxito! Ve a la pestaña 'Fuentes Primarias y Glosas' para comenzar el análisis.")
                    st.markdown("<br>", unsafe_allow_html=True)


# --- MÓDULO: FUENTES PRIMARIAS Y GLOSAS ---
with tab_fuentes:
    st.subheader("Laboratorio Filológico: Análisis de Fuentes Primarias")
    col_arch, col_perg, col_lab = st.columns([1, 2, 1.5])
    
    with col_arch:
        st.markdown("### 🗄️ Archivero")
        nombres_fuentes = {f["titulo"]: f["id_fuente"] for f in st.session_state.fuentes}
        
        if nombres_fuentes:
            opciones = ["-- Seleccionar Fuente --"] + list(nombres_fuentes.keys())
            idx = 0
            if st.session_state.active_source_id:
                try: idx = list(nombres_fuentes.values()).index(st.session_state.active_source_id) + 1
                except: pass
            
            sel_fuente = st.selectbox("Textos en el proyecto:", opciones, index=idx)
            if sel_fuente != "-- Seleccionar Fuente --":
                nuevo_id = nombres_fuentes[sel_fuente]
                if nuevo_id != st.session_state.active_source_id:
                    st.session_state.active_source_id = nuevo_id
                    st.rerun()
            else:
                if st.session_state.active_source_id is not None:
                    st.session_state.active_source_id = None
                    st.rerun()
        else:
            st.info("No hay textos guardados.")

        st.divider()
        with st.expander("➕ Añadir Nuevo Texto", expanded=not bool(nombres_fuentes)):
            with st.form("form_nueva_fuente"):
                t_tit = st.text_input("Título del manuscrito/obra:")
                t_txt = st.text_area("Pega aquí el texto completo (Chino Clásico, traducción, etc):", height=200)
                if st.form_submit_button("Subir Texto"):
                    if t_tit and t_txt:
                        n_id = str(uuid.uuid4())[:8]
                        st.session_state.fuentes.append({
                            "id_fuente": n_id, "titulo": t_tit, "texto_completo": t_txt, 
                            "chat_history": [], "notas_marginales": []
                        })
                        st.session_state.active_source_id = n_id
                        st.success("Texto incorporado.")
                        st.rerun()

    fuente_activa = next((f for f in st.session_state.fuentes if f["id_fuente"] == st.session_state.active_source_id), None)

    with col_perg:
        st.markdown("### 📜 Pergamino de Lectura")
        if fuente_activa:
            st.markdown(f"**{fuente_activa['titulo']}**")
            st.markdown(f"<div class='pergamino'>{fuente_activa['texto_completo'].replace(chr(10), '<br>')}</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div class='pergamino' style='color:#999; text-align:center;'><br><br><br>Selecciona un texto del archivero para comenzar la lectura.</div>", unsafe_allow_html=True)

    with col_lab:
        st.markdown("### 🔬 Laboratorio Filológico")
        if fuente_activa:
            if "notas_marginales" not in fuente_activa:
                fuente_activa["notas_marginales"] = []
                
            tab_chat, tab_notas = st.tabs(["💬 Glosador IA", "📝 Notas Marginales"])
            
            with tab_chat:
                historial_glosa = fuente_activa.get("chat_history", [])
                
                with st.expander("⚙️ Configurar Consulta Comparativa (RAG)"):
                    usar_rag_fuente = st.checkbox("Cruzar análisis con bases de datos externas", value=False)
                    tablas_f = []
                    kws_f = ""
                    if usar_rag_fuente:
                        tablas_f = st.multiselect("Bases de datos:", ["戰國策", "Xunzi", "Mencio", "JSON de investigación", "Glosas de 鬼谷子", "Fuentes secundarias", "Analectas de Confucio"], key="tablas_f")
                        kws_f = st.text_input("Palabras clave (Opcional):", key="kws_f")

                if len(historial_glosa) > 0:
                    if st.button("🎯 Convertir Conversación en Ficha", use_container_width=True, type="primary"):
                        with st.spinner("Sintetizando hallazgo y exportando al Puzzle..."):
                            datos_ficha = convert_glosa_to_ficha(historial_glosa, fuente_activa['titulo'])
                            st.session_state.fichas.append({
                                "id": str(uuid.uuid4())[:8], 
                                "texto": datos_ficha.get("texto", "Análisis extraído"), 
                                "cita_pie": datos_ficha.get("cita_pie", ""),
                                "referencia_bib": datos_ficha.get("referencia_bib", ""),
                                "categoria": "Análisis de Fuentes",
                                "chat_history": historial_glosa.copy(),
                                "contexto_fijado": fuente_activa['texto_completo'] 
                            })
                            fuente_activa["chat_history"] = []
                            st.success("¡Hallazgo exportado a 'A. Entorno de Ideas'!")
                            st.rerun()
                
                chat_container = st.container(height=350)
                with chat_container:
                    for msg in historial_glosa:
                        with st.chat_message(msg["role"]): st.write(msg["content"])
                
                if prompt := st.chat_input("Consulta a la IA sobre el texto..."):
                    historial_glosa.append({"role": "user", "content": prompt})
                    with st.spinner("Analizando texto primario..."):
                        ctx_rag_f = None
                        if usar_rag_fuente and tablas_f:
                            ctx_rag_f = search_research_data(tablas_f, kws_f)

                        res = chat_with_primary_source(historial_glosa[:-1], prompt, fuente_activa['texto_completo'], fuente_activa.get('notas_marginales', []), ctx_rag_f)
                        historial_glosa.append({"role": "assistant", "content": res})
                        fuente_activa['chat_history'] = historial_glosa
                    st.rerun()
            
            with tab_notas:
                st.markdown("Anota traducciones o comentarios personales. La IA leerá estas notas.")
                with st.form("form_nueva_nota"):
                    nueva_nota_txt = st.text_area("Añadir nota al margen:")
                    if st.form_submit_button("Guardar Nota"):
                        if nueva_nota_txt.strip():
                            fuente_activa["notas_marginales"].append({
                                "id": str(uuid.uuid4())[:8],
                                "texto": nueva_nota_txt.strip()
                            })
                            st.rerun()
                
                for nota in fuente_activa["notas_marginales"]:
                    with st.container():
                        col_txt, col_exp, col_del = st.columns([4, 1, 1])
                        with col_txt:
                            st.info(nota["texto"])
                        with col_exp:
                            if st.button("📤", key=f"exp_nota_{nota['id']}", help="Exportar a Entorno de Ideas"):
                                st.session_state.fichas.append({
                                    "id": str(uuid.uuid4())[:8],
                                    "texto": nota["texto"],
                                    "cita_pie": f"Nota marginal sobre manuscrito: {fuente_activa['titulo']}",
                                    "referencia_bib": fuente_activa['titulo'],
                                    "categoria": "Análisis de Fuentes",
                                    "chat_history": [],
                                    "contexto_fijado": fuente_activa['texto_completo']
                                })
                                st.toast("✅ Nota exportada al Puzzle")
                        with col_del:
                            if st.button("🗑️", key=f"del_nota_{nota['id']}", help="Eliminar nota"):
                                fuente_activa["notas_marginales"].remove(nota)
                                st.rerun()

        else:
            st.info("Esperando texto primario...")


# --- FASE A: CHAT, REFLEXIONES Y TABLERO KANBAN ---
with tab_ideas:
    st.subheader("1. Conversación, Reflexiones y Fichas")
    
    st.markdown("**Configuración del Entorno de Ideas:**")
    col_ctrl1, col_ctrl2 = st.columns(2)
    with col_ctrl1:
        estilo_citacion_a = st.selectbox("Estilo de Citación:", ["APA 7", "Chicago (Notas y Bibliografía)", "Harvard", "MLA"], key="estilo_a")
    with col_ctrl2:
        tablas_a = st.multiselect("Bases de datos RAG en la nube:", ["戰國策", "Xunzi", "Mencio", "JSON de investigación", "Glosas de 鬼谷子", "Fuentes secundarias", "Analectas de Confucio"], key="tablas_a")
        kws_a = st.text_input("Palabras clave para filtrar las fuentes en la nube (Opcional):", key="kws_a")

    st.divider()
    col_inputs, col_tablero = st.columns([1, 1.2])
    
    with col_inputs:
        subtab_chat, subtab_manual = st.tabs(["💬 Entorno de Charla", "✍️ Reflexión Manual"])
        
        with subtab_chat:
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

            ficha_activa_a = next((f for f in st.session_state.fichas if f['id'] == st.session_state.active_chat_id), None) if st.session_state.active_chat_id else None
            historial_actual_a = ficha_activa_a.get("chat_history", []) if ficha_activa_a else []
            
            chat_container_a = st.container(height=400)
            with chat_container_a:
                for msg in historial_actual_a:
                    with st.chat_message(msg["role"]): st.write(msg["content"])
            
            if ficha_activa_a and len(historial_actual_a) > 0:
                if st.button("🔄 Sintetizar/Actualizar Ficha con este chat", use_container_width=True):
                    with st.spinner("Releyendo conversación y actualizando ficha..."):
                        chat_text = "\n".join([f"{m['role']}: {m['content']}" for m in historial_actual_a])
                        ctx_rag = ficha_activa_a.get('contexto_fijado', None)
                        nuevos_datos = extraer_ficha_de_idea(chat_text, estilo_citacion_a, ctx_rag)
                        
                        ficha_activa_a['texto'] = nuevos_datos.get("texto", ficha_activa_a['texto'])
                        ficha_activa_a['cita_pie'] = nuevos_datos.get("cita_pie", ficha_activa_a.get('cita_pie', ''))
                        ficha_activa_a['referencia_bib'] = nuevos_datos.get("referencia_bib", ficha_activa_a.get('referencia_bib', ''))
                        st.success("¡Ficha actualizada!")
                        st.rerun()

            if prompt_a := st.chat_input("Discute ideas con la IA (Fase Ideas)..."):
                historial_actual_a.append({"role": "user", "content": prompt_a})
                with st.spinner("Procesando consulta y anclando fuentes..."):
                    if st.session_state.active_chat_id is None:
                        contexto_rag_a = search_research_data(tablas_a, kws_a) if tablas_a else None
                    else:
                        contexto_rag_a = ficha_activa_a.get('contexto_fijado', None)

                    res = chat_with_ideas(historial_actual_a[:-1], prompt_a, contexto_rag_a)
                    historial_actual_a.append({"role": "assistant", "content": res})
                    
                    if st.session_state.active_chat_id is None:
                        chat_text = f"user: {prompt_a}\nassistant: {res}"
                        datos_ficha = extraer_ficha_de_idea(chat_text, estilo_citacion_a, contexto_rag_a)
                        nuevo_id = str(uuid.uuid4())[:8]
                        st.session_state.fichas.append({
                            "id": nuevo_id, 
                            "texto": datos_ficha.get("texto", "Texto no extraído"), 
                            "cita_pie": datos_ficha.get("cita_pie", ""),
                            "referencia_bib": datos_ficha.get("referencia_bib", ""),
                            "categoria": "Ideas Generales",
                            "chat_history": historial_actual_a,
                            "contexto_fijado": contexto_rag_a 
                        })
                        st.session_state.active_chat_id = nuevo_id 
                    else:
                        ficha_activa_a['chat_history'] = historial_actual_a

                st.rerun()

        with subtab_manual:
            with st.form("form_nota_manual"):
                txt_manual = st.text_area("Texto de tu reflexión (Requerido):")
                cita_manual = st.text_input("Nota al pie (Opcional):")
                bib_manual = st.text_input("Referencia Bibliográfica (Opcional):")
                cat_manual = st.selectbox("Categoría:", st.session_state.categorias)
                
                if st.form_submit_button("➕ Añadir al Tablero", type="primary"):
                    if txt_manual.strip():
                        st.session_state.fichas.append({
                            "id": str(uuid.uuid4())[:8], "texto": txt_manual, 
                            "cita_pie": cita_manual, "referencia_bib": bib_manual, "categoria": cat_manual,
                            "chat_history": [], "contexto_fijado": None 
                        })
                        st.success("Reflexión añadida.")
                        st.rerun()

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
                            with st.expander("⚙️ Opciones"):
                                nueva_cat = st.selectbox("Mover a:", st.session_state.categorias, index=st.session_state.categorias.index(cat), key=f"sel_{f['id']}")
                                if nueva_cat != cat:
                                    f['categoria'] = nueva_cat; st.rerun()
                                st.divider()
                                e_txt = st.text_area("Texto:", f['texto'], key=f"etxt_{f['id']}")
                                e_cit = st.text_input("Cita:", f.get('cita_pie', ''), key=f"ecit_{f['id']}")
                                e_bib = st.text_input("Bib:", f.get('referencia_bib', ''), key=f"ebib_{f['id']}")
                                if st.button("💾 Guardar Edición", key=f"save_{f['id']}"):
                                    f['texto'] = e_txt; f['cita_pie'] = e_cit; f['referencia_bib'] = e_bib; st.rerun()
                                st.divider()
                                instruccion = st.text_area("¿Qué debe mejorar la IA?", key=f"inst_{f['id']}")
                                if st.button("Ejecutar Refinamiento", key=f"ref_{f['id']}"):
                                    if instruccion.strip():
                                        with st.spinner("Refinando..."):
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
with tab_indices:
    st.subheader("Organización de Ideas mediante IA")
    if st.button("🧠 Generar Nuevo Índice desde Fichas", type="primary"):
        with st.spinner("Analizando debates profundos e infiriendo estructura..."):
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
        st.info("No hay índices guardados.")

# --- FASE D: MOTOR DE PROMPTS INTELIGENTE ---
with tab_prompts:
    st.subheader("Evaluación de Coherencia y Prompts")
    indice = st.session_state.current_project.get('estructura_activa')
    
    if not indice:
        st.warning("⚠️ Selecciona o genera una estructura en la Fase B/C.")
    else:
        for cap in indice.get('capitulos', []):
            cap_id = str(cap['nro'])
            with st.expander(f"⚙️ Configurar Prompt: Cap {cap_id} - {cap['titulo']}"):
                textos_notas = []
                for fid in cap.get('fichas_asociadas', []):
                    f_real = next((f for f in st.session_state.fichas if f['id'] == fid), None)
                    if f_real:
                        hist = "\n".join([f"{m['role']}: {m['content']}" for m in f_real.get('chat_history', [])])
                        textos_notas.append(f"--- FICHA ---\nResumen: {f_real['texto']}\nDebate original:\n{hist}\n")
                notas_str = "\n".join(textos_notas)
                
                if st.button(f"🔍 Evaluar Material y Generar Prompt (Cap {cap_id})"):
                    with st.spinner("Evaluando completitud del debate..."):
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
with tab_redaccion:
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
            with st.spinner("Escribiendo documento..."):
                prompt_cap = prompts_eval.get(nro_cap_sel, "")
                cap_data = next((c for c in indice['capitulos'] if str(c['nro']) == nro_cap_sel), {})
                
                textos_notas = []
                for f in st.session_state.fichas:
                    if f['id'] in cap_data.get('fichas_asociadas', []):
                        hist = "\n".join([f"{m['role']}: {m['content']}" for m in f.get('chat_history', [])])
                        textos_notas.append(f"--- FICHA ---\nResumen principal: {f['texto']}\nCita: {f.get('cita_pie','')}\nDesarrollo profundo:\n{hist}\n")
                notas_str = "\n".join(textos_notas)
                
                texto_redactado = execute_final_writing(prompt_cap, notas_str, idioma_sel, estilo_libre, estilo_citacion_e)
                
                cont_actual = st.session_state.current_project.get('contenido_redactado') or {}
                cont_actual[nro_cap_sel] = texto_redactado
                update_project_data(st.session_state.current_project['id'], {"contenido_redactado": cont_actual})
                st.session_state.current_project['contenido_redactado'] = cont_actual
                st.rerun()

        documento = st.session_state.current_project.get('contenido_redactado', {})
        if documento:
            st.markdown("### 📑 Vista de Lectura")
            
            if st.button("📚 Generar/Actualizar Bibliografía Final"):
                with st.spinner("Formateando bibliografía..."):
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
