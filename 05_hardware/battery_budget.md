# 05 · Battery budget — method, and why the numbers are not facts

**None of these figures is a measurement.** They are arithmetic on datasheet radio currents
(nRF52840) or on *assumed* currents (ESP32-S3 BLE), to show which quantities dominate and what
E6 must measure.

## Model

Cell: 3.7 V nominal, 2 000 mAh → 7.4 Wh nameplate.
Usable energy = 7.4 Wh × 0.8 (temperature + ageing derate) × 0.8 (stop at 20 % reserve) × 0.9
(buck/DC-DC efficiency) = **4.26 Wh**.

Average load at the 3.0 V rail:

```
I_avg = δ_scan · I_rx + f_tx · t_event · I_tx + I_cpu,avg + I_flash,avg + I_sleep + I_reg,q
P     = 3.0 V · I_avg ;   runtime = 4.26 Wh / P
t_event (3 primaries + 3 AUX on 2M) ≈ 3 × 136 µs + 3 × 1 064 µs = 3.6 ms
```

## Scenarios [estimate]

| Scenario | assumptions | I_avg | runtime |
|---|---|---|---|
| nRF52840, alone, idle scan 5 % | I_rx 6.26 mA [spec]; 0.5 mA CPU/flash/regulator **assumed** | 0.81 mA | ≈ 1 750 h (73 d) |
| nRF52840, crowd, scan 30 %, ~2 events/s | + 0.05 mA TX [spec-derived]; 0.6 mA other **assumed** | 2.5 mA | ≈ 560 h (23 d) |
| nRF52840, LISTEN in crowd | no TX | 2.5 mA | ≈ 570 h |
| ESP32-S3, crowd, scan 30 %, BLE RX **assumed 40 mA**, 8 mA other **assumed** | — | 20 mA | ≈ 71 h (3 d) |
| ESP32-S3, crowd, BLE RX **assumed 80 mA** | — | 32 mA | ≈ 44 h (2 d) |
| ESP32-S3, alone, 5 % scan, **assumed 60 mA** RX | — | 6 mA | ≈ 240 h (10 d) |

## What dominates

1. **Scan duty × receive current.** Transmission is < 2 % of the nRF52840 budget in the crowd
   case; listening is > 70 %. LISTEN therefore costs about the same energy as COURIER.
2. The ESP32-S3 BLE receive current is the single most important unknown (E6).
3. Simulation energy outputs (`energy_mAh_*` in results) count only radio-on time × nRF52840
   datasheet currents; they are comparative across strategies, not predictions of battery life.

## Safety

Never connect a single Li-ion cell directly to the UNO R4's VIN (needs ≥ 6 V) or 5 V pin. Use a
protected cell, a proper charger IC (CC/CV, thermal limit), and either a buck-boost to 3.3 V
(ESP32-S3) or the nRF52840's own regulator path. Firmware enforces the 20 % / 10 % thresholds
(spec §9) but cannot replace the protection circuit.
