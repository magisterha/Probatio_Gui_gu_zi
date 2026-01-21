import streamlit as st
from supabase import create_client, Client
import google.generativeai as genai
import json

# --- 1. CONFIGURACIÓN INICIAL ---
st.set_page_config(page_title="Sinología AI", layout="centered")

# Recuperar claves de los secretos de Streamlit
# Asegúrate de configurar esto en el panel de Streamlit Cloud
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    
    # Iniciar clientes
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    genai.configure(api_key=GOOGLE_API_KEY)
except Exception as e:
    st.error(f"Error de configuración de secretos: {e}")
    st.stop()

# --- 2. INTERFAZ DE USUARIO (FRONTEND) ---
st.title("🏯 Asistente de Investigación Sinológica")
st.markdown("Busca un sinograma en la base de datos de textos clásicos (Supabase) y genera un análisis con IA (Gemini 2.0 Flash).")

with st.form("research_form"):
    # Input 1: El Sinograma
    col1, col2 = st.columns([1, 3])
    with col1:
        sinograma_input = st.text_input("Sinograma(s)", placeholder="Ej: 粵, 若...")
    with col2:
        # Input 2: Petición concreta
        peticion_concreta = st.text_input(
            "Petición concreta", 
            placeholder="Ej: Compara la visión de Tao Hongjing con la de Yin Tongyang"
        )

    # Input 3: Formato de Salida
    tipo_formato = st.selectbox(
        "Formato de salida",
        options=[
            "Explicación breve (Diccionario)",
            "Breve ensayo académico",
            "Explicación detallada de la consulta",
            "Otro (Personalizado)"
        ]
    )
    
    formato_otro = st.text_input("Si elegiste 'Otro', especifica aquí:", placeholder="Ej: Tabla comparativa markdown")

    # Input 4: Idioma
    idioma_salida = st.selectbox(
        "Responder en",
        options=["Español", "English", "中文 (Chino)", "Français"]
    )

    submitted = st.form_submit_button("🔍 Analizar con Gemini")

# --- 3. LÓGICA DEL BACKEND ---
if submitted:
    if not sinograma_input:
        st.warning("Por favor, introduce al menos un sinograma.")
    else:
        # A) BÚSQUEDA EN SUPABASE (Retrieval)
        with st.spinner(f"Buscando '{sinograma_input}' en documentos..."):
            try:
                # Traemos todos los textos para filtrar en Python (para piloto)
                response = supabase.table('textos_clasicos').select("*").execute()
                
                contexto_encontrado = []
                for fila in response.data:
                    # Convertimos a string para buscar el caracter fácil
                    contenido_str = json.dumps(fila['contenido'], ensure_ascii=False)
                    if sinograma_input in contenido_str:
                        contexto_encontrado.append(fila['contenido'])
                
                if not contexto_encontrado:
                    st.error(f"No se encontró el sinograma '{sinograma_input}' en la base de datos.")
                    st.stop() # Detenemos si no hay datos
                
                st.success(f"¡Contexto encontrado! ({len(contexto_encontrado)} documentos)")
                
            except Exception as e:
                st.error(f"Error conectando a Supabase: {e}")
                st.stop()

        # B) GENERACIÓN CON GEMINI (Generation)
        with st.spinner("Consultando a Gemini 2.0 Flash..."):
            try:
                # Preparamos los datos recuperados como texto
                contexto_texto = json.dumps(contexto_encontrado, indent=2, ensure_ascii=False)
                formato_final = formato_otro if tipo_formato == "Otro (Personalizado)" else tipo_formato

                # Construimos el Prompt
                prompt_final = f"""
                Actúa como un sinólogo experto.
                
                TAREA:
                Interpretar el sinograma o sinogramas: "{sinograma_input}".
                Petición específica del usuario: "{peticion_concreta}"

                CONTEXTO RECUPERADO DE LA BASE DE DATOS (JSON):
                ```json
                {contexto_texto}
                ```

                INSTRUCCIONES:
                1. Basa tu respuesta EXCLUSIVAMENTE en el contexto proporcionado arriba. Si la información no está en el JSON, indícalo.
                2. Formato de salida deseado: {formato_final}.
                3. Idioma de la respuesta: {idioma_salida}.
                """

                # Llamada al modelo
                # Nota: Asegúrate que el nombre del modelo es correcto para tu acceso.
                # Si 'gemini-2.0-flash' da error, prueba 'gemini-1.5-flash' o 'gemini-pro'.
                model = genai.GenerativeModel('gemini-2.0-flash') 
                
                response_ai = model.generate_content(prompt_final)
                
                # Mostrar resultado
                st.markdown("### 📜 Resultado del Análisis")
                st.write(response_ai.text)
                
                # Expandible para ver qué datos usó realmente (Transparencia RAG)
                with st.expander("Ver fuentes JSON utilizadas"):
                    st.json(contexto_encontrado)

            except Exception as e:
                st.error(f"Error al llamar a Gemini: {e}")
