import google.generativeai as genai
import json
import re

# --- CONFIGURACIÓN ---
def get_model():
    return genai.GenerativeModel('gemini-2.0-flash')

# --- FASE A: IDEAS Y EXTRACCIÓN DE FICHAS ESTRUCTURADAS ---
def chat_with_ideas(messages, user_input, contexto_rag=None):
    model = get_model()
    
    # 1. EMPAQUETADO ESTRICTO DE LA RAG
    if contexto_rag:
        ctx_str = f"\n\n--- INICIO DEL CONTEXTO DE BASES DE DATOS (RAG) ---\n{json.dumps(contexto_rag, ensure_ascii=False)}\n--- FIN DEL CONTEXTO RAG ---\n"
    else:
        ctx_str = "\n\n[AVISO CRÍTICO: No se ha proporcionado contexto RAG para esta consulta.]"

    # 2. INSTRUCCIONES DE HIERRO (ANTI-ALUCINACIÓN Y CITA OBLIGATORIA)
    system_instruction = f"""Eres un investigador y tutor de tesis experto en Sinología.
    
    REGLAS DE HIERRO PARA ESTA CONVERSACIÓN:
    1. CERO ALUCINACIONES: Tienes ESTRICTAMENTE PROHIBIDO usar tu conocimiento general o inventar información. 
    2. DEPENDENCIA TOTAL: Debes responder ÚNICA y EXCLUSIVAMENTE basándote en el "CONTEXTO DE BASES DE DATOS" proporcionado abajo.
    3. CITAS OBLIGATORIAS: Cada afirmación, idea o traducción que des DEBE estar justificada. En el JSON del contexto, la información de la obra, autor o enlace suele estar al final de cada bloque. Debes incluir esa cita exacta en tu respuesta (ej. [Mencio, 2A:1] o [Autor, Año, p. X]).
    4. RESPUESTA VACÍA: Si el usuario pregunta algo que no se encuentra en el CONTEXTO RAG proporcionado, no intentes deducirlo. Responde explícitamente: "No hay información en las fuentes consultadas para justificar esta respuesta."
    5. Usa siempre 'Pekín' con acento.
    {ctx_str}"""
    
    prompt_completo = f"INSTRUCCIONES DEL SISTEMA:\n{system_instruction}\n\n--- HISTORIAL DE LA CONVERSACIÓN ---\n"
    
    for msg in messages:
        rol = "Investigador" if msg["role"] == "user" else "Tutor IA"
        prompt_completo += f"**{rol}**: {msg['content']}\n\n"
        
    prompt_completo += f"**Investigador**: {user_input}\n**Tutor IA**: "
    
    try:
        response = model.generate_content(prompt_completo)
        return response.text
    except Exception as e:
        return f"⚠️ Error en la conexión con la API de Gemini: {str(e)}"

