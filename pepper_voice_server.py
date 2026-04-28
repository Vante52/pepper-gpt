# -*- coding: utf-8 -*-
import sys
import socket
from naoqi import ALProxy

# ==========================================
# CONFIGURACIÓN DEL SERVIDOR DE VOZ
# ==========================================
PORT = 5001

def stop_dialog():
    """Pausa ASR para que no interfiera"""
    print("[Pre-vuelo] Pausando reconocimiento de voz (ASR)...")
    try:
        asr = ALProxy("ALSpeechRecognition", "127.0.0.1", 9559)
        asr.pause(True)
    except Exception:
        pass

def setup_voice(tts):
    """Configura el perfil de voz y animaciones automáticas"""
    try:
        tts.setLanguage("Spanish")
        tts.setParameter("pitchShift", 1.2)
        tts.setParameter("doubleVoice", 0.0)
    except Exception:
        pass
        
    try:
        speaking_movement = ALProxy("ALSpeakingMovement", "127.0.0.1", 9559)
        speaking_movement.setEnabled(True)
        speaking_movement.setMode("contextual")
    except Exception:
        pass

def animate_and_speak(animated_speech, text_raw):
    """Envía la orden a los motores de Pepper"""
    # 1. Asegurar formato UTF-8 para Python 2.7 (NAOqi odia los objetos unicode)
    if isinstance(text_raw, unicode):
        safe_text = text_raw.encode('utf-8')
    else:
        safe_text = text_raw

    clean_text = safe_text.strip()
    if not clean_text: return
    
    # 2. Inyectamos velocidad baja y pitch joven
    enriched_text = "\\vct=115\\ \\rspd=85\\ " + clean_text
    print("[Pepper] Hablando: '{}'".format(clean_text))
    
    try:
        # Esto bloquea la ejecución hasta que Pepper termina de decir esta frase
        animated_speech.say(enriched_text)
    except Exception as e:
        print("[Error] ALAnimatedSpeech falló: {}".format(e))

def main():
    print("=" * 50)
    print(" PEPPER VOICE SERVER (Puerto {})".format(PORT))
    print(" (Recibe streaming desde la IA y lo habla)")
    print("=" * 50)
    
    try:
        tts = ALProxy("ALTextToSpeech", "127.0.0.1", 9559)
        animated_speech = ALProxy("ALAnimatedSpeech", "127.0.0.1", 9559)
    except Exception as e:
        print("[!] FATAL: Ejecuta esto DENTRO del robot.")
        sys.exit(1)
        
    stop_dialog()
    setup_voice(tts)
    
    # Levantar servidor TCP
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(('0.0.0.0', PORT))
    server_sock.listen(1)
    
    print("\n[+] Servidor levantado. Esperando al cerebro (Host)...")
    
    try:
        while True:
            conn, addr = server_sock.accept()
            print("\n[+] Cerebro conectado desde: {}".format(addr))
            
            while True:
                data = conn.recv(8192)
                if not data:
                    break # Se cortó la conexión
                
                # Decodificamos de bytes a string unicode
                text_chunk = data.decode('utf-8')
                
                # El host envía __END__ cuando la IA terminó toda su respuesta
                # Esto es para que Pepper confirme cuándo físicamente terminó de hablarlo todo
                parts = text_chunk.split(u"__END__")
                
                for i, part in enumerate(parts):
                    if part.strip():
                        animate_and_speak(animated_speech, part)
                        
                    if i < len(parts) - 1:
                        # Mandamos un ACK (Acknowledgement) para que el Host sepa
                        # que puede prender los micrófonos de nuevo
                        conn.sendall(b"ACK")
                        
            conn.close()
            print("[-] Cerebro desconectado. Esperando...")
            
    except KeyboardInterrupt:
        print("\n[!] Apagando servidor.")
    finally:
        try:
            asr = ALProxy("ALSpeechRecognition", "127.0.0.1", 9559)
            asr.pause(False)
        except:
            pass

if __name__ == "__main__":
    main()
