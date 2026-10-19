/* zb1_bringup_main.cpp
 * ZB-1 bring-up sketch (Arduino IDE / arduino-cli, arduino-esp32 core).
 *
 * Exercises every ZB-1 subsystem that ZEMIZDAT needs:
 *   1. battery voltage via the VBAT/2 divider
 *   2. microSD power switch + 4-bit SDMMC mount (falls back to 1-bit), card size
 *   3. BLE 5 anonymous, non-connectable extended advertising carrying a ZEMIZDAT
 *      FRAG frame (experiment E1 transmitter role)
 *   4. passive BLE scanning that feeds every ZEMIZDAT frame through zm_core.c and
 *      reports verified completions (experiment E1/E2 receiver role)
 *
 * Roles: hold BOOT at power-up -> LISTEN (scan only, never advertises);
 *        otherwise COURIER (advertise + scan).
 *
 * Build requirements (see ../../README.md §9):
 *   - board: "ESP32S3 Dev Module", USB CDC On Boot: Enabled, Flash 8MB, PSRAM: disabled
 *     (or the zemizdat_zb1 variant once installed)
 *   - library NimBLE-Arduino 1.4.x with CONFIG_BT_NIMBLE_EXT_ADV=1 and
 *     CONFIG_BT_NIMBLE_MAX_EXT_ADV_DATA_LEN=1650 (edit nimconfig.h, or pass as build flags)
 */
#include <Arduino.h>
#include <NimBLEDevice.h>
#include <SD_MMC.h>
#include "zb1_board.h"
extern "C" {
#include "zm_core.h"
}

#if !CONFIG_BT_NIMBLE_EXT_ADV
#error "Enable CONFIG_BT_NIMBLE_EXT_ADV=1 in NimBLE-Arduino (nimconfig.h or build flags)"
#endif

static const uint16_t ZM_COMPANY_ID = 0xFFFF;   // SIG test ID: prototypes only (wire_format.md §4)

/* Worked example 1 from 03_protocol/wire_format.md: single-chunk, self-certifying FRAG */
static const uint8_t kTestFrame[62] = {
  0x5a,0x12,0x00,0x00,0x01,0x00,0x2e,0x00,0x56,0x2a,0xb3,0xb8,0xfe,0xf3,0xe6,0x3e,
  0x01,0x00,0x22,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x54,0x72,0x75,0x74,
  0x68,0x20,0x73,0x75,0x72,0x76,0x69,0x76,0x65,0x73,0x20,0x77,0x69,0x74,0x68,0x6f,
  0x75,0x74,0x20,0x70,0x65,0x72,0x6d,0x69,0x73,0x73,0x69,0x6f,0x6e,0x2e};

static bool g_listen_only = false;
static zm_rx g_rx;                      // 17 KB static receive state (I3: no heap)
static uint8_t g_have[64][8];           // tiny stand-in for the flash index
static volatile int g_nhave = 0;
static volatile uint32_t g_frames = 0, g_completes = 0, g_rejects = 0;

static bool have_sid(const uint8_t sid[8], void *) {
  for (int i = 0; i < g_nhave; i++) if (!memcmp(g_have[i], sid, 8)) return true;
  return false;
}

/* ---------------------------------------------------------------- battery */
static float read_vbat() {
  analogSetPinAttenuation(ZB1_VBAT_SENSE, ADC_11db);
  uint32_t mv = 0;
  for (int i = 0; i < 16; i++) mv += analogReadMilliVolts(ZB1_VBAT_SENSE);
  return 2.0f * (mv / 16) / 1000.0f;      // 1M/1M divider
}

/* ---------------------------------------------------------------- microSD */
static void sd_test() {
  pinMode(ZB1_SD_DETECT, INPUT);          // 100k external pull-up; low = card present
  if (digitalRead(ZB1_SD_DETECT) == HIGH) { Serial.println("[sd] no card"); return; }
  digitalWrite(ZB1_SD_PWR_EN, HIGH);      // TPS22917 on
  delay(5);
  bool ok = SD_MMC.setPins(ZB1_SD_CLK, ZB1_SD_CMD, ZB1_SD_D0, ZB1_SD_D1, ZB1_SD_D2, ZB1_SD_D3)
            && SD_MMC.begin("/sdcard", false /* 4-bit */);
  if (!ok) {
    Serial.println("[sd] 4-bit mount failed, trying 1-bit");
    ok = SD_MMC.begin("/sdcard", true);
  }
  if (ok) {
    Serial.printf("[sd] type=%d size=%llu MB used=%llu MB\n", (int)SD_MMC.cardType(),
                  SD_MMC.cardSize() / (1024ULL * 1024ULL), SD_MMC.usedBytes() / (1024ULL * 1024ULL));
    SD_MMC.end();
  } else {
    Serial.println("[sd] mount failed (exFAT cards: reformat FAT32 or use SdFat, README §6)");
  }
  digitalWrite(ZB1_SD_PWR_EN, LOW);       // power the card off: idle cards draw 0.1-1 mA
}

