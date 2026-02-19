import streamlit as st
from supabase import create_client, Client
import google.generativeai as genai
import json
import io 
from docx import Document 

# --- 1. CONFIGURACIÓN Y DICCIONARIO DE IDIOMAS ---

TRANSLATIONS = {
    "Español": {
        "page_title": "Buscador de 訓詁",
        "main_title": "🏯 Buscador de 訓詁 (Xùngǔ)",
        "desc": "Consulta múltiples fuentes clásicas y genera análisis con IA.",
        "db_select": "Bases de datos a consultar",
        "input_req": "Prompt / Petición",
        "input_req_placeholder": "Ej: Analiza el concepto de virtud en estos textos y compáralos...",
        "resp_lang": "Idioma de la respuesta (IA)",
        "btn_analyze": "🔍 Analizar con Gemini",
        "warn_input": "Por favor, introduce un prompt y selecciona al menos una base de datos.",
        "searching": "Extrayendo información de las fuentes seleccionadas...",
        "error_not_found": "No se encontraron datos en las tablas seleccionadas.",
        "success_found": "¡Contexto cargado correctamente!",
        "analyzing": "Consultando a Gemini 2.0 Flash...",
        "result_title": "📜 Resultado del Análisis",
        "source_title": "Ver datos JSON enviados a la IA",
        "btn_download_word": "📥 Descargar Análisis en Word",
        "filename_prefix": "Analisis_Xungu",
        "sidebar_lang": "Idioma de la Interfaz / 介面語言"
    },
    "Traditional Chinese": {
        "page_title": "訓詁搜尋器",
        "main_title": "🏯 訓詁搜尋器 (Xùngǔ)",
        "desc": "查詢多種經典文獻並透過 AI 生成分析。",
        "db_select": "要查詢的資料庫",
        "input_req": "提示詞 / 具體要求",
        "input_req_placeholder": "例如：分析這些文本中的美德概念並進行比較...",
        "resp_lang": "回覆語言 (AI)",
        "btn_analyze": "🔍 使用 Gemini 分析",
        "warn_input": "請輸入提示詞，並選擇至少一個資料庫。",
        "searching": "正在從所選來源提取資訊...",
        "error_not_found": "在所選資料庫中找不到資料。",
        "success_found": "成功載入上下文！",
        "analyzing": "正在諮詢 Gemini 2.0 Flash...",
        "result_title": "📜 分析結果",
        "source_title": "查看發送給 AI 的 JSON 資料",
        "btn_download_word": "📥 下載 Word 分析報告",
        "filename_prefix": "Xungu_Analysis",
        "sidebar_lang": "Interface Language / 介面語言"
    },
    "English": {
        "page_title": "Xùngǔ Searcher",
        "main_title": "🏯 Xùngǔ Searcher (Exegesis)",
        "desc": "Search multiple classical sources and generate AI exegesis analysis.",
        "db_select": "Databases to query",
        "input_req": "Prompt / Request",
        "input_req_placeholder": "E.g.: Analyze the concept of virtue in these texts and compare them...",
        "resp_lang": "Response Language (AI)",
        "btn_analyze": "🔍 Analyze with Gemini",
        "warn_input": "Please enter a prompt and select at least one database.",
        "searching": "Extracting information from selected sources...",
        "error_not_found": "No data found in the selected databases.",
        "success_found": "Context loaded successfully!",
        "analyzing": "Consulting Gemini 2.0 Flash...",
        "result_title": "📜 Analysis Result",
        "source_title": "View JSON data sent to AI",
        "btn_download_word": "📥 Download Analysis as Word",
        "filename_prefix": "Xungu_Analysis",
        "sidebar_lang": "Interface Language / 介面語言"
    }
}

st.set_page_config(page_title="Sinología AI", layout="centered")

# --- 2. SELECTOR DE IDIOMA (SIDEBAR) ---
idiomas_disponibles = ["Español", "Traditional Chinese", "English"]
lang_sel = st.sidebar.selectbox("Language / Idioma / 語言", idiomas_disponibles)
T = TRANSLATIONS[lang_sel]

# LISTA DE TABLAS DISPONIBLES EN SUPABASE
TABLAS_DISPONIBLES = [
    "Glosas de 鬼谷子",
    "Analectas de Confucio",
    "Fuentes secundarias",
    "JSON de investigación",
    "Mencio",
    "Xunzi",
    "戰國策"
]

