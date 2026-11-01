# Reacciona — The Box Arcade (Mac MVP)

Primer prototipo **local, sin PWA ni gateway**, sobre el BLE real de Concept2 PM5 y el código de ergtrack.

## Instalación

En macOS, con Python 3.10+:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install bleak
```

## Ejecutar

```bash
# Simulación acelerada, sin máquina
python reacciona.py --simulate --tick 0 --mute

# Simulación con sonidos
python reacciona.py --simulate

# BLE real, seleccionar PM5 por su número
python reacciona.py

# Ejecutar pruebas
python -m unittest test_reacciona.py -v
```

El juego detecta monitores que anuncian PM5 mediante BLE. Si encuentra uno solo lo selecciona automáticamente; si encuentra varios, muestra una lista numerada para elegir sin conocer sus números. `--name` sigue disponible como filtro opcional. El PM5 debe estar despierto, y macOS debe permitir Bluetooth al terminal. No se envían comandos de escritura al monitor.

## Mecánicas

Calibración de 45 segundos a esfuerzo cómodo. Se toma la mediana de los últimos 30 segundos como potencia de referencia. Hay ocho eventos en orden aleatorio: tres **escape** (acelerar al menos al 130% del valor de referencia), tres **defend** (mantenerse entre 85–115%) y dos **recover** (bajar al 45–75%). Cada evento concede tres segundos de transición. Se evalúan cinco segundos en escape u ocho en los otros dos.

Puntuación: 100 puntos por éxito, 25 extras por ejecución excelente y 50 por cada tercera acción correcta consecutiva. Tres vidas al inicio; fallar escape resta una vida, o consume un escudo. Dos defensas correctas cargan un escudo (máximo uno). Una acción de defensa o recuperación fallida no quita vidas.

La interfaz principal es audio generado localmente y mensajes en el terminal. Se guarda la partida en `reacciona-last-session.json`.

## Limitaciones de esta versión

- Los objetivos son **experimentales**, no una prescripción de entrenamiento; parar si aparecen molestias y no sacrificar técnica por los puntos.
- Las notificaciones de potencia del PM5 pueden llegar con variación temporal; aún debemos medir latencia con RowErg y SkiErg reales.
- La duración es aproximada: depende del número de eventos, pausas y reproducción del audio. Todavía no hay un temporizador rígido de tres minutos.
- Si faltan métricas recientes, se interrumpe sin penalizar; aún no existe reconexión automática.
- Esta versión es para **tu Mac**. La PWA y los gateways BLE son una fase posterior.
