/* Host test: cross-checks the C core against Python vectors, then fuzzes it.
 * Build: make test   (uses -fsanitize=address,undefined)
 */
#include "zm_core.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int hexval(int c) { return c <= '9' ? c - '0' : (c | 32) - 'a' + 10; }
static size_t unhex(const char *s, uint8_t *out, size_t max) {
    size_t n = 0;
    while (s[0] && s[1] && s[0] != '\n' && n < max) { out[n++] = (uint8_t)(hexval(s[0]) << 4 | hexval(s[1])); s += 2; }
    return n;
}

/* tiny "store": set of sid64s */
static uint8_t store[512][8]; static int nstore;
static bool have(const uint8_t sid[8], void *ctx) {
    (void)ctx;
    for (int i = 0; i < nstore; i++) if (!memcmp(store[i], sid, 8)) return true;
    return false;
}

static uint64_t rng = 0x9E3779B97F4A7C15ull;
static uint32_t rnd(void) { rng ^= rng << 13; rng ^= rng >> 7; rng ^= rng << 17; return (uint32_t)rng; }

int main(void) {
    FILE *fp = fopen("vectors.txt", "r");
    if (!fp) { perror("vectors.txt"); return 2; }
    static char line[20000];
    static uint8_t frames[400][ZM_FRAME_MAX]; static size_t flen[400]; int nf = 0;
    static zm_rx rx; zm_rx_init(&rx, 120000);
    int expect_ok = 0, expect_n = 0, fails = 0;
    uint8_t got_id[32]; int got = 0;
    uint8_t salt[4] = {1, 2, 3, 4}; uint16_t want_d[ZM_BUCKETS]; zm_sdb sdb;

    while (fgets(line, sizeof line, fp)) {
        if (line[0] == 'F') {
            uint8_t f[ZM_FRAME_MAX + 8]; size_t n = unhex(line + 2, f, sizeof f);
            memcpy(frames[nf], f, n); flen[nf++] = n;
            const uint8_t *cpo; uint16_t clen; uint8_t id[32];
            zm_rc rc = zm_rx_frame(&rx, f, n, 1000, have, NULL, &cpo, &clen, id);
            if (rc == ZM_COMPLETE) { memcpy(got_id, id, 32); got = 1; memcpy(store[nstore++], id, 8); }
            else if (rc != ZM_OK) { printf("unexpected rc %d\n", rc); fails++; }
        } else if (line[0] == 'E') {
            uint8_t id[32]; unhex(line + 2, id, 32); expect_n++;
            if (got && !memcmp(id, got_id, 32)) expect_ok++; else { printf("vector %d: id mismatch\n", expect_n); fails++; }
            got = 0;
        } else if (line[0] == 'S') {
            uint8_t f[ZM_FRAME_MAX]; size_t n = unhex(line + 2, f, sizeof f);
            if (zm_parse_sdb(f, n, &sdb) != ZM_OK) { puts("sdb parse failed"); fails++; }
        } else if (line[0] == 'D') {
            char *p = line + 2;
            for (unsigned b = 0; b < ZM_BUCKETS; b++) want_d[b] = (uint16_t)strtoul(p, &p, 10);
            for (unsigned b = 0; b < ZM_BUCKETS; b++)
                if (sdb.digest[b] != want_d[b]) { printf("sdb digest %u mismatch\n", b); fails++; break; }
        } else if (line[0] == 'B') {
            char *p = line + 2; unsigned b = (unsigned)strtoul(p, &p, 10); p++;
            static uint8_t sids[256][8]; size_t k = unhex(p, (uint8_t *)sids, sizeof sids) / 8;
            if (zm_bucket_digest(salt, (const uint8_t (*)[8])sids, k) != want_d[b]) {
                printf("bucket %u digest mismatch\n", b); fails++;
            }
        }
    }
    fclose(fp);
    printf("vectors: %d/%d objects reassembled with matching ids\n", expect_ok, expect_n);

    /* re-delivery of every frame must be rejected as already held (I1 at receive path) */
    int dup_ok = 0;
    for (int i = 0; i < nf; i++) {
        const uint8_t *cpo; uint16_t clen; uint8_t id[32];
        zm_rc rc = zm_rx_frame(&rx, frames[i], flen[i], 2000, have, NULL, &cpo, &clen, id);
        if (rc == ZM_E_HAVE) dup_ok++;
    }
    printf("duplicates rejected: %d/%d\n", dup_ok, nf);
    if (dup_ok != nf) fails++;

    /* fuzz: mutate known-good frames, feed with an EMPTY store so reassembly is exercised */
    nstore = 0; zm_rx_init(&rx, 50);
    long iters = 2000000, completes = 0, bad_complete = 0;
    for (long it = 0; it < iters; it++) {
        uint8_t f[ZM_FRAME_MAX + 16]; int src = (int)(rnd() % (unsigned)nf);
        size_t n = flen[src]; memcpy(f, frames[src], n);
        int muts = (int)(rnd() % 4);
        for (int m = 0; m < muts; m++) {
            switch (rnd() % 4) {
            case 0: if (n) f[rnd() % n] = (uint8_t)rnd(); break;
            case 1: if (n) f[rnd() % n] ^= (uint8_t)(1u << (rnd() % 8)); break;
            case 2: if (n) n--; break;
            default: if (n < sizeof f) f[n++] = (uint8_t)rnd(); break;
            }
        }
        const uint8_t *cpo; uint16_t clen; uint8_t id[32];
        zm_rc rc = zm_rx_frame(&rx, f, n, (uint32_t)it, NULL, NULL, &cpo, &clen, id);
        if (rc == ZM_COMPLETE) {
            completes++;
            /* every completed object must re-hash to its id and validate */
            uint8_t lv[ZM_MAX_CHUNKS][ZM_LEAF]; uint8_t k = 0, id2[32];
            for (uint16_t o = 0; o < clen; o = (uint16_t)(o + ZM_CHUNK), k++)
                zm_leaf(k, cpo + o, (uint16_t)(((unsigned)(clen - o) < ZM_CHUNK) ? (unsigned)(clen - o) : ZM_CHUNK), lv[k]);
            zm_id_from_leaves(clen, (const uint8_t (*)[ZM_LEAF])lv, k, id2);
            if (memcmp(id, id2, 32) || zm_validate_cpo(cpo, clen) != ZM_OK) bad_complete++;
        }
    }
    printf("fuzz: %ld frames, %ld completions, %ld invalid completions\n", iters, completes, bad_complete);
    printf("static RAM of receiver state: %zu bytes (ZM_SLOTS=%u)\n", sizeof(zm_rx), ZM_SLOTS);
    if (bad_complete) fails++;
    printf(fails ? "FAIL\n" : "PASS\n");
    return fails ? 1 : 0;
}
