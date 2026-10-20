/*
 * e1_main.cpp — ZB-1 experiment E1 harness.
 *
 * Drives the NimBLE C GAP API directly (ble_gap_ext_adv_* / ble_gap_ext_disc) after
 * NimBLEDevice::init(""), so payloads larger than one AD structure can be chained across
 * AUX_CHAIN_IND PDUs and the receiver sees the raw extended-report fragment status
 * (COMPLETE / INCOMPLETE / TRUNCATED).
 *
 * Board 1 transmits; board 2 receives ('r') and verifies SHA-256 of every reassembled stream;
 * an nRF52840 dongle + Wireshark checks what is actually on air (AdvA absent, chain length, PHY).
 *
 * Origin: contributed draft, reviewed and corrected for NimBLE-Arduino 1.4.3 (see README.md,
 * "Changes from the draft").
 *
 * Required build flags (or the same #defines in NimBLE-Arduino/src/nimconfig.h):
 *   -DCONFIG_BT_NIMBLE_EXT_ADV=1 -DCONFIG_BT_NIMBLE_MAX_EXT_ADV_DATA_LEN=1650
 *   -DCONFIG_BT_NIMBLE_MSYS1_BLOCK_COUNT=24
 */
#include <Arduino.h>
#include <NimBLEDevice.h>
#include <mbedtls/sha256.h>
#include <mbedtls/version.h>

#if defined(CONFIG_NIMBLE_CPP_IDF)
#  include "host/ble_gap.h"
#  include "host/ble_hs.h"
#  include "os/os_mbuf.h"
#else
#  include "nimble/nimble/host/include/host/ble_gap.h"
#  include "nimble/nimble/host/include/host/ble_hs.h"
#  include "nimble/porting/nimble/include/os/os_mbuf.h"
#endif

#if !CONFIG_BT_NIMBLE_EXT_ADV
#  error "Build with -DCONFIG_BT_NIMBLE_EXT_ADV=1 (see README.md)"
#endif
#if CONFIG_BT_NIMBLE_MAX_EXT_ADV_DATA_LEN < 1650
#  error "Build with -DCONFIG_BT_NIMBLE_MAX_EXT_ADV_DATA_LEN=1650 (mode M3 needs 1615 B of AD data)"
#endif

/* mbedtls 2.x (arduino-esp32 core 2.0.x) has the *_ret variants; 3.x (core 3.x) renamed them. */
#if MBEDTLS_VERSION_MAJOR >= 3
#  define SHA_START(c)        mbedtls_sha256_starts((c), 0)
#  define SHA_UPDATE(c, p, n) mbedtls_sha256_update((c), (p), (n))
#  define SHA_FINISH(c, o)    mbedtls_sha256_finish((c), (o))
#else
#  define SHA_START(c)        mbedtls_sha256_starts_ret((c), 0)
#  define SHA_UPDATE(c, p, n) mbedtls_sha256_update_ret((c), (p), (n))
#  define SHA_FINISH(c, o)    mbedtls_sha256_finish_ret((c), (o))
#endif

// --- ZB-1 pins (pinmap.csv) ---
static const int PIN_LED_RED     = 47;   // IO47: LED1
static const int PIN_BUTTON_BOOT = 0;    // IO0: SW2 BOOT

// HCI LE Extended Advertising Report: Address_Type 0xFF = "no address provided (anonymous)".
// NimBLE passes the controller's value through unchanged (ble_hs_hci_evt.c).
static const uint8_t ADDR_TYPE_ANONYMOUS = 0xFF;

// --- E1 test matrix ---
struct E1Mode {
    const char* name;
    uint16_t    payload_len;   // logical bytes; > ~245 B of AD data forces AUX_CHAIN_IND
    uint8_t     anonymous;     // 1 = omit AdvA, 0 = advertise with a fresh non-resolvable address
    uint8_t     sec_phy;       // BLE_HCI_LE_PHY_2M or BLE_HCI_LE_PHY_1M
    uint32_t    itvl_units;    // 0.625 ms units (800 = 500 ms)
};

