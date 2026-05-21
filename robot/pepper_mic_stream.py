# -*- coding: utf-8 -*-
import time
import sys
import threading
import Queue
import socket
from naoqi import ALProxy, ALBroker, ALModule

# ==========================================
# CONFIGURACIÓN DE RED
# ==========================================
HOST_IP = None  # Se asgina por argumento
HOST_PORT = 5000

AudioStreamerModule = None

class AudioStreamer(ALModule):
    def __init__(self, name):
        ALModule.__init__(self, name)
        self.audio_device = ALProxy("ALAudioDevice", "127.0.0.1", 9559)
        self.audio_queue = Queue.Queue() # Cola thread-safe para no bloquear processRemote
        self.running = True
        
        # 1. Establecer conexión TCP con el Host
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.sock.connect((HOST_IP, HOST_PORT))
            print("[Red] Conectado exitosamente al Host en {}:{}".format(HOST_IP, HOST_PORT))
        except Exception as e:
            print("[Error] No se pudo conectar al host: {}".format(e))
            self.running = False
            return
            
        # 2. Iniciar el hilo consumidor (red)
        self.network_thread = threading.Thread(target=self._network_loop)
        self.network_thread.daemon = True
        self.network_thread.start()
        
        # 3. Configurar ALAudioDevice (16kHz, canal 3=Frente, 0=Interleaved)
        self.audio_device.setClientPreferences(self.getName(), 16000, 3, 0)
        self.audio_device.subscribe(self.getName())
        print("[Audio] Suscrito a ALAudioDevice (16kHz).")

    def processRemote(self, nbOfChannels, nbOfSamplesByChannel, timeStamp, inputBuffer):
        """
        Callback ESTRICTO de ALAudioDevice.
        Prohibido bloquear. Solo metemos datos a la Queue.
        """
        if self.running:
            try:
                # inputBuffer contiene bytes crudos PCM 16-bit
                self.audio_queue.put_nowait(inputBuffer)
            except Queue.Full:
                pass # Previene cuelgues si la cola se saturara

    def _network_loop(self):
        """
        Hilo asíncrono: extrae los datos de la cola y los dispara por el socket.
        """
        while self.running:
            try:
                data = self.audio_queue.get(True, 1) # Bloquea hasta 1 segundo esperando
                self.sock.sendall(data)
            except Queue.Empty:
                continue
            except socket.error as e:
                print("[Error de Red] Conexión perdida: {}".format(e))
                self.running = False
                break
            except Exception as e:
                print("[Error Desconocido] {}".format(e))
                self.running = False
                break

    def stop(self):
        """Desuscripción limpia"""
        self.running = False
        try:
            self.audio_device.unsubscribe(self.getName())
            print("[Audio] Desuscrito de ALAudioDevice exitosamente.")
        except Exception as e:
            print("[Error] Al desuscribir audio: {}".format(e))
            
        try:
            self.sock.close()
            print("[Red] Socket cerrado.")
        except:
            pass

def pre_flight_cleanup():
    """Apaga servicios nativos que compiten por los micrófonos"""
    print("[Pre-vuelo] Liberando micrófonos de ALDialog y ASR...")
    try:
        dialog = ALProxy("ALDialog", "127.0.0.1", 9559)
        dialog.unsubscribe("ALDialog")
    except Exception:
        pass
        
    try:
        asr = ALProxy("ALSpeechRecognition", "127.0.0.1", 9559)
        asr.unsubscribe("ALSpeechRecognition")
    except Exception:
        pass
    print("[Pre-vuelo] Completado.")

def main():
    global HOST_IP
    if len(sys.argv) < 2:
        print("[!] ERROR FATAL: Falta la IP del servidor Host.")
        print("Uso: python pepper_mic_stream.py <IP_DEL_HOST>")
        print("Ejemplo: python pepper_mic_stream.py 172.16.0.8")
        sys.exit(1)
        
    HOST_IP = sys.argv[1]

    # 1. Liberar micrófonos
    pre_flight_cleanup()

    # 2. Instanciar Broker
    try:
        myBroker = ALBroker("myBroker", "0.0.0.0", 0, "127.0.0.1", 9559)
    except Exception as e:
        print("No se pudo iniciar el Broker local: {}".format(e))
        sys.exit(1)

    # 3. Arrancar streaming
    global AudioStreamerModule
    AudioStreamerModule = AudioStreamer("AudioStreamerModule")

    if not AudioStreamerModule.running:
        print("Saliendo debido a errores de inicio...")
        myBroker.shutdown()
        sys.exit(1)

    print("=" * 60)
    print(" ENVIANDO AUDIO EN TIEMPO REAL A {}...".format(HOST_IP))
    print(" Presiona Ctrl+C para finalizar.")
    print("=" * 60)
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[!] Ctrl+C presionado. Terminando...")
    finally:
        if AudioStreamerModule:
            AudioStreamerModule.stop()
        myBroker.shutdown()
        print("Salida completada limpiamente.")

if __name__ == "__main__":
    main()
