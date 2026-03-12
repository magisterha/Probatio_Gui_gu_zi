import google.generativeai as genai
import streamlit as st
import json
import re

# --- CONFIGURACIÓN ---
def get_model():
    return genai.GenerativeModel('gemini-2.0-flash')

# --- FASE A: IDEAS (CHAT CONVERSACIONAL) ---
def chat_with_ideas(messages, user_input):
    model = get_model()
    # Personalidad de tutor de tesis
    system_instruction = (
        "Eres un tutor de tesis experto en Sinología. Ayudas al usuario a pivotar ideas, "
        "encontrar vacíos de investigación y definir conceptos de Xùngǔ. "
        "Usa siempre 'Pekín' con acento para referirte a la capital. Sé ingenioso y académico."
    )
    
    # Preparamos el historial
    chat = model.start_chat(history=[])
    # En una implementación real, aquí pasarías el historial guardado en messages
    response = chat.send_message(f"{system_instruction}\n\nUsuario dice: {user_input}")
    return response.text

# --- FASE B: GENERADOR DE ESTRUCTURA (JSON) ---
def generate_research_structure(contexto_data, enfoque_usuario):
    model = get_model()
    
    contexto_str = json.dumps(contexto_data, indent=2, ensure_ascii=False)
    
    prompt = f"""
    Eres un Decano de Investigación especializado en estudios clásicos chinos.
    Basándote en los siguientes DATOS DE SUPABASE:
    {contexto_str}
    
    Y en este ENFOQUE: "{enfoque_usuario}"
    
    TAREA:
    Diseña una estructura de monografía doctoral. 
    Responde EXCLUSIVAMENTE con un objeto JSON (sin markdown innecesario) con este formato:
    {{
      "titulo_tesis": "Título académico sugerido",
      "introduccion": "Breve resumen del problema",
      "capitulos": [
        {{
          "nro": 1,
          "titulo": "Título del capítulo",
          "objetivo": "Qué se pretende demostrar",
          "subpuntos": ["Punto A", "Punto B"]
        }}
      ]
    }}
    Usa 'Pekín' si mencionas la capital.
    """
    
    response = model.generate_content(prompt)
    # Limpieza de posibles tags de markdown ```json ... ```
    clean_json = re.sub(r'```json|```', '', response.text).strip()
    return json.loads(clean_json)

# --- FASE C: GENERADOR DE PROMPTS MAESTROS ---
def create_master_prompt_for_section(capitulo, contexto_secundario):
    model = get_model()
    
    # Formateamos el contexto secundario si existe
    if contexto_secundario:
        contexto_str = json.dumps(contexto_secundario, indent=2, ensure_ascii=False)
    else:
        contexto_str = "No se encontraron fuentes secundarias previas. Basa tu propuesta en el conocimiento general de la disciplina."
    
    prompt = f"""
    Eres un Ingeniero de Prompts Académicos experto en Sinología. 
    Tengo un capítulo de tesis titulado: "{capitulo['titulo']}".
    Su objetivo es: "{capitulo['objetivo']}".
    
    REVISIÓN DE FUENTES SECUNDARIAS (Estado de la cuestión):
    {contexto_str}
    
    TAREA:
    Basándote en estas fuentes secundarias, identifica debates, vacíos o enfoques interesantes y genera UN 'Prompt Maestro' detallado para que otra IA redacte este capítulo.
    
    El prompt resultante debe exigir a la IA redactora lo siguiente:
    1. Un tono académico y formal.
    2. Explorar las propuestas de investigación derivadas de las fuentes secundarias mostradas.
    3. Referencias a la exégesis (Xùngǔ) si aplica.
    4. Una estructura de párrafos coherente para una monografía.
    
    Devuelve estrictamente solo el texto del prompt maestro listo para usarse. Usa 'Pekín' si aplica.
    """
    
    response = model.generate_content(prompt)
    return response.text

# --- FASE D: EJECUCIÓN (REDACCIÓN FINAL) ---
def execute_section_writing(master_prompt, research_context):
    model = get_model()
    
    contexto_str = json.dumps(research_context, indent=2, ensure_ascii=False)
    
    prompt_final = f"""
    {master_prompt}
    
    CONTEXTO DE INVESTIGACIÓN DISPONIBLE:
    {contexto_str}
    
    REGLA DE ORO: No saludes, no digas 'Aquí tienes el capítulo'. 
    Escribe directamente el contenido de la tesis como un documento profesional.
    Usa 'Pekín' con acento.
    """
    
    response = model.generate_content(prompt_final)
    return response.text
