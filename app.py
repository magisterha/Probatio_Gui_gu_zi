import streamlit as st
from supabase import create_client, Client
import google.generativeai as genai
import json
import io # Para manejar el archivo en memoria
from docx import Document # Para crear el Word

# --- 1. CONFIGURACIÓN Y DICCIONARIO DE IDIOMAS ---

TRANSLATIONS = {
    "Español": {
        "page_title": "Buscador de 訓詁",
        "main_title": "🏯 Buscador de 訓詁 (Xùngǔ)",
        "desc": "Consulta las 'Glosas de 鬼谷子' y genera análisis con IA.",
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
        "warn_input": "Por favor, introduce al menos un sinograma.",
        "searching": "Buscando '{input}' en 'Glosas de 鬼谷子'...",
        "error_not_found": "No se encontró el sinograma '{input}' en la base de datos.",
        "success_found": "¡Contexto encontrado! ({count} documentos)",
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
        "desc": "查詢「鬼谷子」註釋並透過 AI 生成分析。",
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
        "warn_input": "請輸入至少一個漢字。",
        "searching": "正在「Glosas de 鬼谷子」中搜尋 '{input}'...",
        "error_not_found": "資料庫中找不到漢字 '{input}'。",
        "success_found": "找到上下文！({count} 份文件)",
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
        "desc": "Search 'Glosses of Guiguzi' and generate AI analysis.",
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
        "warn_input": "Please enter at least one character.",
        "searching": "Searching for '{input}' in 'Glosas de 鬼谷子'...",
        "error_not_found": "Character '{input}' not found in database.",
        "success_found": "Context found! ({count} documents)",
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
    # Streamlit devuelve markdown, pero Word necesita texto plano o un parser complejo.
    # Por simplicidad y robustez, insertamos el texto. 
    # (Si la respuesta tiene tablas complejas, esto solo pondrá el texto)
    doc.add_paragraph(contenido)
    
    # Guardar en buffer de memoria (no en disco)
    bio = io.BytesIO()
    doc.save(bio)
    bio.seek(0)
    return bio

# --- 5. INTERFAZ DE USUARIO ---
st.title(T["main_title"])
st.markdown(T["desc"])

with st.form("research_form"):
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
    if not sinograma_input:
        st.warning(T["warn_input"])
    else:
        # A) BÚSQUEDA
        with st.spinner(T["searching"].format(input=sinograma_input)):
            try:
                response = supabase.table('Glosas de 鬼谷子').select("*").execute()
                
                contexto_encontrado = []
                for fila in response.data:
                    contenido_str = json.dumps(fila, ensure_ascii=False)
                    if sinograma_input in contenido_str:
                        contexto_encontrado.append(fila)
                
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
                Role: Expert Sinologist in 'Xungu' (Exegesis) and the Guiguzi text.
                
                TASK:
                Analyze the character(s): "{sinograma_input}".
                User specific request: "{peticion_concreta}"

                RETRIEVED CONTEXT FROM DATABASE (Table: Glosas de 鬼谷子):
                ```json
                {contexto_texto}
                ```

                INSTRUCTIONS:
                1. Base your answer PRIMARILY on the provided JSON context.
                2. If the context contains specific glosses for the Guiguzi, prioritize them.
                3. Desired Output Format: {formato_final}.
                4. RESPONSE LANGUAGE: {idioma_salida}.
                """

                model = genai.GenerativeModel('gemini-2.0-flash') 
                response_ai = model.generate_content(prompt_final)
                
                # C) MOSTRAR RESULTADOS
                st.markdown(f"### {T['result_title']}")
                st.write(response_ai.text)
                
                # D) BOTÓN DE DESCARGA WORD
                # Generamos el archivo en memoria
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