# --- 3. CONEXIÓN A SUPABASE Y GEMINI ---
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    genai.configure(api_key=GOOGLE_API_KEY)
except Exception as e:
    st.error(f"Error config: {e}")
    st.stop()

# --- 4. FUNCIÓN HELPER PARA WORD ---
def crear_word(titulo, subtitulo, contenido):
    doc = Document()
    doc.add_heading(titulo, 0)
    doc.add_heading(subtitulo, level=1)
    doc.add_paragraph(contenido)
    
    bio = io.BytesIO()
    doc.save(bio)
    bio.seek(0)
    return bio

# --- 5. INTERFAZ DE USUARIO ---
st.title(T["main_title"])
st.markdown(T["desc"])

with st.form("research_form"):
    # Selector de bases de datos (Vacío por defecto)
    tablas_seleccionadas = st.multiselect(
        T["db_select"], 
        options=TABLAS_DISPONIBLES, 
        default=[] 
    )

    # Área de texto más grande para el prompt
    peticion_concreta = st.text_area(T["input_req"], placeholder=T["input_req_placeholder"], height=100)

    # Selector de idioma de salida
    idioma_salida = st.selectbox(
        T["resp_lang"],
        options=["Español", "English", "中文 (Traditional Chinese)", "Français"]
    )

    submitted = st.form_submit_button(T["btn_analyze"])

# --- 6. LÓGICA DEL BACKEND ---
if submitted:
    if not peticion_concreta or not tablas_seleccionadas:
        st.warning(T["warn_input"])
    else:
        # A) BÚSQUEDA MULTI-TABLA (Extracción completa)
        with st.spinner(T["searching"]):
            contexto_encontrado = []
            try:
                for tabla in tablas_seleccionadas:
                    # Traemos todos los datos de las tablas seleccionadas
                    response = supabase.table(tabla).select("*").execute()
                    
                    if response.data:
                        contexto_encontrado.append({
                            "Fuente/Tabla": tabla,
                            "Datos": response.data
                        })
                
                if not contexto_encontrado:
                    st.error(T["error_not_found"])
                    st.stop()
                
                st.success(T["success_found"])
                
            except Exception as e:
                st.error(f"Error Supabase: {e}")
                st.stop()

        # B) GENERACIÓN
        with st.spinner(T["analyzing"]):
            try:
                contexto_texto = json.dumps(contexto_encontrado, indent=2, ensure_ascii=False)

                prompt_final = f"""
                Role: Expert Sinologist in classical Chinese texts and 'Xungu' (Exegesis).
                
                USER PROMPT / TASK:
                "{peticion_concreta}"

                RETRIEVED CONTEXT FROM DATABASES:
                ```json
                {contexto_texto}
                ```

                INSTRUCTIONS:
                1. Answer the user's prompt based PRIMARILY on the provided JSON context. 
                2. Explicitly cite or reference the specific sources/tables (e.g., Analectas, Mencio, Guiguzi) if they are relevant to your explanation.
                3. RESPONSE LANGUAGE: {idioma_salida}.
                """

                model = genai.GenerativeModel('gemini-2.0-flash') 
                response_ai = model.generate_content(prompt_final)
                
                # C) MOSTRAR RESULTADOS
                st.markdown(f"### {T['result_title']}")
                st.write(response_ai.text)
                
                # D) BOTÓN DE DESCARGA WORD
                word_file = crear_word(
                    titulo=T["main_title"], 
                    subtitulo="Análisis Generado por IA", 
                    contenido=response_ai.text
                )
                
                # Reducimos el prompt a unas pocas palabras para el nombre del archivo
                nombre_archivo_corto = "_".join(peticion_concreta.split()[:3])
                # Limpiamos caracteres que no sean alfanuméricos
                nombre_archivo_seguro = "".join(c for c in nombre_archivo_corto if c.isalnum() or c == '_')
                
                st.download_button(
                    label=T["btn_download_word"],
                    data=word_file,
                    file_name=f"{T['filename_prefix']}_{nombre_archivo_seguro}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
                
                with st.expander(T["source_title"]):
                    st.json(contexto_encontrado)

            except Exception as e:
                st.error(f"Error Gemini: {e}")