static const E1Mode kModes[] = {
    {"M0:  200 B | single AUX_ADV_IND | anon=1 | 2M",  200, 1, BLE_HCI_LE_PHY_2M, 800},
    {"M1: 1088 B | chained (5 AD)     | anon=1 | 2M", 1088, 1, BLE_HCI_LE_PHY_2M, 800},
    {"M2: 1088 B | chained (5 AD)     | anon=0 | 2M", 1088, 0, BLE_HCI_LE_PHY_2M, 800},
    {"M3: 1580 B | chained (7 AD)     | anon=1 | 2M", 1580, 1, BLE_HCI_LE_PHY_2M, 800},
    {"M4: 1088 B | chained (5 AD)     | anon=1 | 1M", 1088, 1, BLE_HCI_LE_PHY_1M, 800},
    // The test_plan.md E1 case: one ZEMIZDAT event = AUX_ADV_IND + 2 x AUX_CHAIN_IND, ~720 B AdvData
    {"M5:  705 B | 3-PDU spec event   | anon=1 | 2M",  705, 1, BLE_HCI_LE_PHY_2M, 800},
};
static constexpr size_t kNumModes = sizeof(kModes) / sizeof(kModes[0]);

// --- runtime state ---
static size_t   g_mode_idx   = 5;      // M5 = the E1 pass/fail case in 08_verification/test_plan.md
static bool     g_tx_enabled = true;
static bool     g_rx_enabled = false;
static uint32_t g_tx_seq     = 0;
static int8_t   g_tx_power   = 0;      // dBm; 0 matches the battery budget (README §3)
static bool     g_scan_full  = false;  // false: 30 % duty (the E1 procedure), true: 100 %

struct RxStats {
    uint32_t adv_complete = 0, adv_incomplete = 0, adv_truncated = 0;
    uint32_t zm_valid = 0, zm_bad_sha = 0, interleaved = 0, overflow = 0;
    uint32_t anon_seen = 0, addr_seen = 0;
    // HCI report fragments per chain (index 7 = 7 or more). The controller splits reports by its
    // own buffer size, so this tracks PDUs only approximately; the sniffer is authoritative.
    uint32_t frags_complete[8] = {0};
    uint32_t frags_truncated[8] = {0};
};
static volatile RxStats g_stats;

// One reassembly slot, keyed by (address type, address, SID). A fragment from a different
// advertiser while a chain is in progress aborts that chain (counted as "interleaved").
static uint8_t  g_reasm_buf[1650];
static size_t   g_reasm_len = 0;
static bool     g_reasm_active = false;
static uint8_t  g_reasm_key[8];
static uint8_t  g_reasm_frags = 0;

// Large scratch buffers are static: the NimBLE host task stack is only 4 KB
// (CONFIG_BT_NIMBLE_HOST_TASK_STACK_SIZE) and the RX path runs on it.
static uint8_t  g_logical_rx[1600];
static uint8_t  g_logical_tx[1600];
static uint8_t  g_ad_wire[1650];

/* Logical stream (test payload, deliberately NOT the ZEMIZDAT wire format):
 *   [0..1] 'Z','M'   [2..5] seq (LE)   [6..7] total length N (LE)
 *   [8..N-33] deterministic body       [N-32..N-1] SHA-256 over [0..N-33]
 * Carried as consecutive Manufacturer Specific Data AD structures (company 0xFFFF, SIG test ID):
 *   [len][0xFF][0xFF 0xFF][chunk index][<=248 bytes]                                     */
