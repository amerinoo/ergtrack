# ErgTrack

Videojuego tipo Scalextric controlado por monitores Concept2 PM5.

## Estado

**PoC 0: USB / HID / CSAFE.** Este código todavía no ha sido probado con un PM5 físico. No usa ErgRace.

## Requisitos

- macOS con Python 3.10+
- Cable USB del Mac al puerto USB-B del PM5 (o USB-C en PM5 recientes)
- Un monitor PM5 encendido

## Uso

```bash
git clone https://github.com/amerinoo/ergtrack.git
cd ergtrack
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python pm5_probe.py --list
python pm5_probe.py --probe
```

`--list` enumera los dispositivos Concept2 encontrados. `--probe` envía una solicitud CSAFE de versión (de solo lectura), imprime los bytes recibidos y sirve para diagnosticar el transporte sin interpretar todavía distancia, potencia ni cadencia.

Si macOS no reconoce el monitor:

```bash
system_profiler SPUSBDataType
```

Comparte los resultados de `--list` y `--probe` (excluyendo números de serie si lo prefieres). Después implementaremos lectura periódica de métricas y una segunda máquina.

## Plan

1. Detección USB y transporte CSAFE.
2. Lectura real de distancia, velocidad, potencia y cadencia.
3. Verificación de dos PM5 vía RS485 (RJ45) con un USB — **no confirmada** para nuestra implementación.
4. Simulador y primer circuito de carreras con Phaser.

## Referencias

- [Concept2 — desarrollo de software](https://www.concept2.com/support/software-development)
- [PM5 CSAFE Communication Definition](https://www.concept2.co.uk/files/pdf/us/monitors/PM5_CSAFECommunicationDefinition.pdf)

El puerto RJ45 del PM5 es RS485, no una conexión Ethernet TCP/IP: no conectarlo a un switch Ethernet o PoE.
