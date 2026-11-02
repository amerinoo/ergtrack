# ErgTrack — The Box Arcade

Juegos y experimentos basados en métricas de monitores Concept2 PM5 a través de Bluetooth Low Energy (BLE).

## Estado

Prototipo inicial local para macOS. `pm5_ble.py` centraliza el descubrimiento, selección y comunicación BLE de los monitores PM5. `ble_drag_test.py` es el diagnóstico de métricas y `reacciona.py` el primer juego de audio, sin necesidad de mirar la pantalla.

## Requisitos

- macOS y Python 3.10+
- Concept2 PM5 encendido y anunciándose por Bluetooth BLE
- Permisos Bluetooth para la terminal en macOS

## Instalación

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Uso

```bash
# Pruebas unitarias (sin PM5)
python -m unittest test_reacciona.py -v

# Diagnóstico de descubrimiento BLE (si PM5 no aparece)
python ble_scan.py --seconds 30

# Prueba de métricas PM5 con BLE
python ble_drag_test.py --seconds 30

# Reacciona con PM5 real
python reacciona.py

# Simulación rápida sin PM5
python reacciona.py --simulate --tick 0 --mute
```

Al detectar un PM5 se selecciona automáticamente; si hay varios, se ofrece un menú numerado.

Más detalles: [README-REACCIONA.md](README-REACCIONA.md).

## Arquitectura

- `pm5_ble.py`: driver BLE reutilizable; decodifica distancia, potencia, cadencia y drag factor.
- `ble_scan.py`: diagnóstico de anuncios BLE sin conectarse al PM5.
- `ble_drag_test.py`: captura y diagnostica métricas.
- `reacciona.py`: juego de supervivencia basado en audio, potencia relativa y recompensas.

No se envían instrucciones de escritura al PM5. La PWA para clientes y los gateways BLE son fases posteriores; las pruebas iniciales se realizan únicamente en el Mac.
