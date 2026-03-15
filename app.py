import streamlit as st
from supabase import create_client, Client
import json
import uuid

# Backend modules
from modules.database import search_research_data, get_user_projects, create_new_project, update_project_data
from modules.ai_engine import (
    chat_with_ideas, extraer_ficha_de_idea, generar_indice_desde_fichas, 
    evaluar_y_crear_prompt_inteligente, execute_final_writing, generar_bibliografia_global
)
from modules.export_utils import generar_documento_word

st.set_page_config(page_title="Investigador de Sinología AI", layout="wide")

try:
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception as e:
    st.error("Error de conexión a BD.")
    st.stop()

# Estilos
st.markdown("""
    <style>
    .ficha { background-color: #f8f9fa; padding: 15px; border-left: 4px solid #4CAF50; border-radius: 5px; margin-bottom: 10px; color: black; }
    .document-box { background-color: #ffffff; padding: 40px; border: 1px solid #ccc; font-family: serif; line-height: 1.8; color: black; }
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
                res = supabase.auth.sign_in_with_password({"email": email, "password": pw})
                st.session_state.user = {"id": res.user.id, "email": res.user.email}
                st.rerun()
    else:
        st.write(f"Investigador: **{st.session_state.user['email']}**")
        proyectos = get_user_projects(st.session_state.user['id'])
        nombres = [p['nombre'] for p in proyectos] if proyectos else []
        sel = st.selectbox("Monografías", ["-- Nuevo --"] + nombres)
        if sel == "-- Nuevo --":
            with st.form("new_proj"):
                nuevo_n = st.text_input("Título")
                if st.form_submit_button("Crear"):
                    create_new_project(st.session_state.user['id'], nuevo_n)
                    st.rerun()
        else:
            p_seleccionado = next(p for p in proyectos if p['nombre'] == sel)
            if st.session_state.current_project != p_seleccionado:
                st.session_state.current_project = p_seleccionado
                st.session_state.fichas = p_seleccionado.get('fichas', [])
                st.rerun()
        
        if st.button("Guardar Fichas en Nube"):
            update_project_data(st.session_state.current_project['id'], {"fichas": st.session_state.fichas})
            st.success("Guardado.")

if not st.session_state.current_project:
    st.info("Selecciona o crea un proyecto para empezar.")
    st.stop()

# --- NAVEGACIÓN PRINCIPAL ---
st.title(f"📖 {st.session_state.current_project['nombre']}")
tab1, tab2, tab3, tab4 = st.tabs([
    "💡 A. Lluvia de Ideas y Fichas", 
    "🏗️ B/C. Organización y Repositorio de Índices", 
    "⚙️ D. Motor de Prompts Inteligente", 
    "📜 E. Redacción y Exportación"
])

# --- FASE A: CHAT Y TABLERO KANBAN DE FICHAS ---
with tab1:
    st.subheader("1. Conversación y Extracción de Fichas")
    col_chat, col_fichas = st.columns([1, 1])
    
    with col_chat:
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]): st.write(msg["content"])
        
        if prompt := st.chat_input("Discute ideas con la IA..."):
            st.session_state.chat_history.append({"role": "user", "content": prompt})
            with st.spinner("Pensando..."):
                res = chat_with_ideas(st.session_state.chat_history, prompt)
                st.session_state.chat_history.append({"role": "assistant", "content": res})
                
                # Extracción automática de ficha
                nueva_ficha_txt = extraer_ficha_de_idea(prompt + " " + res)
                st.session_state.fichas.append({
                    "id": str(uuid.uuid4())[:8], 
                    "texto": nueva_ficha_txt, 
                    "categoria": "Ideas Generales"
                })
            st.rerun()

    with col_fichas:
        st.markdown("### Tablero de Ideas (Fichas)")
        # Nueva categoría
        n_cat = st.text_input("Añadir categoría:")
        if st.button("Crear Categoría") and n_cat:
            if n_cat not in st.session_state.categorias:
                st.session_state.categorias.append(n_cat)
                st.rerun()
                
        # Mostrar Fichas estilo Kanban
        for cat in st.session_state.categorias:
            fichas_cat = [f for f in st.session_state.fichas if f['categoria'] == cat]
            with st.expander(f"📁 {cat} ({len(fichas_cat)})", expanded=True):
                for f in fichas_cat:
                    st.markdown(f"<div class='ficha'>{f['texto']}</div>", unsafe_allow_html=True)
                    nueva_cat = st.selectbox("Mover a:", st.session_state.categorias, index=st.session_state.categorias.index(cat), key=f"sel_{f['id']}")
                    if nueva_cat != cat:
                        f['categoria'] = nueva_cat
                        st.rerun()

# --- FASE B/C: ORGANIZADOR DE ÍNDICES Y REPOSITORIO ---
with tab2:
    st.subheader("Organización de Ideas mediante IA")
    st.write("La IA analizará todas tus fichas categorizadas y propondrá un índice estructurado.")
    
    if st.button("🧠 Generar Nuevo Índice desde Fichas", type="primary"):
        with st.spinner("Analizando fichas e infiriendo estructura..."):
            nuevo_indice = generar_indice_desde_fichas(st.session_state.fichas)
            
            # Guardar en repositorio de versiones
            repositorio = st.session_state.current_project.get('repositorio_indices', [])
            nuevo_indice['version'] = f"V{len(repositorio)+1} - {st.session_state.current_project['nombre']}"
            repositorio.append(nuevo_indice)
            
            update_project_data(st.session_state.current_project['id'], {
                "repositorio_indices": repositorio,
                "estructura_activa": nuevo_indice # El índice actual con el que trabajaremos
            })
            st.session_state.current_project['repositorio_indices'] = repositorio
            st.session_state.current_project['estructura_activa'] = nuevo_indice
            st.success("Índice generado y guardado en el repositorio.")
            st.rerun()

    st.divider()
    st.subheader("📚 Repositorio de Versiones")
    repositorio = st.session_state.current_project.get('repositorio_indices', [])
    
    if repositorio:
        # Selector de versión activa
        opciones_v = [r['version'] for r in repositorio]
        v_sel = st.selectbox("Selecciona la versión de la estructura para trabajar:", opciones_v, index=len(opciones_v)-1)
        indice_activo = next(r for r in repositorio if r['version'] == v_sel)
        st.session_state.current_project['estructura_activa'] = indice_activo
        
        st.markdown(f"### Índice Activo: {indice_activo.get('titulo_tesis', '')}")
        for cap in indice_activo.get('capitulos', []):
            with st.expander(f"Capítulo {cap.get('nro')}: {cap.get('titulo')}"):
                st.write(f"**Objetivo:** {cap.get('objetivo')}")
                st.write("**Fichas vinculadas por la IA:**")
                # Mostrar el contenido de las fichas vinculadas
                fichas_ids = cap.get('fichas_asociadas', [])
                for fid in fichas_ids:
                    ficha_real = next((f for f in st.session_state.fichas if f['id'] == fid), None)
                    if ficha_real: st.info(ficha_real['texto'])
    else:
        st.info("No hay índices guardados. Genera uno arriba.")

# --- FASE D: MOTOR DE PROMPTS INTELIGENTE ---
with tab3:
    st.subheader("Evaluación de Coherencia y Prompts")
    indice = st.session_state.current_project.get('estructura_activa')
    
    if not indice:
        st.warning("⚠️ Selecciona o genera una estructura en la pestaña anterior.")
    else:
        st.write("El sistema evaluará si las notas en cada capítulo son suficientes o si debe generar texto nuevo.")
        for cap in indice.get('capitulos', []):
            cap_id = str(cap['nro'])
            with st.expander(f"⚙️ Configurar Prompt: Cap {cap_id} - {cap['titulo']}"):
                
                # Recopilar texto de fichas asociadas
                textos_notas = []
                for fid in cap.get('fichas_asociadas', []):
                    f = next((f for f in st.session_state.fichas if f['id'] == fid), None)
                    if f: textos_notas.append(f['texto'])
                notas_str = "\n".join(textos_notas)
                
                if st.button(f"🔍 Evaluar Notas y Generar Prompt (Cap {cap_id})"):
                    with st.spinner("Evaluando completitud de la investigación..."):
                        prompt_generado = evaluar_y_crear_prompt_inteligente(cap, notas_str)
                        
                        prompts_eval = st.session_state.current_project.get('prompts_inteligentes', {})
                        prompts_eval[cap_id] = prompt_generado
                        update_project_data(st.session_state.current_project['id'], {"prompts_inteligentes": prompts_eval})
                        st.session_state.current_project['prompts_inteligentes'] = prompts_eval
                        st.rerun()
                
                p_actual = st.session_state.current_project.get('prompts_inteligentes', {}).get(cap_id, "")
                if p_actual:
                    st.text_area("Prompt Maestro Evaluado (Editable):", value=p_actual, height=150, key=f"pe_{cap_id}")

# --- FASE E: REDACCIÓN FINAL Y EXPORTACIÓN ---
with tab4:
    st.subheader("Redacción y Ensamblaje Final")
    prompts_eval = st.session_state.current_project.get('prompts_inteligentes', {})
    indice = st.session_state.current_project.get('estructura_activa')
    
    if not prompts_eval or not indice:
        st.warning("⚠️ Faltan prompts generados en la Fase D.")
    else:
        # Menú de configuración de redacción
        col_c1, col_c2, col_c3 = st.columns(3)
        with col_c1: idioma_sel = st.selectbox("Idioma de Redacción:", ["Español", "Inglés", "Chino Mandarín", "Francés"])
        with col_c2: estilo_citacion = st.selectbox("Estilo de Citación:", ["APA 7", "Chicago (Notas y Bibliografía)", "Harvard", "MLA"])
        with col_c3: estilo_libre = st.text_area("Comentarios de Estilo (Opcional):", placeholder="Ej: Usa un tono muy conservador, evita voz pasiva...")

        st.divider()
        cap_sel = st.selectbox("Selecciona capítulo a redactar:", [f"Capítulo {c['nro']}" for c in indice['capitulos']])
        nro_cap_sel = cap_sel.split(" ")[1]
        
        if st.button(f"🚀 Ejecutar Redacción ({cap_sel})", type="primary"):
            with st.spinner("Escribiendo documento académico..."):
                prompt_cap = prompts_eval.get(nro_cap_sel, "")
                
                # Buscar notas asociadas para pasárselas al redactor
                cap_data = next((c for c in indice['capitulos'] if str(c['nro']) == nro_cap_sel), {})
                textos_notas = [f['texto'] for f in st.session_state.fichas if f['id'] in cap_data.get('fichas_asociadas', [])]
                notas_str = "\n".join(textos_notas)
                
                texto_redactado = execute_final_writing(prompt_cap, notas_str, idioma_sel, estilo_libre, estilo_citacion)
                
                cont_actual = st.session_state.current_project.get('contenido_redactado') or {}
                cont_actual[nro_cap_sel] = texto_redactado
                update_project_data(st.session_state.current_project['id'], {"contenido_redactado": cont_actual})
                st.session_state.current_project['contenido_redactado'] = cont_actual
                st.rerun()

        # VISUALIZACIÓN Y EXPORTACIÓN
        documento = st.session_state.current_project.get('contenido_redactado', {})
        if documento:
            st.markdown("### 📑 Vista de Lectura")
            
            # Generador de bibliografía
            if st.button("📚 Generar/Actualizar Bibliografía Final"):
                with st.spinner("Extrayendo citas y formateando bibliografía..."):
                    texto_total = "\n\n".join(documento.values())
                    biblio = generar_bibliografia_global(texto_total, estilo_citacion)
                    update_project_data(st.session_state.current_project['id'], {"bibliografia": biblio})
                    st.session_state.current_project['bibliografia'] = biblio
                    st.rerun()

            bibliografia_actual = st.session_state.current_project.get('bibliografia', "")

            # Renderizar en pantalla
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
            # Botón de exportación a Word
            archivo_word = generar_documento_word(
                indice.get('titulo_tesis', 'Monografía'), 
                documento, 
                bibliografia_actual
            )
            st.download_button(
                label="📥 Descargar Documento en Word (.docx)",
                data=archivo_word,
                file_name=f"{st.session_state.current_project['nombre']}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