/* ---------------------------------------------------------------- BLE receive */
class ScanCB : public NimBLEAdvertisedDeviceCallbacks {
  void onResult(NimBLEAdvertisedDevice *dev) override {
    if (dev->getManufacturerDataCount() == 0) return;
    std::string md = dev->getManufacturerData();
    if (md.size() < 3) return;
    const uint8_t *p = (const uint8_t *)md.data();
    if ((p[0] | (p[1] << 8)) != ZM_COMPANY_ID || p[2] != ZM_MAGIC) return;
    g_frames++;
    const uint8_t *cpo; uint16_t len; uint8_t id[32];
    zm_rc rc = zm_rx_frame(&g_rx, p + 2, md.size() - 2, millis(), have_sid, nullptr, &cpo, &len, id);
    if (rc == ZM_COMPLETE) {
      g_completes++;
      if (g_nhave < 64) memcpy(g_have[g_nhave++], id, 8);
      Serial.printf("[rx] verified pamphlet %02x%02x%02x%02x… (%u B): %.*s\n", id[0], id[1], id[2],
                    id[3], len, (int)(len - ZM_CPO_HDR), (const char *)cpo + ZM_CPO_HDR);
    } else if (rc != ZM_OK && rc != ZM_E_HAVE) {
      g_rejects++;
    }
  }
};

/* ---------------------------------------------------------------- BLE transmit */
static void start_courier_adv() {
  NimBLEExtAdvertisement adv(BLE_HCI_LE_PHY_1M, BLE_HCI_LE_PHY_2M);
  adv.setLegacyAdvertising(false);
  adv.setConnectable(false);
  adv.setScannable(false);
  adv.setAnonymous(true);                 // no AdvA on air (spec §3); E1 checks the controller honours it
  std::string md;
  md.push_back((char)(ZM_COMPANY_ID & 0xFF));
  md.push_back((char)(ZM_COMPANY_ID >> 8));
  md.append((const char *)kTestFrame, sizeof kTestFrame);
  adv.setManufacturerData(md);
  adv.setTxPower(0);                      // 0 dBm: the power budget in README §3 assumes it
  adv.setMinInterval(800);                // 0.625 ms units -> 500 ms (bring-up rate, not the carousel)
  adv.setMaxInterval(800);
  NimBLEExtAdvertising *ext = NimBLEDevice::getAdvertising();
  if (ext->setInstanceData(0, adv) && ext->start(0)) Serial.println("[ble] extended advertising on");
  else Serial.println("[ble] extended advertising FAILED (record for E1)");
}

void setup() {
  pinMode(ZB1_LED, OUTPUT);
  pinMode(ZB1_SD_PWR_EN, OUTPUT);
  digitalWrite(ZB1_SD_PWR_EN, LOW);
  pinMode(ZB1_BTN_BOOT, INPUT_PULLUP);
  g_listen_only = digitalRead(ZB1_BTN_BOOT) == LOW;
  Serial.begin(115200);
  delay(1500);
  Serial.printf("\nZB-1 bring-up — role: %s\n", g_listen_only ? "LISTEN" : "COURIER");
  Serial.printf("[pwr] VBAT = %.2f V\n", read_vbat());
  sd_test();

  zm_rx_init(&g_rx, 120000);
  NimBLEDevice::init("");
  if (!g_listen_only) start_courier_adv();
  NimBLEScan *scan = NimBLEDevice::getScan();
  scan->setAdvertisedDeviceCallbacks(new ScanCB(), true /* want duplicates */);
  scan->setActiveScan(false);             // passive: LISTEN never transmits (I5)
  scan->setInterval(100);                 // ms
  scan->setWindow(30);                    // 30 % duty, the spec's crowd-mode default
  scan->start(0, nullptr, false);         // scan forever
}

void loop() {
  static uint32_t last = 0;
  if (millis() - last > 5000) {
    last = millis();
    digitalWrite(ZB1_LED, HIGH); delay(20); digitalWrite(ZB1_LED, LOW);
    Serial.printf("[stat] frames=%lu verified=%lu rejected=%lu held=%d vbat=%.2fV\n",
                  (unsigned long)g_frames, (unsigned long)g_completes, (unsigned long)g_rejects,
                  g_nhave, read_vbat());
  }
  delay(10);
}
