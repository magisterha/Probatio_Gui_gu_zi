import google.generativeai as genai
import json
import re

# --- CONFIGURACIÓN ---
def get_model():
    return genai.GenerativeModel('gemini-2.0-flash')

# --- MÓDULO NUEVO: FUENTES PRIMARIAS Y GLOSAS ---
def chat_with_primary_source(messages, user_input, source_text, notas_marginales=None):
    model = get_model()
    
    # Preparamos las notas marginales para que la IA las lea
    notas_str = ""
    if notas_marginales and len(notas_marginales) > 0:
        lista_notas = "\n".join([f"- {n['texto']}" for n in notas_marginales])
        notas_str = f"\n--- NOTAS MARGINALES DEL INVESTIGADOR ---\n{lista_notas}\n-----------------------------------------\n"
    
    system_instruction = f"""Eres un experto filólogo y comentarista de textos clásicos (glosador).
    REGLAS DE HIERRO:
    1. Tienes un único documento primario de referencia. Debes responder a las preguntas del investigador BASÁNDOTE ESTRICTAMENTE en el texto proporcionado abajo.
    2. El investigador ha tomado 'Notas Marginales' sobre este texto. Úsalas como contexto vital para entender su enfoque y línea de investigación.
    3. Si el usuario te pide analizar una palabra o concepto, busca su aparición en este texto y explica su contexto específico en esta obra.
    4. No inventes información. Si el texto no menciona lo que el usuario pregunta, indícalo claramente.
  
    
    --- TEXTO PRIMARIO DE REFERENCIA ---
    {source_text}
    ------------------------------------
    {notas_str}
    """
    
    prompt_completo = f"INSTRUCCIONES DEL SISTEMA:\n{system_instruction}\n\n--- HISTORIAL DE LA CONVERSACIÓN ---\n"
    for msg in messages:
        rol = "Investigador" if msg["role"] == "user" else "Glosa IA"
        prompt_completo += f"**{rol}**: {msg['content']}\n\n"
        
    prompt_completo += f"**Investigador**: {user_input}\n**Glosa IA**: "
    
    try:
        return model.generate_content(prompt_completo).text
    except Exception as e:
        return f"⚠️ Error en la conexión con la API de Gemini: {str(e)}"

def convert_glosa_to_ficha(chat_history, titulo_fuente):
    model = get_model()
    
    historial_str = "\n".join([f"{m['role']}: {m['content']}" for m in chat_history])
    
    prompt = f"""
    Eres un asistente de investigación académica. 
    Analiza este debate filológico sobre la fuente primaria "{titulo_fuente}":
    
    DEBATE:
    {historial_str}
    
    TAREA:
    Extrae la conclusión principal o el hallazgo filológico más importante y devuélvelo EXACTAMENTE con esta estructura JSON:
    {{
        "texto": "El hallazgo analítico o traducción extraída del debate (máx 5 líneas).",
        "cita_pie": "Nota al pie referenciando la obra: {titulo_fuente}",
        "referencia_bib": "Referencia bibliográfica provisional de la obra: {titulo_fuente}"
    }}
    """
    try:
        response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        datos = json.loads(response.text)
        datos_seguros = {k.lower(): v for k, v in datos.items()}
        return {
            "texto": datos_seguros.get("texto", "No se pudo extraer el texto"), 
            "cita_pie": datos_seguros.get("cita_pie", f"Fuente: {titulo_fuente}"),
            "referencia_bib": datos_seguros.get("referencia_bib", f"{titulo_fuente}")
        }
    except Exception as e:
        return {"texto": "Error de extracción.", "cita_pie": "Error", "referencia_bib": "Error"}

# --- FASE A: IDEAS Y EXTRACCIÓN DE FICHAS ESTRUCTURADAS ---
def chat_with_ideas(messages, user_input, contexto_rag=None):
    model = get_model()
    if contexto_rag:
        ctx_str = f"\n\n--- INICIO DEL CONTEXTO DE BASES DE DATOS (RAG) ---\n{json.dumps(contexto_rag, ensure_ascii=False)}\n--- FIN DEL CONTEXTO RAG ---\n"
    else:
        ctx_str = "\n\n[AVISO CRÍTICO: No se ha proporcionado contexto RAG para esta consulta.]"

    system_instruction = f"""Eres un investigador y tutor de tesis experto en Sinología.
    REGLAS DE HIERRO PARA ESTA CONVERSACIÓN:
    1. CERO ALUCINACIONES: Tienes ESTRICTAMENTE PROHIBIDO usar tu conocimiento general o inventar información. 
    2. DEPENDENCIA TOTAL: Debes responder ÚNICA y EXCLUSIVAMENTE basándote en el "CONTEXTO DE BASES DE DATOS" proporcionado abajo.
    3. CITAS OBLIGATORIAS: Cada afirmación, idea o traducción que des DEBE estar justificada. En el JSON del contexto, la información de la obra, autor o enlace suele estar al final de cada bloque. Debes incluir esa cita exacta en tu respuesta (ej. [Mencio, 2A:1]).
    4. RESPUESTA VACÍA: Si el usuario pregunta algo que no se encuentra en el CONTEXTO RAG proporcionado, no intentes deducirlo. Responde explícitamente: "No hay información en las fuentes consultadas para justificar esta respuesta."
    {ctx_str}"""
    
    prompt_completo = f"INSTRUCCIONES DEL SISTEMA:\n{system_instruction}\n\n--- HISTORIAL DE LA CONVERSACIÓN ---\n"
    for msg in messages:
        rol = "Investigador" if msg["role"] == "user" else "Tutor IA"
        prompt_completo += f"**{rol}**: {msg['content']}\n\n"
        
    prompt_completo += f"**Investigador**: {user_input}\n**Tutor IA**: "
    
    try:
        return model.generate_content(prompt_completo).text
    except Exception as e:
        return f"⚠️ Error: {str(e)}"

