import google.generativeai as genai
import json
import re

# --- CONFIGURACIÓN ---
def get_model():
    return genai.GenerativeModel('gemini-2.0-flash')

# --- FASE A: IDEAS Y EXTRACCIÓN DE FICHAS ESTRUCTURADAS ---
def chat_with_ideas(messages, user_input, contexto_rag=None):
    model = get_model()
    ctx_str = f"\n\nCONTEXTO DE BASES DE DATOS DE APOYO:\n{json.dumps(contexto_rag, ensure_ascii=False)}" if contexto_rag else ""
    system_instruction = (
        "Eres un tutor de tesis experto en Sinología. Ayudas al usuario a pivotar ideas. "
        "Usa siempre 'Pekín' con acento. Sé riguroso y académico." + ctx_str
    )
    chat = model.start_chat(history=[]) 
    response = chat.send_message(f"{system_instruction}\n\nUsuario dice: {user_input}")
    return response.text

def extraer_ficha_de_idea(texto_interaccion, estilo_citacion, contexto_rag=None):
    model = get_model()
    ctx_str = f"\n\nCONTEXTO DE FUENTES:\n{json.dumps(contexto_rag, ensure_ascii=False)}" if contexto_rag else "No hay contexto de BD aportado."
    
    prompt = f"""
    Eres un asistente de investigación estructurando una base de datos cualitativa.
    Analiza la siguiente interacción y extrae una ficha de trabajo formal.
    
    INTERACCIÓN RECIENTE:
    {texto_interaccion}
    {ctx_str}
    
    TAREA:
    Extrae la información en formato JSON estricto con las siguientes TRES claves:
    1. "texto": El desarrollo académico de la idea (máx 5 líneas).
    2. "cita_pie": La nota al pie formateada en estilo {estilo_citacion}.
    3. "referencia_bib": La referencia bibliográfica completa en estilo {estilo_citacion}.
    
    Si no hay un libro específico en la interacción, intenta deducirlo del Contexto de Fuentes. Si es imposible, escribe "Referencia pendiente".
    Responde EXCLUSIVAMENTE con el objeto JSON.
    """
    response = model.generate_content(prompt)
    clean_json = re.sub(r'```json|```', '', response.text).strip()
    try:
        return json.loads(clean_json)
    except json.JSONDecodeError:
        return {"texto": response.text, "cita_pie": "Error de formato.", "referencia_bib": "Error de formato."}

def refinar_ficha_con_ia(texto_original, instruccion_usuario, estilo_citacion, contexto_rag=None):
    model = get_model()
    ctx_str = f"\n\nCONTEXTO DE FUENTES:\n{json.dumps(contexto_rag, ensure_ascii=False)}" if contexto_rag else ""
    
    prompt = f"""
    Eres un asistente de investigación académica. Refina esta ficha de trabajo siguiendo las instrucciones del investigador.
    
    FICHA ORIGINAL: {texto_original}
    INSTRUCCIÓN: "{instruccion_usuario}"
    {ctx_str}
    
    TAREA:
    1. Modifica la ficha para cumplir la instrucción. Mantén concisión (máx 6 líneas).
    2. Devuelve los datos en JSON con: "texto", "cita_pie", "referencia_bib". Usa el estilo {estilo_citacion}.
    Responde EXCLUSIVAMENTE con el objeto JSON.
    """
    response = model.generate_content(prompt)
    clean_json = re.sub(r'```json|```', '', response.text).strip()
    try:
        return json.loads(clean_json)
    except json.JSONDecodeError:
        return {"texto": response.text, "cita_pie": "Error al refinar cita.", "referencia_bib": "Error al refinar referencia."}

# --- FASE B/C: SÍNTESIS DE ÍNDICE DESDE FICHAS ---
def generar_indice_desde_fichas(fichas_categorizadas):
    model = get_model()
    fichas_str = json.dumps(fichas_categorizadas, indent=2, ensure_ascii=False)
    
    prompt = f"""
    Eres un Decano de Investigación. Revisa estas notas y fichas organizadas:
    {fichas_str}
    
    TAREA:
    Crea un Índice de Tesis estructurado que dé sentido a estas notas.
    Responde EXCLUSIVAMENTE con un JSON con este formato exacto:
    {{
      "titulo_tesis": "Título sugerido",
      "capitulos": [
        {{
          "nro": 1,
          "titulo": "Título",
          "objetivo": "Objetivo",
          "fichas_asociadas": ["ID de las fichas que encajan aquí (usa los IDs del JSON proporcionado)"]
        }}
      ]
    }}
    """
    response = model.generate_content(prompt)
    clean_json = re.sub(r'```json|```', '', response.text).strip()
    return json.loads(clean_json)

# --- FASE D: EVALUADOR Y REFINADOR DE PROMPTS ---
def evaluar_y_crear_prompt_inteligente(capitulo, notas_texto):
    model = get_model()
    prompt = f"""
    Eres un Director de Tesis evaluando el material para el Capítulo: "{capitulo['titulo']}".
    Objetivo: {capitulo['objetivo']}
    NOTAS RECOPILADAS: {notas_texto if notas_texto else "Ninguna nota asociada."}
    
    TAREA: Evalúa si las notas son suficientes para redactar el capítulo y genera un Prompt Maestro.
    - Si son suficientes: Instruye a la IA a "Dar coherencia estilística a las notas SIN inventar información nueva".
    - Si son insuficientes: Instruye a la IA a "Redactar el capítulo expandiendo la información y desarrollando argumentos para cubrir el vacío".
    
    Devuelve EXCLUSIVAMENTE el texto del prompt generado.
    """
    return model.generate_content(prompt).text

# --- FASE E: REDACCIÓN FINAL Y BIBLIOGRAFÍA ---
def execute_final_writing(prompt_maestro, notas_texto, idioma, estilo, estilo_citacion):
    model = get_model()
    prompt_final = f"""
    INSTRUCCIÓN MAESTRA: {prompt_maestro}
    MATERIAL BASE (NOTAS): {notas_texto}
    
    REQUISITOS:
    - Idioma: {idioma}
    - Notas de estilo: {estilo if estilo else "Académico formal estándar"}
    - Estilo de Citación: {estilo_citacion}. Asegúrate de insertar las notas al pie dentro del texto usando este formato.
    
    TAREA: Redacta el contenido del capítulo. NO saludes. Escribe directamente el texto académico usando 'Pekín' con acento.
    """
    return model.generate_content(prompt_final).text

def generar_bibliografia_global(contenido_completo, estilo_citacion):
    model = get_model()
    prompt = f"""
    Lee la siguiente tesis completa y extrae/genera una lista bibliográfica en formato {estilo_citacion}.
    TESIS: {contenido_completo}
    Devuelve SOLO la bibliografía formateada en orden alfabético.
    """
    return model.generate_content(prompt).text