static size_t build_chained_ad_stream(uint8_t* out_ad, size_t max_out, uint16_t n, uint32_t seq) {
    if (n < 48) n = 48;
    if (n > sizeof(g_logical_tx)) n = sizeof(g_logical_tx);
    uint8_t* L = g_logical_tx;
    L[0] = 'Z'; L[1] = 'M';
    memcpy(&L[2], &seq, 4);
    memcpy(&L[6], &n, 2);
    for (uint16_t i = 8; i < n - 32; ++i) L[i] = static_cast<uint8_t>((i ^ (seq & 0xFF)) & 0xFF);

    mbedtls_sha256_context sha;
    mbedtls_sha256_init(&sha);
    SHA_START(&sha);
    SHA_UPDATE(&sha, L, n - 32);
    SHA_FINISH(&sha, &L[n - 32]);
    mbedtls_sha256_free(&sha);

    size_t out = 0, src = 0, rem = n;
    uint8_t idx = 0;
    while (rem > 0) {
        size_t chunk = rem > 248 ? 248 : rem;
        if (out + chunk + 5 > max_out) break;
        out_ad[out++] = static_cast<uint8_t>(chunk + 4);   // type + company(2) + index + data
        out_ad[out++] = 0xFF;
        out_ad[out++] = 0xFF;
        out_ad[out++] = 0xFF;
        out_ad[out++] = idx++;
        memcpy(&out_ad[out], &L[src], chunk);
        out += chunk; src += chunk; rem -= chunk;
    }
    return out;
}

static bool verify_chained_ad_stream(const uint8_t* ad, size_t ad_len, uint32_t* seq, uint16_t* out_len) {
    uint8_t* L = g_logical_rx;
    size_t n = 0, pos = 0;
    uint8_t expect_idx = 0;
    while (pos < ad_len) {
        uint8_t el_len = ad[pos];
        if (el_len == 0 || pos + 1 + el_len > ad_len) break;
        if (ad[pos + 1] == 0xFF && el_len >= 5 && ad[pos + 2] == 0xFF && ad[pos + 3] == 0xFF) {
            if (ad[pos + 4] != expect_idx++) return false;     // missing / reordered chunk
            size_t c = el_len - 4;
            if (n + c > sizeof(g_logical_rx)) return false;
            memcpy(&L[n], &ad[pos + 5], c);
            n += c;
        }
        pos += 1 + el_len;
    }
    if (n < 48 || L[0] != 'Z' || L[1] != 'M') return false;
    uint16_t declared = 0;
    memcpy(seq, &L[2], 4);
    memcpy(&declared, &L[6], 2);
    *out_len = declared;
    if (declared != n) return false;

    uint8_t h[32];
    mbedtls_sha256_context sha;
    mbedtls_sha256_init(&sha);
    SHA_START(&sha);
    SHA_UPDATE(&sha, L, declared - 32);
    SHA_FINISH(&sha, h);
    mbedtls_sha256_free(&sha);
    return memcmp(h, &L[declared - 32], 32) == 0;
}

static void make_key(const struct ble_gap_ext_disc_desc& d, uint8_t key[8]) {
    key[0] = d.addr.type;
    memcpy(&key[1], d.addr.val, 6);
    key[7] = d.sid;
}

