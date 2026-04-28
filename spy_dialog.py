# -*- coding: utf-8 -*-
import time
import sys
import datetime
from naoqi import ALProxy, ALBroker, ALModule

# Variable global requerida por la arquitectura de ALModule en Python
SpyDialogModule = None

class SpyDialog(ALModule):
    def __init__(self, name):
        ALModule.__init__(self, name)
        # Conectamos a ALMemory (usamos 127.0.0.1 al ejecutarse directo en el robot)
        self.memory = ALProxy("ALMemory", "127.0.0.1", 9559)
        
        # Suscribimos al evento principal del motor de reconocimiento (Nuance)
        self.memory.subscribeToEvent("WordRecognized", self.getName(), "onWordRecognized")
        
        # Opcional: Suscribir a lo que ALDialog finalmente "valida" para sus reglas
        self.memory.subscribeToEvent("Dialog/LastInput", self.getName(), "onLastInput")

    def onWordRecognized(self, key, value, message):
        """
        Callback cuando ALSpeechRecognition (Nuance) reconoce algo.
        'value' es una lista: [palabra_1, confianza_1, palabra_2, confianza_2, ...]
        Normalmente el índice 0 y 1 son la mejor coincidencia.
        """
        if value and len(value) >= 2:
            phrase = value[0]
            confidence = value[1]
            
            # Filtramos los "<...>" vacíos o ruido con nula confianza
            if phrase and phrase != "<...>":
                timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                print("[{}] [ASR] Escuchó: '{}' (Confianza: {:.2f})".format(timestamp, phrase, confidence))

    def onLastInput(self, key, value, message):
        """
        Callback secundario cuando ALDialog acepta y procesa la entrada de texto.
        """
        if value:
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            print("[{}] [ALDialog] Validó entrada: '{}'".format(timestamp, value))

    def clean_exit(self):
        """Desuscripción limpia de ALMemory"""
        try:
            print("Desuscribiendo de los eventos de ALMemory...")
            self.memory.unsubscribeToEvent("WordRecognized", self.getName())
            self.memory.unsubscribeToEvent("Dialog/LastInput", self.getName())
        except Exception as e:
            print("Aviso al desuscribirse: {}".format(e))

def main():
    # Para recibir callbacks a través de ALModule, necesitamos registrar un ALBroker local
    try:
        myBroker = ALBroker("myBroker",
            "0.0.0.0",   # Escuchar en todas las interfaces locales
            0,           # Puerto aleatorio disponible
            "127.0.0.1", # IP del broker de NAOqi (localhost)
            9559)        # Puerto de NAOqi
    except Exception as e:
        print("No se pudo instanciar el broker local. ¿Está NAOqi corriendo?")
        print("Detalle: {}".format(e))
        sys.exit(1)

    global SpyDialogModule
    SpyDialogModule = SpyDialog("SpyDialogModule")

    print("=" * 60)
    print(" SpyDialog iniciado correctamente dentro de Pepper.")
    print(" Escuchando la memoria en tiempo real...")
    print(" Presiona Ctrl+C para detener y limpiar los procesos.")
    print("=" * 60)

    try:
        # Bucle infinito para mantener vivo el proceso
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[!] Señal de interrupción detectada (Ctrl+C). Saliendo...")
    finally:
        # Procedimiento de limpieza estricto
        if SpyDialogModule is not None:
            SpyDialogModule.clean_exit()
        if 'myBroker' in locals():
            myBroker.shutdown()
        print("Procesos cerrados de manera limpia.")

if __name__ == "__main__":
    main()
