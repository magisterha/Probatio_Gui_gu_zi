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
        "desc": "Consulta múltiples fuentes clásicas y genera análisis exegéticos con IA.",
        "db_select": "Bases de datos a consultar",
        "input_char": "Sinograma(s)",
        "input_char_placeholder": "Ej: 粵, 若...",
        "input_req": "Petición concreta",
        "input_req_placeholder": "Ej: Explica el sentido oculto según el texto...",
        "output_format": "Formato de salida",
        "formats": ["Explicación breve (Diccionario)", "Breve ensayo académico", "Explicación detallada", "Otro (Personalizado)"],
        "other_format": "Si elegiste 'Otro', especifica aquí:",
        "other_placeholder": "Ej: Tabla comparativa markdown",
        "resp_lang": "Idioma de la respuesta (IA)",
        "btn_analyze": "🔍 Analizar con Gemini",
        "warn_input": "Por favor, introduce al menos un sinograma y selecciona al menos una base de datos.",
        "searching": "Buscando '{input}' en las fuentes seleccionadas...",
        "error_not_found": "No se encontró el sinograma '{input}' en las bases de datos seleccionadas.",
        "success_found": "¡Contexto encontrado! ({count} documentos en total)",
        "analyzing": "Consultando a Gemini 2.0 Flash...",
        "result_title": "📜 Resultado del Análisis",
        "source_title": "Ver fuentes JSON utilizadas (Evidencia)",
        "btn_download_word": "📥 Descargar Análisis en Word",
        "filename_prefix": "Analisis_Xungu",
        "sidebar_lang": "Idioma de la Interfaz / 介面語言"
    },
    "Traditional Chinese": {
        "page_title": "訓詁搜尋器",
        "main_title": "🏯 訓詁搜尋器 (Xùngǔ)",
        "desc": "查詢多種經典文獻並透過 AI 生成分析。",
        "db_select": "要查詢的資料庫",
        "input_char": "漢字",
        "input_char_placeholder": "例如：粵, 若...",
        "input_req": "具體要求",
        "input_req_placeholder": "例如：解釋此字在文中的隱含意義...",
        "output_format": "輸出格式",
        "formats": ["簡短解釋 (字典)", "學術短文", "詳細解釋", "其他 (自定義)"],
        "other_format": "若選擇「其他」，請在此說明：",
        "other_placeholder": "例如：Markdown 比較表",
        "resp_lang": "回覆語言 (AI)",
        "btn_analyze": "🔍 使用 Gemini 分析",
        "warn_input": "請輸入至少一個漢字，並選擇至少一個資料庫。",
        "searching": "正在所選來源中搜尋 '{input}'...",
        "error_not_found": "在所選資料庫中找不到漢字 '{input}'。",
        "success_found": "找到上下文！(共 {count} 份文件)",
        "analyzing": "正在諮詢 Gemini 2.0 Flash...",
        "result_title": "📜 分析結果",
        "source_title": "查看使用的 JSON 來源 (證據)",
        "btn_download_word": "📥 下載 Word 分析報告",
        "filename_prefix": "Xungu_Analysis",
        "sidebar_lang": "Interface Language / 介面語言"
    },
    "English": {
        "page_title": "Xùngǔ Searcher",
        "main_title": "🏯 Xùngǔ Searcher (Exegesis)",
        "desc": "Search multiple classical sources and generate AI exegesis analysis.",
        "db_select": "Databases to query",
        "input_char": "Character(s)",
        "input_char_placeholder": "E.g.: 粵, 若...",
        "input_req": "Specific Request",
        "input_req_placeholder": "E.g.: Explain the hidden meaning according to the text...",
        "output_format": "Output Format",
        "formats": ["Brief Explanation (Dictionary)", "Short Academic Essay", "Detailed Explanation", "Other (Custom)"],
        "other_format": "If 'Other' selected, specify here:",
        "other_placeholder": "E.g.: Markdown comparison table",
        "resp_lang": "Response Language (AI)",
        "btn_analyze": "🔍 Analyze with Gemini",
        "warn_input": "Please enter at least one character and select at least one database.",
        "searching": "Searching for '{input}' in selected sources...",
        "error_not_found": "Character '{input}' not found in selected databases.",
        "success_found": "Context found! ({count} documents total)",
        "analyzing": "Consulting Gemini 2.0 Flash...",
        "result_title": "📜 Analysis Result",
        "source_title": "View JSON sources used (Evidence)",
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
    # Selector de bases de datos
    tablas_seleccionadas = st.multiselect(
        T["db_select"], 
        options=TABLAS_DISPONIBLES, 
        default=TABLAS_DISPONIBLES # Por defecto selecciona todas, puedes dejarlo vacío 'default=[]' para una hoja totalmente en blanco
    )

    col1, col2 = st.columns([1, 3])
    with col1:
        sinograma_input = st.text_input(T["input_char"], placeholder=T["input_char_placeholder"])
    with col2:
        peticion_concreta = st.text_input(T["input_req"], placeholder=T["input_req_placeholder"])

    tipo_formato = st.selectbox(T["output_format"], options=T["formats"])
    formato_otro = st.text_input(T["other_format"], placeholder=T["other_placeholder"])

    idioma_salida = st.selectbox(
        T["resp_lang"],
        options=["Español", "English", "中文 (Traditional Chinese)", "Français"]
    )

    submitted = st.form_submit_button(T["btn_analyze"])

# --- 6. LÓGICA DEL BACKEND ---
if submitted:
    if not sinograma_input or not tablas_seleccionadas:
        st.warning(T["warn_input"])
    else:
        # A) BÚSQUEDA MULTI-TABLA
        with st.spinner(T["searching"].format(input=sinograma_input)):
            contexto_encontrado = []
            try:
                for tabla in tablas_seleccionadas:
                    response = supabase.table(tabla).select("*").execute()
                    
                    for fila in response.data:
                        contenido_str = json.dumps(fila, ensure_ascii=False)
                        if sinograma_input in contenido_str:
                            # Añadimos la fuente para que la IA sepa de dónde viene
                            contexto_encontrado.append({
                                "Fuente/Tabla": tabla,
                                "Datos": fila
                            })
                
                if not contexto_encontrado:
                    st.error(T["error_not_found"].format(input=sinograma_input))
                    st.stop()
                
                st.success(T["success_found"].format(count=len(contexto_encontrado)))
                
            except Exception as e:
                st.error(f"Error Supabase: {e}")
                st.stop()

        # B) GENERACIÓN
        with st.spinner(T["analyzing"]):
            try:
                contexto_texto = json.dumps(contexto_encontrado, indent=2, ensure_ascii=False)
                formato_final = formato_otro if tipo_formato == T["formats"][3] else tipo_formato

                prompt_final = f"""
                Role: Expert Sinologist in classical Chinese texts and 'Xungu' (Exegesis).
                
                TASK:
                Analyze the character(s): "{sinograma_input}".
                User specific request: "{peticion_concreta}"

                RETRIEVED CONTEXT FROM DATABASES:
                ```json
                {contexto_texto}
                ```

                INSTRUCTIONS:
                1. Base your answer PRIMARILY on the provided JSON context. Make sure to reference the different sources (e.g., Confucius, Mencius, Guiguzi) if they appear in the data.
                2. Synthesize the different meanings across the provided classical texts.
                3. Desired Output Format: {formato_final}.
                4. RESPONSE LANGUAGE: {idioma_salida}.
                """

                model = genai.GenerativeModel('gemini-2.0-flash') 
                response_ai = model.generate_content(prompt_final)
                
                # C) MOSTRAR RESULTADOS
                st.markdown(f"### {T['result_title']}")
                st.write(response_ai.text)
                
                # D) BOTÓN DE DESCARGA WORD
                word_file = crear_word(
                    titulo=T["main_title"], 
                    subtitulo=f"{T['input_char']}: {sinograma_input}", 
                    contenido=response_ai.text
                )
                
                st.download_button(
                    label=T["btn_download_word"],
                    data=word_file,
                    file_name=f"{T['filename_prefix']}_{sinograma_input}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
                
                with st.expander(T["source_title"]):
                    st.json(contexto_encontrado)

            except Exception as e:
                st.error(f"Error Gemini: {e}")
