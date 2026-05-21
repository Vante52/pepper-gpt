# 🤖 Pepper Robot Side Scripts
> **Scripts ligeros en Python 2.7 nativo que se ejecutan directamente dentro de Pepper.**

Estos scripts no requieren dependencias externas (sólo la librería nativa `naoqi` y módulos estándar de Python 2.7).

## 📁 Archivos Incluidos

1.  **`pepper_mic_stream.py`**:
    *   **Función**: Captura el micrófono frontal a 16 kHz y transmite el flujo PCM crudo en tiempo real a través de un socket TCP al PC Host.
    *   **Uso**:
        ```bash
        python pepper_mic_stream.py <IP_DEL_HOST_UBUNTU>
        ```
2.  **`pepper_voice_server.py`**:
    *   **Función**: Servidor que escucha oraciones del cerebro en el puerto `5001` y activa `ALAnimatedSpeech` para hablar con gesticulación contextual y modulación de prosodia ("voz joven").
    *   **Uso**:
        ```bash
        python pepper_voice_server.py
        ```
3.  **`pepper_speaker.py`**:
    *   **Función**: Script de prueba de habla local para validar el sintetizador de voz nativo en Pepper.
4.  **`spy_dialog.py`**:
    *   **Función**: Herramienta de monitoreo y diagnóstico para validar si ALDialog está interactuando con los micrófonos y verificar variables en la memoria `ALMemory`.

## 🚀 Despliegue Rápido
Desde tu computadora Host, puedes transferir toda esta carpeta al robot con un solo comando SCP:
```bash
scp -r robot/ nao@<IP_DE_PEPPER>:/home/nao/
```
Y luego conectarte por SSH para ejecutarlos:
```bash
ssh nao@<IP_DE_PEPPER>
cd robot/
python pepper_voice_server.py
```