def extraer_ficha_de_idea(texto_interaccion, estilo_citacion, contexto_rag=None):
    model = get_model()
    ctx_str = f"\n\nCONTEXTO DE FUENTES:\n{json.dumps(contexto_rag, ensure_ascii=False)}" if contexto_rag else "No hay contexto aportado."
    
    prompt = f"""
    Analiza la siguiente conversación/interacción y extrae o actualiza una ficha de trabajo formal.
    INTERACCIÓN A SINTETIZAR:
    {texto_interaccion}
    {ctx_str}
    
    Devuelve EXACTAMENTE con esta estructura JSON:
    {{
        "texto": "El desarrollo académico de la idea resumida en la interacción (máx 5 líneas).",
        "cita_pie": "La nota al pie formateada en estilo {estilo_citacion}.",
        "referencia_bib": "La referencia bibliográfica completa en estilo {estilo_citacion}."
    }}
    """
    try:
        response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
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
        return {"texto": "Error de extracción.", "cita_pie": "Error", "referencia_bib": "Error"}

def refinar_ficha_con_ia(texto_original, instruccion_usuario, estilo_citacion, contexto_rag=None):
    model = get_model()
    ctx_str = f"\n\nCONTEXTO DE FUENTES:\n{json.dumps(contexto_rag, ensure_ascii=False)}" if contexto_rag else ""
    prompt = f"""
    Refina esta ficha de trabajo siguiendo las instrucciones del investigador.
    FICHA ORIGINAL: {texto_original}
    INSTRUCCIÓN: "{instruccion_usuario}"
    {ctx_str}
    Devuelve EXACTAMENTE JSON con 'texto', 'cita_pie', 'referencia_bib'.
    """
    try:
        response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        return {k.lower(): v for k, v in json.loads(response.text).items()}
    except Exception:
        return {"texto": texto_original, "cita_pie": "Error", "referencia_bib": "Error"}

# --- FASE B/C: SÍNTESIS DE ÍNDICE DESDE FICHAS CON DEBATE PROFUNDO ---
def generar_indice_desde_fichas(fichas_brutas):
    model = get_model()
    fichas_procesadas = []
    for f in fichas_brutas:
        historial = "\n".join([f"{'Investigador' if m['role']=='user' else 'IA'}: {m['content']}" for m in f.get("chat_history", [])])
        fichas_procesadas.append({
            "id_ficha": f["id"], "categoria": f.get("categoria", ""),
            "idea_resumen": f.get("texto", ""), "debate_profundo": historial if historial else "Nota directa."
        })
        
    fichas_str = json.dumps(fichas_procesadas, indent=2, ensure_ascii=False)
    
    prompt = f"""
    Eres un Decano estructurando una tesis doctoral. 
    DEBES leer el debate profundo de cada ficha para entender los matices antes de proponer el índice.
    MATERIAL DE TRABAJO:
    {fichas_str}
    
    Devuelve EXACTAMENTE JSON:
    {{
      "titulo_tesis": "Título sugerido",
      "capitulos": [
        {{ "nro": 1, "titulo": "Título", "objetivo": "Objetivo detallado basado en el debate profundo", "fichas_asociadas": ["ID"] }}
      ]
    }}
    """
    try:
        response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        return json.loads(response.text)
    except Exception:
        return {"titulo_tesis": "Error al generar índice", "capitulos": []}

# --- FASE D: EVALUADOR Y REFINADOR DE PROMPTS ---
def evaluar_y_crear_prompt_inteligente(capitulo, notas_texto):
    model = get_model()
    prompt = f"""
    Eres un Director de Tesis evaluando el material para el Capítulo: "{capitulo['titulo']}". Objetivo: {capitulo['objetivo']}
    NOTAS RECOPILADAS (INCLUYEN DEBATE PROFUNDO): {notas_texto if notas_texto else "Ninguna nota."}
    
    TAREA: Evalúa si el material es suficiente y genera un Prompt Maestro.
    Devuelve EXCLUSIVAMENTE el texto del prompt generado.
    """
    return model.generate_content(prompt).text

# --- FASE E: REDACCIÓN FINAL Y BIBLIOGRAFÍA ---
def execute_final_writing(prompt_maestro, notas_texto, idioma, estilo, estilo_citacion):
    model = get_model()
    prompt_final = f"""
    INSTRUCCIÓN MAESTRA: {prompt_maestro}
    MATERIAL BASE (NOTAS, CITAS Y DEBATE PROFUNDO): {notas_texto}
    
    REQUISITOS: Idioma: {idioma}. Estilo: {estilo}. Citación: {estilo_citacion}. Asegúrate de insertar notas al pie.
    TAREA: Redacta el contenido del capítulo. NO saludes. 
    """
    return model.generate_content(prompt_final).text

def generar_bibliografia_global(contenido_completo, estilo_citacion):
    model = get_model()
    prompt = f"Lee la tesis y extrae/genera una lista bibliográfica en formato {estilo_citacion}.\nTESIS: {contenido_completo}\nDevuelve SOLO la bibliografía formateada."
    return model.generate_content(prompt).text
