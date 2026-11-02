# Reacciona — The Box Arcade (Mac MVP)

Primer prototipo **local, sin PWA ni gateway**, sobre el BLE real de Concept2 PM5 y el código de ergtrack.

La conexión BLE se implementa **una sola vez** en `pm5_ble.py`. Tanto `reacciona.py` como `ble_drag_test.py` lo importan, comparten descubrimiento, selección, conexión, suscripción a 0x31/0x32/0x36 y decodificación. Las pruebas de decodificación no necesitan hardware.

## Instalación

En macOS, con Python 3.10+:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install bleak
```

## Interfaz gráfica en macOS

La aplicación Tkinter incluye una guía de inicio: sentarse al remo, pulsar MENU en PM5, conectar y empezar a remar. La partida comienza al detectar movimiento (en modo real). La barra de esfuerzo ocupa el espacio principal, con zona objetivo fija y marcador suavizado; la simulación evita avisos falsos por relojes diferentes.

La aplicación Tkinter muestra el estado de conexión del PM5, potencia en directo, objetivos, fases, cuenta atrás, rondas, puntos, vidas, escudo y racha. Permite configurar el número de rondas (1 a 20), la potencia de referencia y un filtro opcional para elegir el PM5 por nombre. Conserva los sonidos del motor y no requiere servidor.

```bash
python reacciona_gui.py
```

Para probar sin PM5, marca **Simulación** antes de iniciar. Para cerrar una partida, pulsa **Detener** (la ejecución se detiene al llegar a un punto seguro entre fases). En Mac, Python debe disponer de `tkinter`; si `import tkinter` falla, utiliza una instalación de Python con soporte Tcl/Tk. Si hay varios PM5, introduce un fragmento distintivo del nombre del monitor.

## Ejecutar

```bash
# Simulación acelerada, sin máquina
python reacciona.py --simulate --tick 0 --mute

# Simulación con sonidos
python reacciona.py --simulate

# BLE real: reutiliza la calibración guardada o calibra si no existe
python reacciona.py

# Pruebas rápidas: usa los 112 W ya medidos, sin calibrar
python reacciona.py --baseline 112 --rounds 3

# Forzar una nueva calibración y guardarla
python reacciona.py --recalibrate

# Ejecutar pruebas
python -m unittest test_reacciona.py -v
```

El juego detecta monitores que anuncian PM5 mediante BLE. Si encuentra uno solo lo selecciona automáticamente; si encuentra varios, muestra una lista numerada para elegir sin conocer sus números. `--name` sigue disponible como filtro opcional. El PM5 debe estar despierto, y macOS debe permitir Bluetooth al terminal. No se envían comandos de escritura al monitor.

## Calibración reutilizable

La primera partida real sin configuración guarda la referencia en `.reacciona-calibration.json`. Las siguientes partidas la reutilizan automáticamente. `--baseline W` utiliza temporalmente un valor manual (no lo guarda), y `--recalibrate` mide y sustituye el valor guardado. La simulación no modifica la calibración real. La referencia corresponde a la persona y máquina con las que se midió; recalibrar al cambiar de deportista o de máquina.

## Mecánicas

Calibración de 45 segundos a esfuerzo cómodo. Se toma la mediana de los últimos 30 segundos como potencia de referencia. Los eventos se eligen aleatoriamente según el número de rondas (evitando dos escapes consecutivos): **escape** (acelerar al menos al 130% del valor de referencia), **defend** (mantenerse entre 85–115%) y **recover** (bajar al 45–75%). Cada evento concede tres segundos de transición. Se evalúan cinco segundos en escape u ocho en los otros dos.

Puntuación: 100 puntos por éxito, 25 extras por ejecución excelente y 50 por cada tercera acción correcta consecutiva. Tres vidas al inicio; fallar escape resta una vida, o consume un escudo. Dos defensas correctas cargan un escudo (máximo uno). Una acción de defensa o recuperación fallida no quita vidas.

La voz está desactivada: se utilizan señales sonoras y una cuenta atrás de tres pitidos, y el terminal muestra instrucciones y explicación de los puntos. Durante la espera, mantén el 85–115% de la referencia. El número de rondas se controla con `--rounds N` (1–20; por defecto 3). Los resultados muestran cuántas muestras cumplen el objetivo. Se guarda la partida en `reacciona-last-session.json`.

## Limitaciones de esta versión

- Los objetivos son **experimentales**, no una prescripción de entrenamiento; parar si aparecen molestias y no sacrificar técnica por los puntos.
- Las notificaciones de potencia del PM5 pueden llegar con variación temporal; aún debemos medir latencia con RowErg y SkiErg reales.
- La duración es aproximada: depende del número de eventos, pausas y reproducción del audio. Todavía no hay un temporizador rígido de tres minutos.
- Si faltan métricas recientes, se interrumpe sin penalizar; aún no existe reconexión automática.
- Esta versión es para **tu Mac**. La PWA y los gateways BLE son una fase posterior.
