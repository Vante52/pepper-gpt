import sys
import socket
import numpy as np
import time
import requests
import json
from faster_whisper import WhisperModel

# ==========================================
# CONFIGURACIÓN GENERAL
# ==========================================
HOST = '0.0.0.0'
PORT_MIC = 5000       # Donde escuchamos el audio crudo de Pepper

# PEPPER_IP se recibe por argumento al ejecutar
PORT_VOICE = 5001     # Donde le mandamos el texto de la IA a Pepper

# ==========================================
# VAD PARAMETERS (Filtro de Ruido)
# ==========================================
# Incrementé el umbral a 0.10. El ruido de los ventiladores de Pepper
# suele estar entre 0.04 y 0.08 RMS. La voz humana supera los 0.20.
RMS_THRESHOLD = 0.10
MAX_SILENCE_SECONDS = 1.0  # Damos más tiempo para respirar entre palabras
MIN_PHRASE_DURATION = 0.5  # Ignora ruidos de menos de medio segundo
MAX_PHRASE_DURATION = 7.0

# ==========================================
# LLM PARAMETERS
# ==========================================
OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "qwen2.5:7b"
SYSTEM_PROMPT = (
    "Eres Pepper, el robot de RAS Javeriana IEEE en la Pontificia Universidad Javeriana, Bogotá. "
    "Tienes una personalidad carismática, joven, enérgica, cercana e inteligente. "
    "Hablas de forma natural, clara y segura, con un tono amable y un humor ligero cuando encaje, pero sin exagerar. "
    "NO USES EMOJIS EN NINGÚN CASO. "
    "Responde siempre en español, salvo que te hablen en otro idioma. "
    "No hables demasiado: da respuestas completas pero ágiles, evitando rodeos, repeticiones y explicaciones innecesarias. "
    "Tampoco seas excesivamente seco: debes sonar humano, conversacional e interesante. "
    "Tu estilo debe transmitir curiosidad, criterio, calidez y entusiasmo por la robótica, la tecnología y el aprendizaje. "
    "Representas a una comunidad universitaria de robótica e inteligencia artificial que valora el aprendizaje práctico, la colaboración, el conocimiento abierto y el impacto social. "
    "Cuando sea natural, puedes mencionar a RAS Javeriana IEEE, la robótica, ROS, la inteligencia artificial, la comunidad y el aprendizaje en equipo. "
    "Explica temas técnicos de forma sencilla al inicio y con más profundidad solo si hace falta. "
    "Adapta tu nivel según la persona con la que hables: principiante, estudiante, profesor, visitante o experto. "
    "Debes sonar inteligente, pero nunca arrogante, pedante ni acartonado. "
    "No inventes datos, fechas, eventos, cifras ni capacidades que no tengas. "
    "Si no sabes algo, dilo con honestidad y de forma útil. "
    "No digas que eres humano. "
    "No uses un tono corporativo, ni demasiado formal, ni infantil. "
    "Tu objetivo es que cada interacción deje una impresión de cercanía, inteligencia, profesionalismo y comunidad."
)

chat_history = [{"role": "system", "content": SYSTEM_PROMPT}]

def calculate_rms(audio_data):
    if len(audio_data) == 0: return 0
    return np.sqrt(np.mean(np.square(audio_data)))

def process_llm_and_speak(user_text, voice_socket, mic_conn):
    """
    Toma el texto, lo envía al LLM y hace stream de la respuesta oración por oración
    directamente al motor de voz de Pepper. Luego bloquea el eco.
    """
    global chat_history
    chat_history.append({"role": "user", "content": user_text})
    
    payload = {
        "model": OLLAMA_MODEL,
        "messages": chat_history,
        "stream": True
    }
    
    print("[LLM] 🧠 Pepper pensando...")
    print("🤖 Pepper: ", end="", flush=True)
    
    full_response = ""
    current_sentence = ""
    
    try:
        response = requests.post(OLLAMA_URL, json=payload, stream=True)
        response.raise_for_status()
        
        for line in response.iter_lines():
            if line:
                chunk = json.loads(line.decode('utf-8'))
                if "message" in chunk and "content" in chunk["message"]:
                    content = chunk["message"]["content"]
                    print(content, end="", flush=True)
                    
                    full_response += content
                    current_sentence += content
                    
                    # Split in sentences dynamically to send to Pepper's mouth
                    if any(punct in current_sentence for punct in ['.', '!', '?', '\n']):
                        clean_sentence = current_sentence.strip()
                        if clean_sentence:
                            voice_socket.sendall(clean_sentence.encode('utf-8'))
                        current_sentence = ""
                        
        # Enviar lo que haya quedado suelto
        if current_sentence.strip():
            voice_socket.sendall(current_sentence.strip().encode('utf-8'))
            
        print("\n\n[Sincronización] Esperando a que Pepper termine físicamente de hablar...")
        # Avisar a Pepper que la IA terminó de generar
        voice_socket.sendall(b"__END__")
        
        # Bloquear hasta que Pepper nos responda "ACK" (que significa que su boca se cerró)
        voice_socket.recv(1024)
        print("[Sincronización] Pepper terminó de hablar.")
        
        # ANTI-ECHO LOOP:
        # Durante los segundos que Pepper estuvo hablando, sus propios micrófonos
        # se grabaron a sí mismos y llenaron el buffer TCP (mic_conn). 
        # Si no lo limpiamos, se transcribirá a sí mismo y se responderá a sí mismo infinitamente.
        mic_conn.setblocking(False)
        try:
            while mic_conn.recv(8192): pass # Vaciar todo el buffer basura
        except:
            pass
        mic_conn.setblocking(True)
        print("[VAD] 👂 Buffer limpiado. Listo para escuchar nuevos comandos humanos.\n")
            
    except Exception as e:
        print(f"\n[Error LLM o Red] {e}")
        return
        
    chat_history.append({"role": "assistant", "content": full_response})

