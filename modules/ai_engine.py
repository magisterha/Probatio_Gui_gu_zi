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
    system_instruction = (
        "Eres un tutor de tesis experto en Sinología. Ayudas al usuario a pivotar ideas, "
        "encontrar vacíos de investigación y definir conceptos de Xùngǔ. "
        "Usa siempre 'Pekín' con acento para referirte a la capital. Sé ingenioso y académico."
    )
    
    chat = model.start_chat(history=[])
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
    clean_json = re.sub(r'```json|```', '', response.text).strip()
    return json.loads(clean_json)

# --- FASE C: GENERADOR DE PROMPTS MAESTROS ---
def create_master_prompt_for_section(capitulo, contexto_secundario):
    model = get_model()
    
    if contexto_secundario:
        contexto_str = json.dumps(contexto_secundario, indent=2, ensure_ascii=False)
    else:
        contexto_str = "No se encontraron fuentes secundarias previas. Basa tu propuesta en el conocimiento general."
    
    prompt = f"""
    Eres un Ingeniero de Prompts Académicos experto en Sinología. 
    Tengo un capítulo de tesis titulado: "{capitulo['titulo']}".
    Su objetivo es: "{capitulo['objetivo']}".
    
    REVISIÓN DE FUENTES SECUNDARIAS:
    {contexto_str}
    
    TAREA:
    Identifica debates y enfoques interesantes y genera UN 'Prompt Maestro' directivo.
    El prompt debe exigir:
    1. Tono académico y formal.
    2. Exploración de propuestas basadas en las fuentes.
    3. Referencias a la exégesis (Xùngǔ).
    
    Devuelve estrictamente solo el texto del prompt maestro listo para usarse. Usa 'Pekín' si aplica.
    """
    response = model.generate_content(prompt)
    return response.text

# --- FASE D: REFINADOR DE PROMPTS (NUEVO) ---
def refine_prompt_into_subprompts(capitulo, master_prompt, contexto_rag):
    model = get_model()
    
    contexto_str = json.dumps(contexto_rag, indent=2, ensure_ascii=False) if contexto_rag else "Sin contexto RAG adicional."
    subpuntos_str = "\n".join([f"- {sp}" for sp in capitulo.get('subpuntos', [])])
    
    prompt = f"""
    Eres un Arquitecto de Prompts experto. Para escribir un capítulo doctoral exhaustivo de docenas de páginas, debemos subdividir el trabajo.
    
    CAPÍTULO: {capitulo['titulo']}
    SUBPUNTOS DEL CAPÍTULO:
    {subpuntos_str}
    
    PROMPT MAESTRO ORIGINAL (Reglas generales):
    {master_prompt}
    
    CONTEXTO DE BASES DE DATOS (RAG):
    {contexto_str}
    
    TAREA:
    Divide el Prompt Maestro en una serie secuencial de sub-prompts. 
    Crea 1 sub-prompt específico para redactar una introducción ampliada del capítulo, luego 1 sub-prompt hiper-detallado por cada subpunto mencionado, y finalmente 1 sub-prompt para la conclusión del capítulo.
    
    Cada sub-prompt debe exigir a la IA redactora un desarrollo profundo (al menos 3-4 páginas por sección) y obligarla a citar/integrar el Contexto RAG proporcionado.
    
    Responde EXCLUSIVAMENTE con un objeto JSON (sin formato markdown) con este formato:
    {{
      "sub_prompts": [
        "Prompt detallado para la introducción...",
        "Prompt detallado para el subpunto 1...",
        "Prompt detallado para la conclusión..."
      ]
    }}
    """
    response = model.generate_content(prompt)
    clean_json = re.sub(r'```json|```', '', response.text).strip()
    return json.loads(clean_json)

# --- FASE E: EJECUCIÓN (REDACCIÓN FINAL) ---
def execute_section_writing(prompt_especifico, research_context):
    model = get_model()
    contexto_str = json.dumps(research_context, indent=2, ensure_ascii=False)
    
    prompt_final = f"""
    INSTRUCCIÓN ESPECÍFICA DE REDACCIÓN:
    {prompt_especifico}
    
    CONTEXTO DE INVESTIGACIÓN (Bases de datos / RAG):
    {contexto_str}
    
    REGLA DE ORO: No saludes. Escribe directamente el contenido denso, académico y profundo. Usa 'Pekín' con acento.
    """
    response = model.generate_content(prompt_final)
    return response.text