def extraer_ficha_de_idea(texto_interaccion, estilo_citacion, contexto_rag=None):
    model = get_model()
    ctx_str = f"\n\nCONTEXTO DE FUENTES:\n{json.dumps(contexto_rag, ensure_ascii=False)}" if contexto_rag else "No hay contexto de BD aportado."
    
    prompt = f"""
    Eres un asistente de investigación estructurando una base de datos cualitativa.
    Analiza la siguiente conversación/interacción y extrae o actualiza una ficha de trabajo formal.
    
    INTERACCIÓN A SINTETIZAR:
    {texto_interaccion}
    {ctx_str}
    
    TAREA:
    Extrae la información y devuélvela EXACTAMENTE con esta estructura de claves JSON:
    {{
        "texto": "El desarrollo académico de la idea resumida en la interacción (máx 5 líneas).",
        "cita_pie": "La nota al pie formateada en estilo {estilo_citacion}.",
        "referencia_bib": "La referencia bibliográfica completa en estilo {estilo_citacion}."
    }}
    
    Si no hay un libro específico en la interacción, intenta deducirlo del Contexto de Fuentes. Si es imposible, escribe "Referencia pendiente".
    """
    try:
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        datos = json.loads(response.text)
        if isinstance(datos, list): datos = datos[0]
        if "ficha" in datos: datos = datos["ficha"]
        datos_seguros = {k.lower(): v for k, v in datos.items()}
        
        return {
            "texto": datos_seguros.get("texto", response.text), 
            "cita_pie": datos_seguros.get("cita_pie", "Sin cita"),
            "referencia_bib": datos_seguros.get("referencia_bib", "Referencia pendiente")
        }
    except Exception as e:
        return {"texto": "Error de extracción de la IA.", "cita_pie": "Error", "referencia_bib": "Error"}

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
    2. Devuelve los datos EXACTAMENTE con esta estructura JSON:
    {{
        "texto": "El texto modificado y mejorado",
        "cita_pie": "La cita al pie actualizada si aplica",
        "referencia_bib": "La referencia actualizada si aplica"
    }}
    """
    try:
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        datos = json.loads(response.text)
        datos_seguros = {k.lower(): v for k, v in datos.items()}
        return datos_seguros
    except Exception as e:
        return {"texto": texto_original, "cita_pie": "Error al refinar", "referencia_bib": "Error al refinar"}

# --- FASE B/C: SÍNTESIS DE ÍNDICE DESDE FICHAS CON DEBATE PROFUNDO ---
def generar_indice_desde_fichas(fichas_brutas):
    model = get_model()
    
    # PREPARACIÓN: Empaquetamos el resumen de la ficha junto con todo su historial de chat.
    fichas_procesadas = []
    for f in fichas_brutas:
        historial = ""
        for msg in f.get("chat_history", []):
            rol = "Investigador" if msg["role"] == "user" else "Tutor IA"
            historial += f"{rol}: {msg['content']}\n"
            
        fichas_procesadas.append({
            "id_ficha": f["id"],
            "categoria": f.get("categoria", ""),
            "idea_resumen": f.get("texto", ""),
            "debate_profundo": historial if historial else "Nota manual directa sin conversación."
        })
        
    fichas_str = json.dumps(fichas_procesadas, indent=2, ensure_ascii=False)
    
    prompt = f"""
    Eres un Decano de Investigación estructurando una tesis doctoral. 
    Revisa este volcado de ideas recopiladas por el investigador.
    
    ATENCIÓN CRÍTICA: Cada nota contiene una "idea_resumen" breve, pero también el "debate_profundo" (la conversación exacta que originó la idea). 
    DEBES leer el debate profundo de cada ficha para entender los matices, argumentos y conexiones lógicas reales antes de proponer el índice. No te quedes solo en la superficie.
    
    MATERIAL DE TRABAJO:
    {fichas_str}
    
    TAREA:
    Crea un Índice de Tesis estructurado que dé sentido a este material.
    Devuelve los datos EXACTAMENTE con esta estructura JSON:
    {{
      "titulo_tesis": "Título sugerido",
      "capitulos": [
        {{
          "nro": 1,
          "titulo": "Título",
          "objetivo": "Objetivo detallado basado en el debate profundo",
          "fichas_asociadas": ["ID de las fichas que encajan aquí"]
        }}
      ]
    }}
    """
    try:
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        return json.loads(response.text)
    except Exception as e:
        return {"titulo_tesis": "Error al generar índice", "capitulos": []}

# --- FASE D: EVALUADOR Y REFINADOR DE PROMPTS ---
def evaluar_y_crear_prompt_inteligente(capitulo, notas_texto):
    model = get_model()
    prompt = f"""
    Eres un Director de Tesis evaluando el material para el Capítulo: "{capitulo['titulo']}".
    Objetivo: {capitulo['objetivo']}
    
    NOTAS RECOPILADAS (INCLUYEN DEBATE PROFUNDO DE LAS FICHAS): 
    {notas_texto if notas_texto else "Ninguna nota asociada."}
    
    TAREA: Evalúa si el material y el debate son suficientes para redactar el capítulo y genera un Prompt Maestro.
    - Si son suficientes: Instruye a la IA a "Dar coherencia estilística al material SIN inventar información nueva, integrando los matices del debate".
    - Si son insuficientes: Instruye a la IA a "Redactar el capítulo expandiendo la información y desarrollando argumentos para cubrir el vacío".
    
    Devuelve EXCLUSIVAMENTE el texto del prompt generado.
    """
    return model.generate_content(prompt).text

# --- FASE E: REDACCIÓN FINAL Y BIBLIOGRAFÍA ---
def execute_final_writing(prompt_maestro, notas_texto, idioma, estilo, estilo_citacion):
    model = get_model()
    prompt_final = f"""
    INSTRUCCIÓN MAESTRA: {prompt_maestro}
    MATERIAL BASE (NOTAS, CITAS Y DEBATE PROFUNDO): {notas_texto}
    
    REQUISITOS:
    - Idioma: {idioma}
    - Notas de estilo: {estilo if estilo else "Académico formal estándar"}
    - Estilo de Citación: {estilo_citacion}. Asegúrate de insertar las notas al pie dentro del texto usando este formato y respetando las citas indicadas en el material base.
    
    TAREA: Redacta el contenido del capítulo aprovechando toda la profundidad analítica del material base. NO saludes. Escribe directamente el texto académico usando 'Pekín' con acento.
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