// --- NimBLE GAP callback (scanner) ---
static int e1_gap_event_cb(struct ble_gap_event* event, void*) {
    if (event->type != BLE_GAP_EVENT_EXT_DISC) return 0;
    const struct ble_gap_ext_disc_desc& d = event->ext_disc;
    if (d.props & BLE_HCI_ADV_LEGACY_MASK) return 0;   // legacy PDUs (phones, beacons) are not part of E1

    uint8_t key[8];
    make_key(d, key);
    if (g_reasm_active && memcmp(key, g_reasm_key, 8) != 0) {
        g_stats.interleaved++;                     // another advertiser cut into a chain
        g_reasm_len = 0;
        g_reasm_active = false;
    }
    if (!g_reasm_active) {
        memcpy(g_reasm_key, key, 8);
        g_reasm_active = true;
        g_reasm_len = 0;
        g_reasm_frags = 0;
    }
    if (g_reasm_frags < 7) g_reasm_frags++;
    if (g_reasm_len + d.length_data <= sizeof(g_reasm_buf)) {
        memcpy(&g_reasm_buf[g_reasm_len], d.data, d.length_data);
        g_reasm_len += d.length_data;
    } else {
        g_stats.overflow++;
    }

    switch (d.data_status) {
    case BLE_GAP_EXT_ADV_DATA_STATUS_INCOMPLETE:
        g_stats.adv_incomplete++;
        return 0;
    case BLE_GAP_EXT_ADV_DATA_STATUS_TRUNCATED:
        g_stats.adv_truncated++;
        g_stats.frags_truncated[g_reasm_frags]++;
        g_reasm_len = 0;
        g_reasm_active = false;
        return 0;
    default:  // COMPLETE
        break;
    }
    g_stats.adv_complete++;
    g_stats.frags_complete[g_reasm_frags]++;
    const bool is_anon = d.addr.type == ADDR_TYPE_ANONYMOUS;
    uint32_t seq = 0;
    uint16_t n = 0;
    if (verify_chained_ad_stream(g_reasm_buf, g_reasm_len, &seq, &n)) {
        g_stats.zm_valid++;
        if (is_anon) g_stats.anon_seen++; else g_stats.addr_seen++;
        digitalWrite(PIN_LED_RED, !digitalRead(PIN_LED_RED));
        Serial.printf("[E1-RX] valid seq=%lu logical=%u B ad=%u B rssi=%d phy=%u/%u anon=%d sid=%u\n",
                      (unsigned long)seq, n, (unsigned)g_reasm_len, d.rssi, d.prim_phy, d.sec_phy,
                      is_anon ? 1 : 0, d.sid);
    } else if (g_reasm_len >= 7 && g_reasm_buf[1] == 0xFF && g_reasm_buf[2] == 0xFF &&
               g_reasm_buf[3] == 0xFF && g_reasm_buf[5] == 'Z' && g_reasm_buf[6] == 'M') {
        g_stats.zm_bad_sha++;
        Serial.printf("[E1-RX] BAD stream ad=%u B rssi=%d\n", (unsigned)g_reasm_len, d.rssi);
    }
    g_reasm_len = 0;
    g_reasm_active = false;
    return 0;
}

// --- extended advertising ---
static bool start_e1_ext_adv(size_t mode_idx) {
    const E1Mode& m = kModes[mode_idx];
    const uint8_t inst = 0;
    if (ble_gap_ext_adv_active(inst)) ble_gap_ext_adv_stop(inst);
    ble_gap_ext_adv_remove(inst);

    struct ble_gap_ext_adv_params p;
    memset(&p, 0, sizeof(p));
    p.connectable = 0;
    p.scannable = 0;
    p.legacy_pdu = 0;
    p.anonymous = m.anonymous;
    p.itvl_min = m.itvl_units;
    p.itvl_max = m.itvl_units + 32;          // up to +20 ms
    p.channel_map = 0x07;                     // 37, 38, 39
    p.own_addr_type = BLE_OWN_ADDR_RANDOM;
    p.primary_phy = BLE_HCI_LE_PHY_1M;        // primary must be 1M or Coded
    p.secondary_phy = m.sec_phy;
    p.tx_power = g_tx_power;
    p.sid = static_cast<uint8_t>(mode_idx & 0x0F);

    int rc = ble_gap_ext_adv_configure(inst, &p, nullptr, nullptr, nullptr);
    if (rc != 0) {
        Serial.printf("[E1-TX] ble_gap_ext_adv_configure rc=%d\n", rc);
        return false;
    }
    if (!m.anonymous) {                       // control case: a fresh non-resolvable private address
        ble_addr_t a;
        if (ble_hs_id_gen_rnd(1, &a) == 0) ble_gap_ext_adv_set_addr(inst, &a);
    }

    size_t wire = build_chained_ad_stream(g_ad_wire, sizeof(g_ad_wire), m.payload_len, ++g_tx_seq);
    struct os_mbuf* om = os_msys_get_pkthdr(wire, 0);
    if (!om) {
        Serial.printf("[E1-TX] os_msys_get_pkthdr(%u) failed: raise CONFIG_BT_NIMBLE_MSYS1_BLOCK_COUNT\n",
                      (unsigned)wire);
        return false;
    }
    rc = os_mbuf_append(om, g_ad_wire, wire);
    if (rc != 0) {
        os_mbuf_free_chain(om);
        Serial.printf("[E1-TX] os_mbuf_append rc=%d (mbuf pool exhausted?)\n", rc);
        return false;
    }
    rc = ble_gap_ext_adv_set_data(inst, om);   // takes ownership of om
    if (rc != 0) {
        Serial.printf("[E1-TX] ble_gap_ext_adv_set_data(%u B) rc=%d (controller max data length?)\n",
                      (unsigned)wire, rc);
        return false;
    }
    rc = ble_gap_ext_adv_start(inst, 0, 0);
    if (rc != 0) {
        Serial.printf("[E1-TX] ble_gap_ext_adv_start rc=%d\n", rc);
        return false;
    }
    Serial.printf("[E1-TX] started [%s] logical=%u B ad=%u B seq=%lu tx=%d dBm\n",
                  m.name, m.payload_len, (unsigned)wire, (unsigned long)g_tx_seq, g_tx_power);
    return true;
}