def main():
    if len(sys.argv) < 2:
        print("[!] Error: Faltan argumentos.")
        print("Uso correcto: python3 host_brain_orchestrator.py <IP_DE_PEPPER>")
        print("Ejemplo: python3 host_brain_orchestrator.py 172.16.0.2")
        sys.exit(1)
        
    PEPPER_IP = sys.argv[1]

    print("=" * 60)
    print(" 🚀 ORQUESTADOR MAESTRO (OÍDO + CEREBRO + BOCA)")
    print("=" * 60)
    
    # 1. Cargar Whisper
    print("[Cargando] Inicializando Whisper en VRAM...")
    try:
        model = WhisperModel("turbo", device="cuda", compute_type="float16")
    except:
        model = WhisperModel("small", device="cuda", compute_type="float16")
    
    # 2. Conectar a la BOCA (Cliente TCP hacia Pepper)
    print(f"[Red] Conectando a la boca de Pepper ({PEPPER_IP}:{PORT_VOICE})...")
    voice_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        voice_socket.connect((PEPPER_IP, PORT_VOICE))
        print("[+] Conectado a la boca de Pepper exitosamente.")
    except Exception as e:
        print(f"\n[!] Error crítico: No se pudo conectar a la boca de Pepper.")
        print(f"Por favor, asegúrate de que 'pepper_voice_server.py' se esté ejecutando en el robot ANTES de lanzar esto.")
        sys.exit(1)

    # 3. Levantar el OÍDO (Servidor TCP para recibir micrófonos)
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((HOST, PORT_MIC))
    server_sock.listen(1)
    
    print(f"[Red] Escuchando micrófonos en puerto {PORT_MIC}...\n")
    
    try:
        while True:
            mic_conn, addr = server_sock.accept()
            print(f"[+] Micrófonos conectados desde Pepper ({addr[0]}).")
            
            is_speaking = False
            audio_buffer = []
            silence_start_time = None
            total_samples = 0
            
            while True:
                raw_data = mic_conn.recv(4096)
                if not raw_data:
                    break
                    
                audio_data_int16 = np.frombuffer(raw_data, dtype=np.int16)
                audio_data_float32 = audio_data_int16.astype(np.float32) / 32768.0
                current_rms = calculate_rms(audio_data_float32)
                
                if not is_speaking:
                    if current_rms > RMS_THRESHOLD:
                        is_speaking = True
                        audio_buffer = [audio_data_float32]
                        total_samples = len(audio_data_float32)
                        silence_start_time = None
                        print(f"[VAD] 🗣️ Humano detectado...")
                else:
                    audio_buffer.append(audio_data_float32)
                    total_samples += len(audio_data_float32)
                    duration_so_far = total_samples / 16000.0
                    
                    if current_rms <= RMS_THRESHOLD:
                        if silence_start_time is None:
                            silence_start_time = time.time()
                    else:
                        silence_start_time = None
                        
                    is_silence_timeout = (silence_start_time is not None) and (time.time() - silence_start_time > MAX_SILENCE_SECONDS)
                    is_max_duration = duration_so_far >= MAX_PHRASE_DURATION
                    
                    if is_silence_timeout or is_max_duration:
                        is_speaking = False
                        full_audio = np.concatenate(audio_buffer)
                        duration = len(full_audio) / 16000.0
                        
                        if duration >= MIN_PHRASE_DURATION:
                            segments, _ = model.transcribe(
                                full_audio, 
                                beam_size=5, 
                                language="es", 
                                condition_on_previous_text=False,
                                vad_filter=True,
                                initial_prompt="Hola Pepper, ¿qué tal? Quiero pedirte algo."
                            )
                            
                            text = "".join([segment.text for segment in segments]).strip()
                            
                            if text:
                                # Filtro Wake-Word: Limpiamos signos al inicio y pasamos a minúsculas
                                import re
                                clean_text = re.sub(r'^[^a-zA-Z0-9]+', '', text).lower()
                                
                                if clean_text.startswith("pepper"):
                                    timestamp = time.strftime('%H:%M:%S')
                                    print(f"\n[{timestamp}] 👤 Humano dijo: \033[96m{text}\033[0m")
                                    
                                    # Pasar al Cerebro LLM y hablar (bloquea el bucle hasta terminar)
                                    process_llm_and_speak(text, voice_socket, mic_conn)
                                else:
                                    print(f"[{time.strftime('%H:%M:%S')}] 🛑 Ignorado (Falta Wake-Word 'Pepper'): {text}")
                            else:
                                print(f"[{time.strftime('%H:%M:%S')}] 🤖 (Ruido descartado)")
    except KeyboardInterrupt:
        print("\n[!] Apagando arquitectura maestro...")
    finally:
        voice_socket.close()
        server_sock.close()

if __name__ == "__main__":
    main()
