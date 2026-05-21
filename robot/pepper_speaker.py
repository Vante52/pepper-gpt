# -*- coding: utf-8 -*-
import sys
import random
from naoqi import ALProxy

def stop_dialog():
    """
    Pausa el motor de reconocimiento global (ASR) para evitar que Pepper 
    te escuche e interrumpa con ALDialog mientras está hablando.
    """
    print("[Pre-vuelo] Pausando reconocimiento de voz...")
    try:
        # unsubscribe() falla si no sabemos el ID exacto del suscriptor (ej. ALDialog_xxx).
        # pause(True) detiene el procesamiento de audio globalmente sin romper las suscripciones.
        asr = ALProxy("ALSpeechRecognition", "127.0.0.1", 9559)
        asr.pause(True)
    except Exception as e:
        print("[Aviso] No se pudo pausar ASR: {}".format(e))

def setup_voice(tts):
    """
    Configura el idioma, los parámetros tonales y activa el motor autónomo
    de movimientos al hablar (ALSpeakingMovement).
    """
    try:
        tts.setLanguage("Spanish")
    except Exception as e:
        print("[Aviso] Error al establecer idioma: {}".format(e))

    try:
        # pitchShift (1.0 es default). Valores > 1.0 hacen la voz más aguda/joven.
        tts.setParameter("pitchShift", 1.2)
        # doubleVoice le da el típico tono robótico de C3PO. 0.0 lo desactiva para más naturalidad.
        tts.setParameter("doubleVoice", 0.0)
    except Exception as e:
        print("[Aviso] Error al ajustar parámetros de voz: {}".format(e))
        
    try:
        # Habilitar el motor automático de gestos nativo de NAOqi
        speaking_movement = ALProxy("ALSpeakingMovement", "127.0.0.1", 9559)
        speaking_movement.setEnabled(True)
        speaking_movement.setMode("contextual") # Pepper decide qué gestos hacer según las palabras
    except Exception as e:
        print("[Aviso] No se pudo activar ALSpeakingMovement: {}".format(e))

def animate_and_speak(animated_speech, raw_text):
    """
    Usa el motor automático de ALAnimatedSpeech para que el robot gesticule 
    naturalmente mientras habla, aplicando modificadores de tono Nuance.
    """
    # 1. Manejo seguro de UTF-8 para Python 2.7 (acentos, ñ, etc.)
    if isinstance(raw_text, unicode):
        safe_text = raw_text.encode('utf-8')
    else:
        safe_text = raw_text # raw_input ya devuelve bytestring de la consola
        
    # 2. Construcción del string (Solo modificadores de voz Nuance)
    # Como ALSpeakingMovement está activado, Pepper se moverá automáticamente 
    # interpretando el contexto de lo que dice sin necesidad de ensuciar el string.
    # Solo inyectamos la energía de la voz:
    # \\vct=115\\ : pitch más agudo
    # \\rspd=85\\  : habla MUCHO más lento (85%). Esto fuerza a que respete 
    #                las comas y los puntos, mejorando la dicción.
    
    enriched_text = "\\vct=115\\ \\rspd=85\\ " + safe_text
    
    print("[Pepper] Hablando articulado: '{}'".format(safe_text))
    
    try:
        # say() bloquea hasta que termina de hablar
        animated_speech.say(enriched_text)
    except Exception as e:
        print("[Error] ALAnimatedSpeech.say falló: {}".format(e))

def main():
    print("=" * 50)
    print(" PEPPER ANIMATED SPEAKER (Python 2.7)")
    print(" Acentos y 'ñ' soportados de forma nativa")
    print("=" * 50)
    
    # Conexión local al broker del robot
    try:
        tts = ALProxy("ALTextToSpeech", "127.0.0.1", 9559)
        animated_speech = ALProxy("ALAnimatedSpeech", "127.0.0.1", 9559)
    except Exception as e:
        print("[!] FATAL: No se pudieron instanciar los proxies.")
        print("Asegúrate de ejecutar este script DENTRO de Pepper.")
        print("Detalle: {}".format(e))
        sys.exit(1)
        
    # 1. Silenciar comportamiento nativo
    stop_dialog()
        
    # 2. Configurar el perfil de voz
    setup_voice(tts)
    
    print("\n[+] Todo listo. Escribe lo que quieras que Pepper diga.")
    print("[+] Escribe 'salir' o presiona Ctrl+C para terminar.\n")
    
    while True:
        try:
            # raw_input() atrapa los bytes en bruto de la terminal (incluyendo tildes)
            user_input = raw_input("Escribe el diálogo > ")
            
            if user_input.strip().lower() in ['salir', 'exit', 'quit']:
                print("\nSaliendo...")
                break
                
            if user_input.strip():
                animate_and_speak(animated_speech, user_input)
                
        except KeyboardInterrupt:
            print("\n[!] Cierre forzado (Ctrl+C). Restaurando ASR...")
            break
        except EOFError:
            break

    # Restaurar la audición al salir del script
    try:
        asr = ALProxy("ALSpeechRecognition", "127.0.0.1", 9559)
        asr.pause(False)
        print("Reconocimiento de voz nativo restaurado.")
    except Exception:
        pass

if __name__ == "__main__":
    main()