// --- extended scanning ---
static bool set_e1_ext_scan(bool enable) {
    if (!enable) {
        ble_gap_disc_cancel();
        Serial.println("[E1-RX] scanning stopped");
        return true;
    }
    struct ble_gap_ext_disc_params u;
    memset(&u, 0, sizeof(u));
    u.itvl = 160;                          // 100 ms
    u.window = g_scan_full ? 160 : 48;     // 100 % or 30 % duty (E1 procedure: 30 %)
    u.passive = 1;
    int rc = ble_gap_ext_disc(BLE_OWN_ADDR_RANDOM, 0, 0, 0, BLE_HCI_SCAN_FILT_NO_WL, 0,
                              &u, nullptr, e1_gap_event_cb, nullptr);
    if (rc != 0 && rc != BLE_HS_EALREADY) {
        Serial.printf("[E1-RX] ble_gap_ext_disc rc=%d\n", rc);
        return false;
    }
    Serial.printf("[E1-RX] passive extended scanning started, %d %% duty (1M primary, 1M/2M secondary)\n",
                  g_scan_full ? 100 : 30);
    return true;
}

static void print_stats() {
    Serial.printf("[E1-STATS] complete=%lu incomplete_frags=%lu truncated=%lu | valid=%lu bad=%lu "
                  "| interleaved=%lu overflow=%lu | anon=%lu addr=%lu\n",
                  (unsigned long)g_stats.adv_complete, (unsigned long)g_stats.adv_incomplete,
                  (unsigned long)g_stats.adv_truncated, (unsigned long)g_stats.zm_valid,
                  (unsigned long)g_stats.zm_bad_sha, (unsigned long)g_stats.interleaved,
                  (unsigned long)g_stats.overflow, (unsigned long)g_stats.anon_seen,
                  (unsigned long)g_stats.addr_seen);
    Serial.print("[E1-STATS] fragments per complete chain:  ");
    for (int i = 1; i < 8; ++i) Serial.printf("%d%s:%lu ", i, i == 7 ? "+" : "", (unsigned long)g_stats.frags_complete[i]);
    Serial.print("\n[E1-STATS] fragments before truncation:  ");
    for (int i = 1; i < 8; ++i) Serial.printf("%d%s:%lu ", i, i == 7 ? "+" : "", (unsigned long)g_stats.frags_truncated[i]);
    uint32_t tot = g_stats.zm_valid + g_stats.zm_bad_sha + g_stats.adv_truncated;
    Serial.printf("\n[E1-STATS] intact streams: %lu / %lu caught = %.1f %% (E1 pass at 1 m: >= 90 %%)\n",
                  (unsigned long)g_stats.zm_valid, (unsigned long)tot, tot ? 100.0 * g_stats.zm_valid / tot : 0.0);
}

