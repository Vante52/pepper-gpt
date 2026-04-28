import socket
import numpy as np
import threading
import time
from faster_whisper import WhisperModel

# ==========================================
# CONFIGURACIÓN DEL SERVIDOR
# ==========================================
HOST = '0.0.0.0' # Escucha en todas las interfaces de red
PORT = 5000
SAMPLE_RATE = 16000
CHUNK_SIZE = 4096 # Bytes leídos del socket por iteración

# ==========================================
# CONFIGURACIÓN DE VAD (Detección de Voz por Energía RMS)
# ==========================================
RMS_THRESHOLD = 0.015       # Sensibilidad del micrófono (ajustar si hay ruido)
SILENCE_DURATION = 1.0      # Segundos de silencio para cortar la frase
MIN_PHRASE_DURATION = 0.5   # Segundos mínimos para mandar a transcribir

def calculate_rms(audio_array):
    """Calcula la energía (Root Mean Square) del array de audio."""
    if len(audio_array) == 0: return 0
    return np.sqrt(np.mean(np.square(audio_array)))

def process_audio_stream(conn, addr, model):
    print(f"\n[+] Conexión establecida desde Pepper ({addr[0]}).")
    audio_buffer = []
    is_speaking = False
    silence_start_time = None
    total_samples = 0
    
    try:
        while True:
            raw_data = conn.recv(CHUNK_SIZE)
            if not raw_data:
                break # Conexión cerrada
                
            # 1. Transformación de Bytes (Int16 Little Endian) a Float32 normalizado (-1.0 a 1.0)
            audio_data_int16 = np.frombuffer(raw_data, dtype=np.int16)
            audio_data_float32 = audio_data_int16.astype(np.float32) / 32768.0
            
            # 2. Análisis de Energía
            current_rms = calculate_rms(audio_data_float32)
            
            # 3. Máquina de Estados VAD (Robusta con conteo real de samples)
            if not is_speaking:
                if current_rms > RMS_THRESHOLD:
                    is_speaking = True
                    audio_buffer = [audio_data_float32]
                    total_samples = len(audio_data_float32)
                    silence_start_time = None
                    print(f"[VAD] 🗣️ Pepper escuchando... (RMS base: {current_rms:.4f})")
            else:
                # Estamos grabando
                audio_buffer.append(audio_data_float32)
                total_samples += len(audio_data_float32)
                
                # Check de silencio vs ruido
                if current_rms <= RMS_THRESHOLD:
                    if silence_start_time is None:
                        silence_start_time = time.time()
                else:
                    silence_start_time = None # Rompió el silencio, sigue hablando
                    
                # Checar condiciones para terminar la frase
                silence_timeout = (silence_start_time is not None) and (time.time() - silence_start_time > SILENCE_DURATION)
                max_duration_reached = (total_samples / SAMPLE_RATE) >= 7.0
                
                if silence_timeout or max_duration_reached:
                    is_speaking = False
                    reason = "Silencio" if silence_timeout else "Cortafuegos (7s máx)"
                    
                    phrase_audio = np.concatenate(audio_buffer)
                    duration = len(phrase_audio) / SAMPLE_RATE
                    print(f"[VAD] 🛑 Corte por {reason}. Procesando {duration:.1f}s...")
                    
                    if duration >= MIN_PHRASE_DURATION:
                        # 4. Transcripción usando GPU
                        # Mejoras de precisión aplicadas:
                        # - vad_filter=True: Usa IA (Silero) internamente para ignorar el ruido de motores antes de transcribir.
                        # - initial_prompt: Le da un contexto previo en español para que entienda mejor comandos de robótica.
                        segments, info = model.transcribe(
                            phrase_audio, 
                            beam_size=5, 
                            language="es", 
                            condition_on_previous_text=False,
                            vad_filter=True,
                            initial_prompt="Hola Pepper, ¿qué tal? Quiero pedirte algo."
                        )
                        
                        text = "".join([segment.text for segment in segments]).strip()
                        timestamp = time.strftime('%H:%M:%S')
                        if text:
                            print(f"\n[{timestamp}] 🤖 Pepper escuchó: \033[92m{text}\033[0m\n")
                        else:
                            print(f"[{timestamp}] 🤖 (Whisper no entendió nada)")
                    else:
                        print(f"[VAD] 🚫 Ruido ignorado (muy corto).")
                        
                    audio_buffer = [] # Limpiar para la próxima frase
                    total_samples = 0
                        
    except Exception as e:
        print(f"\n[!] Error en el socket: {e}")
    finally:
        conn.close()
        print(f"[!] Conexión cerrada con {addr[0]}. Esperando reconexión...")

def main():
    print("=" * 60)
    print(" INICIANDO SERVIDOR DE INFERENCIA PARA PEPPER")
    print("=" * 60)
    
    # 1. Cargar modelo en VRAM
    print("[Cargando] Inicializando Faster-Whisper en CUDA...")
    try:
        # Usaremos 'turbo' (large-v3-turbo). Es el estado del arte: 
        # casi la precisión de 'large' pero con la velocidad de 'small'.
        # Ideal para la RTX 3050.
        model = WhisperModel("turbo", device="cuda", compute_type="float16")
    except Exception as e:
        print(f"[Aviso] No se pudo cargar 'turbo'. Fallback al modelo 'small'.\nDetalle: {e}")
        model = WhisperModel("small", device="cuda", compute_type="float16")
        
    print("[Cargando] Modelo listo en VRAM.\n")

    # 2. Levantar Socket Server TCP
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # Evitar "Address already in use"
    server_sock.bind((HOST, PORT))
    server_sock.listen(1)
    
    print(f"[Red] Escuchando conexiones entrantes en el puerto {PORT}...")
    
    try:
        while True:
            conn, addr = server_sock.accept()
            # Hilo dedicado para no bloquear la escucha de nuevos clientes
            thread = threading.Thread(target=process_audio_stream, args=(conn, addr, model))
            thread.daemon = True
            thread.start()
    except KeyboardInterrupt:
        print("\n[!] Cierre forzado. Apagando servidor...")
    finally:
        server_sock.close()

if __name__ == "__main__":
    main()
