import google.generativeai as genai
import json
import re

def get_model():
    return genai.GenerativeModel('gemini-2.0-flash')

# --- FASE A: IDEAS Y EXTRACCIÓN DE FICHAS ---
def chat_with_ideas(messages, user_input):
    model = get_model()
    system_instruction = (
        "Eres un tutor de tesis experto en Sinología. Ayudas al usuario a pivotar ideas. "
        "Usa siempre 'Pekín' con acento. Sé académico."
    )
    chat = model.start_chat(history=[])
    response = chat.send_message(f"{system_instruction}\n\nUsuario dice: {user_input}")
    return response.text

def extraer_ficha_de_idea(texto_idea):
    model = get_model()
    prompt = f"Resume la siguiente idea de investigación en un concepto clave de máximo 3 líneas para una ficha de trabajo:\n\n{texto_idea}"
    return model.generate_content(prompt).text

# --- FASE B: SÍNTESIS DE ÍNDICE DESDE FICHAS ---
def generar_indice_desde_fichas(fichas_categorizadas):
    model = get_model()
    fichas_str = json.dumps(fichas_categorizadas, indent=2, ensure_ascii=False)
    
    prompt = f"""
    Eres un Decano de Investigación. Revisa estas notas y fichas organizadas por el investigador:
    {fichas_str}
    
    TAREA:
    Crea un Índice de Tesis estructurado que dé sentido a estas notas.
    Responde EXCLUSIVAMENTE con un JSON:
    {{
      "titulo_tesis": "Título sugerido",
      "capitulos": [
        {{
          "nro": 1,
          "titulo": "Título",
          "objetivo": "Objetivo",
          "fichas_asociadas": ["ID de las fichas que encajan aquí"]
        }}
      ]
    }}
    """
    response = model.generate_content(prompt)
    clean_json = re.sub(r'```json|```', '', response.text).strip()
    return json.loads(clean_json)

# --- FASE D: EVALUADOR Y REFINADOR DE PROMPTS (FUSIÓN) ---
def evaluar_y_crear_prompt_inteligente(capitulo, notas_texto):
    model = get_model()
    
    prompt = f"""
    Eres un Director de Tesis evaluando el material para el Capítulo: "{capitulo['titulo']}".
    Objetivo del capítulo: {capitulo['objetivo']}
    
    NOTAS DEL INVESTIGADOR RECOPILADAS PARA ESTE CAPÍTULO:
    {notas_texto if notas_texto else "Ninguna nota asociada."}
    
    TAREA:
    1. Evalúa si las notas aportadas son suficientes para redactar el capítulo completo.
    2. Genera un Prompt Maestro para la IA redactora.
    
    REGLAS DEL PROMPT A GENERAR:
    - Si las notas son suficientes: El prompt debe instruir ESTRICTAMENTE a la IA redactora a "Dar coherencia estilística y académica a las notas aportadas SIN inventar información nueva".
    - Si las notas son insuficientes o vacías: El prompt debe instruir a la IA a "Redactar el capítulo expandiendo la información, buscando contexto general y desarrollando argumentos para cubrir el vacío".
    
    Devuelve EXCLUSIVAMENTE el texto del prompt generado, listo para usar.
    """
    return model.generate_content(prompt).text

# --- FASE E: REDACCIÓN FINAL Y BIBLIOGRAFÍA ---
def execute_final_writing(prompt_maestro, notas_texto, idioma, estilo, estilo_citacion):
    model = get_model()
    
    prompt_final = f"""
    INSTRUCCIÓN MAESTRA:
    {prompt_maestro}
    
    MATERIAL BASE (NOTAS):
    {notas_texto}
    
    REQUISITOS DE FORMATO:
    - Idioma de redacción: {idioma}
    - Notas de estilo: {estilo if estilo else "Académico formal estándar"}
    - Estilo de Citación: {estilo_citacion}
    
    TAREA:
    Redacta el contenido del capítulo. NO saludes. Escribe directamente el texto académico.
    """
    return model.generate_content(prompt_final).text

def generar_bibliografia_global(contenido_completo, estilo_citacion):
    model = get_model()
    prompt = f"""
    Lee la siguiente tesis completa y extrae/genera una lista bibliográfica en formato {estilo_citacion} de todos los autores, obras clásicas (ej. Analectas, Mencio) y conceptos mencionados.
    
    TESIS:
    {contenido_completo}
    
    Devuelve SOLO la bibliografía formateada.
    """
    return model.generate_content(prompt).text