static void print_help() {
    Serial.println("\n=== ZB-1 E1 harness ===");
    Serial.println("  0..5  select TX mode          t  toggle TX       r  toggle RX scan");
    Serial.println("  d     RX scan duty 30/100 %");
    Serial.println("  b     re-send with new seq    p  TX power 0/+9 dBm");
    Serial.println("  s     RX statistics           z  zero statistics  h  help");
    Serial.println("  BOOT button: next mode");
    for (size_t i = 0; i < kNumModes; ++i) Serial.printf("  [%u] %s\n", (unsigned)i, kModes[i].name);
}

void setup() {
    pinMode(PIN_LED_RED, OUTPUT);
    pinMode(PIN_BUTTON_BOOT, INPUT_PULLUP);
    digitalWrite(PIN_LED_RED, HIGH);
    Serial.begin(115200);
    for (uint32_t t0 = millis(); !Serial && millis() - t0 < 3000;) delay(10);

    NimBLEDevice::init("");
    ble_addr_t host_rnd;                       // random identity for the scanner / control mode
    if (ble_hs_id_gen_rnd(1, &host_rnd) == 0) ble_hs_id_set_rnd(host_rnd.val);

    print_help();
    start_e1_ext_adv(g_mode_idx);
    digitalWrite(PIN_LED_RED, LOW);
}

void loop() {
    static bool last_btn = HIGH;
    static uint32_t last_press = 0;
    bool btn = digitalRead(PIN_BUTTON_BOOT);
    if (btn == LOW && last_btn == HIGH && millis() - last_press > 250) {
        last_press = millis();
        g_mode_idx = (g_mode_idx + 1) % kNumModes;
        if (g_tx_enabled) start_e1_ext_adv(g_mode_idx);
    }
    last_btn = btn;

    while (Serial.available()) {
        char c = Serial.read();
        if (c >= '0' && c < static_cast<char>('0' + kNumModes)) {
            g_mode_idx = c - '0';
            if (g_tx_enabled) start_e1_ext_adv(g_mode_idx);
        } else if (c == 't' || c == 'T') {
            g_tx_enabled = !g_tx_enabled;
            if (g_tx_enabled) start_e1_ext_adv(g_mode_idx);
            else { ble_gap_ext_adv_stop(0); Serial.println("[E1-TX] advertising stopped"); }
        } else if (c == 'r' || c == 'R') {
            g_rx_enabled = !g_rx_enabled;
            set_e1_ext_scan(g_rx_enabled);
        } else if (c == 'b' || c == 'B') {
            if (g_tx_enabled) start_e1_ext_adv(g_mode_idx);
        } else if (c == 'd' || c == 'D') {
            g_scan_full = !g_scan_full;
            if (g_rx_enabled) { set_e1_ext_scan(false); set_e1_ext_scan(true); }
            else Serial.printf("[E1-RX] scan duty set to %d %%\n", g_scan_full ? 100 : 30);
        } else if (c == 'p' || c == 'P') {
            g_tx_power = g_tx_power == 0 ? 9 : 0;
            if (g_tx_enabled) start_e1_ext_adv(g_mode_idx);
        } else if (c == 's' || c == 'S') {
            print_stats();
        } else if (c == 'z' || c == 'Z') {
            memset((void*)&g_stats, 0, sizeof(g_stats));
            Serial.println("[E1-STATS] zeroed");
        } else if (c == 'h' || c == '?') {
            print_help();
        }
    }
    delay(10);
}
