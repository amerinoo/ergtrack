# ErgTrack — Technical Validation Plan

## Non-negotiable product constraints

- The game comes **last**, after connectivity validation.
- Concept2 PM5 RowErgs and SkiErgs move around the gym; no permanent cables to machines.
- Members use an ordinary iPhone/Android PWA without native apps, browser extensions, special browsers, or staff assistance.
- Gateway(s) may be installed and maintained centrally, but member sessions must be self-service.
- A QR code identifies a **physical station**, not a Bluetooth pairing mechanism.
- No dependency on ErgRace.

## Hypothesis

A local BLE gateway can discover, connect to, read, and automatically reconnect multiple PM5 monitors while distributing metrics to browsers over WebSocket. **This is unverified.**

## Experiments / gates

### T1 — BLE discovery
Scan PM5 advertising while active, after inactivity, and after a wake-up.
Record advertised service UUIDs, stable identifiers available on macOS, RSSI, timestamp, and firmware.
**Pass:** reliably identify the same monitor across repeats and after wake-up without manually activating a special pairing screen.

### T2 — GATT telemetrics
Read/subscribe to PM5 metrics with documented Concept2 BLE UUIDs, capture distance, elapsed time, cadence and power, measure arrival intervals and disconnect rate.
**Pass:** correct readings, with documented update cadence and no unexpected dropout over a continuous 15-minute run.

### T3 — Zero-touch reconnect
Power off / idle / wake / move PM5; gateway retries with bounded backoff and no staff interaction.
**Pass:** recovery without PM5 menu operations. If PM5 only advertises in a manually enabled mode, mark this a major blocker.

### T4 — Scale and interference
Repeat with 2, 4, then 8+ monitors. Test nearby phones and ErgData simultaneously; do not assume simultaneous subscriptions are supported.
**Pass:** reliable per-device identity, no mixed telemetry, acceptable update cadence and documented capacity.

### T5 — End-user PWA
Member scans QR, claims an available station, starts a session, receives telemetrics via Wi-Fi/WebSockets in ordinary iPhone Safari/PWA, ends and releases station.
**Pass:** no additional installs, cables, manual BLE pairing, or staff assistance. Include ownership conflict handling, authentication or short-lived claims, and cleanup.

## Go/no-go

Do not start Phaser/game implementation until T1–T5 pass at representative scale. If BLE is unavailable without interacting with the PM5, evaluate alternate hardware/gateway designs explicitly before promising full self-service.

## Repository status

Existing USB HID / CSAFE probe remains as a diagnostic fallback, not the preferred deployment topology.

## First hardware test

Start with a single PM5 near a Mac. Record its firmware and whether it is BLE-discoverable by a general BLE scanning program immediately upon waking, without navigating monitor menus.
