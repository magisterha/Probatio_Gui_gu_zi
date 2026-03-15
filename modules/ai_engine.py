import google.generativeai as genai
import streamlit as st
import json
import re

# --- CONFIGURACIÓN E UTILIDADES ---

def get_model(system_instruction=None):
    """
    Configura y devuelve el modelo Gemini. 
    Se recomienda pasar la instrucción de sistema aquí para mayor consistencia.
    """
    return genai.GenerativeModel(
        model_name='gemini-2.0-flash',
        system_instruction=system_instruction
    )

def extract_json(text):
    """
    Limpia el texto de la IA y extrae el objeto JSON de forma robusta.
    """
    try:
        # Busca el contenido entre las primeras y últimas llaves
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            clean_json = match.group(0)
            return json.loads(clean_json)
        return json.loads(text)
    except (json.JSONDecodeError, AttributeError) as e:
        st.error(f"Error al procesar el formato JSON: {e}")
        return None

# --- FASE A: IDEAS (CHAT CONVERSACIONAL) ---

def chat_with_ideas(history, user_input):
    """
    Gestiona la conversación del tutor de tesis.
    'history' debe provenir de st.session_state.messages en formato Gemini.
    """
    system_instruction = (
        "Eres un tutor de tesis experto en Sinología. Ayudas al usuario a pivotar ideas, "
        "encontrar vacíos de investigación y definir conceptos de Xùngǔ. "
        "Sé ingenioso y académico. No uses un tono genérico."
    )
    model = get_model(system_instruction)
    
    # El chat de Gemini mantiene el estado si le pasamos el historial
    chat = model.start_chat(history=history)
    response = chat.send_message(user_input)
    return response.text

# --- FASE B: GENERADOR DE ESTRUCTURA (JSON) ---

def generate_research_structure(contexto_data, enfoque_usuario):
    """
    Crea la estructura de la tesis basada en datos de Supabase.
    """
    system_instr = "Eres un Decano de Investigación especializado en estudios clásicos chinos."
    model = get_model(system_instr)
    
    contexto_str = json.dumps(contexto_data, indent=2, ensure_ascii=False)
    
    prompt = f"""
    Basándote en los siguientes DATOS DE SUPABASE:
    {contexto_str}
    
    Y en este ENFOQUE DEL USUARIO: "{enfoque_usuario}"
    
    TAREA:
    Diseña una estructura de monografía doctoral. 
    Responde EXCLUSIVAMENTE con un objeto JSON con este formato exacto:
    {{
      "titulo_tesis": "Título sugerido",
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
    """
    response = model.generate_content(prompt)
    return extract_json(response.text)

# --- FASE C: GENERADOR DE PROMPTS MAESTROS ---

def create_master_prompt_for_section(capitulo, contexto_secundario):
    """
    Genera un prompt directivo para un capítulo específico.
    """
    model = get_model()
    
    contexto_str = json.dumps(contexto_secundario, indent=2, ensure_ascii=False) if contexto_secundario else "Usa conocimiento general."
    
    prompt = f"""
    Eres un Ingeniero de Prompts Académicos experto en Sinología. 
    Capítulo: "{capitulo['titulo']}"
    Objetivo: "{capitulo['objetivo']}"
    Fuentes Secundarias: {contexto_str}
    
    TAREA: Genera UN 'Prompt Maestro' directivo para redactar este capítulo. 
    El prompt debe exigir: tono formal, exégesis (Xùngǔ) y citas del contexto.
    Devuelve solo el texto del prompt.
    """
    response = model.generate_content(prompt)
    return response.text

# --- FASE D: REFINADOR DE PROMPTS ---

def refine_prompt_into_subprompts(capitulo, master_prompt, contexto_rag):
    """
    Divide el prompt maestro en subtareas para redacción profunda.
    """
    model = get_model("Eres un Arquitecto de Prompts experto.")
    
    contexto_str = json.dumps(contexto_rag, indent=2, ensure_ascii=False) if contexto_rag else "Sin contexto adicional."
    subpuntos_str = "\n".join([f"- {sp}" for sp in capitulo.get('subpuntos', [])])
    
    prompt = f"""
    CAPÍTULO: {capitulo['titulo']}
    SUBPUNTOS: {subpuntos_str}
    PROMPT MAESTRO: {master_prompt}
    CONTEXTO RAG: {contexto_str}
    
    TAREA: Divide el trabajo en una serie secuencial de sub-prompts (Intro, Subpuntos, Conclusión).
    Cada sub-prompt debe pedir desarrollo profundo (3-4 páginas).
    Responde EXCLUSIVAMENTE en JSON:
    {{ "sub_prompts": ["...", "...", "..."] }}
    """
    response = model.generate_content(prompt)
    return extract_json(response.text)

# --- FASE E: EJECUCIÓN (REDACCIÓN FINAL) ---

def execute_section_writing(prompt_especifico, research_context):
    """
    Produce el contenido académico final.
    """
    model = get_model()
    contexto_str = json.dumps(research_context, indent=2, ensure_ascii=False)
    
    prompt_final = f"""
    INSTRUCCIÓN ESPECÍFICA: {prompt_especifico}
    CONTEXTO DE INVESTIGACIÓN: {contexto_str}
    
    REGLA DE ORO: No saludes. Escribe directamente el contenido denso, académico y profundo en español.
    """
    response = model.generate_content(prompt_final)
    return response.text

# --- EJEMPLO DE INTEGRACIÓN EN STREAMLIT ---

def main():
    st.title("Asistente de Tesis en Sinología")

    # Inicializar historial de chat si no existe
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Interfaz de Chat (Fase A)
    user_input = st.chat_input("Discute tus ideas de tesis aquí...")
    if user_input:
        # Mostrar mensaje del usuario
        st.chat_message("user").write(user_input)
        
        # Obtener respuesta del tutor
        # Nota: Gemini espera una lista de objetos con 'role' y 'parts'
        history_gemini = [
            {"role": m["role"], "parts": [m["content"]]} 
            for m in st.session_state.messages
        ]
        
        respuesta = chat_with_ideas(history_gemini, user_input)
        
        # Guardar y mostrar
        st.session_state.messages.append({"role": "user", "content": user_input})
        st.session_state.messages.append({"role": "model", "content": respuesta})
        st.chat_message("assistant").write(respuesta)

if __name__ == "__main__":
    main()
