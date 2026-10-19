/* ZEMIZDAT-PROTO-1.0 core receive path. C99, no heap, no recursion.
 * SHA-256 is a straightforward FIPS 180-4 implementation; on hardware replace
 * zm_sha256_* with the SoC accelerator (ESP32-S3 SHA, nRF52840 CC310).
 */
#include "zm_core.h"
#include <string.h>

/* ------------------------------------------------------------------ SHA-256 */
typedef struct { uint32_t h[8]; uint64_t len; uint8_t buf[64]; size_t n; } zm_sha_ctx;

static const uint32_t K[64] = {
 0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
 0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
 0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
 0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
 0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
 0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
 0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
 0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2};
#define ROR(x,n) (((x) >> (n)) | ((x) << (32 - (n))))

static void sha_block(zm_sha_ctx *c, const uint8_t *p) {
    uint32_t w[64], a, b, d, e, f, g, h, cc, t1, t2;
    for (int i = 0; i < 16; i++)
        w[i] = (uint32_t)p[4*i] << 24 | (uint32_t)p[4*i+1] << 16 | (uint32_t)p[4*i+2] << 8 | p[4*i+3];
    for (int i = 16; i < 64; i++) {
        uint32_t s0 = ROR(w[i-15],7) ^ ROR(w[i-15],18) ^ (w[i-15] >> 3);
        uint32_t s1 = ROR(w[i-2],17) ^ ROR(w[i-2],19) ^ (w[i-2] >> 10);
        w[i] = w[i-16] + s0 + w[i-7] + s1;
    }
    a=c->h[0]; b=c->h[1]; cc=c->h[2]; d=c->h[3]; e=c->h[4]; f=c->h[5]; g=c->h[6]; h=c->h[7];
    for (int i = 0; i < 64; i++) {
        t1 = h + (ROR(e,6) ^ ROR(e,11) ^ ROR(e,25)) + ((e & f) ^ (~e & g)) + K[i] + w[i];
        t2 = (ROR(a,2) ^ ROR(a,13) ^ ROR(a,22)) + ((a & b) ^ (a & cc) ^ (b & cc));
        h=g; g=f; f=e; e=d+t1; d=cc; cc=b; b=a; a=t1+t2;
    }
    c->h[0]+=a; c->h[1]+=b; c->h[2]+=cc; c->h[3]+=d; c->h[4]+=e; c->h[5]+=f; c->h[6]+=g; c->h[7]+=h;
}
static void sha_init(zm_sha_ctx *c) {
    static const uint32_t iv[8] = {0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,
                                   0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19};
    memcpy(c->h, iv, sizeof iv); c->len = 0; c->n = 0;
}
static void sha_update(zm_sha_ctx *c, const uint8_t *d, size_t n) {
    c->len += n;
    while (n) {
        size_t k = 64 - c->n; if (k > n) k = n;
        memcpy(c->buf + c->n, d, k); c->n += k; d += k; n -= k;
        if (c->n == 64) { sha_block(c, c->buf); c->n = 0; }
    }
}
static void sha_final(zm_sha_ctx *c, uint8_t out[32]) {
    uint64_t bits = c->len * 8; uint8_t pad = 0x80, z = 0, L[8];
    sha_update(c, &pad, 1);
    while (c->n != 56) sha_update(c, &z, 1);
    for (int i = 0; i < 8; i++) L[i] = (uint8_t)(bits >> (56 - 8*i));
    sha_update(c, L, 8);
    for (int i = 0; i < 8; i++) {
        out[4*i] = (uint8_t)(c->h[i] >> 24); out[4*i+1] = (uint8_t)(c->h[i] >> 16);
        out[4*i+2] = (uint8_t)(c->h[i] >> 8); out[4*i+3] = (uint8_t)c->h[i];
    }
}
void zm_sha256(const uint8_t *d, size_t n, uint8_t out[32]) {
    zm_sha_ctx c; sha_init(&c); sha_update(&c, d, n); sha_final(&c, out);
}

/* ------------------------------------------------------------------ identity */
static uint16_t rd16(const uint8_t *p) { return (uint16_t)(p[0] | (p[1] << 8)); }

void zm_leaf(uint8_t idx, const uint8_t *chunk, uint16_t n, uint8_t out[ZM_LEAF]) {
    zm_sha_ctx c; uint8_t pre[2] = {0x00, idx}, h[32];
    sha_init(&c); sha_update(&c, pre, 2); sha_update(&c, chunk, n); sha_final(&c, h);
    memcpy(out, h, ZM_LEAF);
}
void zm_id_from_leaves(uint16_t len, const uint8_t (*leaves)[ZM_LEAF], uint8_t n, uint8_t out[32]) {
    zm_sha_ctx c; uint8_t pre[3] = {0x01, (uint8_t)len, (uint8_t)(len >> 8)};
    sha_init(&c); sha_update(&c, pre, 3);
    for (uint8_t i = 0; i < n; i++) sha_update(&c, leaves[i], ZM_LEAF);
    sha_final(&c, out);
}

/* Well-formed UTF-8 (RFC 3629): no overlongs, no surrogates, <= U+10FFFF. */
static bool utf8_ok(const uint8_t *s, size_t n) {
    size_t i = 0;
    while (i < n) {
        uint8_t b = s[i];
        if (b < 0x80) { i++; continue; }
        size_t k; uint32_t cp, min;
        if ((b & 0xE0) == 0xC0) { k = 1; cp = b & 0x1F; min = 0x80; }
        else if ((b & 0xF0) == 0xE0) { k = 2; cp = b & 0x0F; min = 0x800; }
        else if ((b & 0xF8) == 0xF0) { k = 3; cp = b & 0x07; min = 0x10000; }
        else return false;
        if (n - i <= k) return false;           /* truncated sequence */
        for (size_t j = 1; j <= k; j++) {
            if ((s[i+j] & 0xC0) != 0x80) return false;
            cp = (cp << 6) | (s[i+j] & 0x3F);
        }
        if (cp < min || cp > 0x10FFFF || (cp >= 0xD800 && cp <= 0xDFFF)) return false;
        i += k + 1;
    }
    return true;
}

zm_rc zm_validate_cpo(const uint8_t *cpo, uint16_t n) {
    if (n < ZM_CPO_HDR + 1 || n > ZM_CPO_MAX) return ZM_E_CPO;
    uint16_t blen = rd16(cpo + 2), mlen = rd16(cpo + 4);
    if (cpo[0] != ZM_VER || cpo[1] != 0 || cpo[10] != 0 || cpo[11] != 0) return ZM_E_CPO;
    if (mlen > ZM_META_MAX || blen < 1 || (uint32_t)ZM_CPO_HDR + mlen + blen != n) return ZM_E_CPO;
    const uint8_t *m = cpo + ZM_CPO_HDR;
    int last = -1;
    for (uint16_t i = 0; i < mlen;) {
        if ((uint32_t)i + 2 > mlen) return ZM_E_CPO;
        uint8_t t = m[i], ln = m[i + 1];
        if (t == 0 || (int)t <= last || (uint32_t)i + 2 + ln > mlen) return ZM_E_CPO;
        last = t; i = (uint16_t)(i + 2 + ln);
    }
    return utf8_ok(cpo + ZM_CPO_HDR + mlen, blen) ? ZM_OK : ZM_E_CPO;
}

/* ------------------------------------------------------------------ receive path */
void zm_rx_init(zm_rx *rx, uint32_t timeout_ms) {
    memset(rx, 0, sizeof *rx); rx->timeout_ms = timeout_ms;
}

static zm_slot *slot_find(zm_rx *rx, const uint8_t sid[8]) {
    for (unsigned i = 0; i < ZM_SLOTS; i++)
        if (rx->slot[i].used && memcmp(rx->slot[i].sid, sid, 8) == 0) return &rx->slot[i];
    return NULL;
}
static zm_slot *slot_alloc(zm_rx *rx, uint32_t now) {
    zm_slot *old = NULL;
    for (unsigned i = 0; i < ZM_SLOTS; i++) {
        if (!rx->slot[i].used) return &rx->slot[i];
        if (!old || rx->slot[i].last_ms < old->last_ms) old = &rx->slot[i];
    }
    if (now - old->last_ms < rx->timeout_ms) return NULL;   /* refuse rather than thrash */
    return old;
}

zm_rc zm_rx_frame(zm_rx *rx, const uint8_t *f, size_t n, uint32_t now,
                  zm_have_fn have, void *ctx,
                  const uint8_t **out_cpo, uint16_t *out_len, uint8_t out_id[32]) {
    if (n < 4 || n > ZM_FRAME_MAX || f[0] != ZM_MAGIC) return ZM_E_ENVELOPE;
    if ((f[1] >> 4) != ZM_VER) return ZM_E_VERSION;
    uint8_t t = f[1] & 0x0F;

    if (t == ZM_T_MANIFEST) {
        if (n < ZM_MANIFEST_HDR) return ZM_E_LENGTH;
        uint8_t total = f[2]; uint16_t len = rd16(f + 4);
        if (f[3] != 0 || total < 2 || total > ZM_MAX_CHUNKS) return ZM_E_HEADER;
        if (n != ZM_MANIFEST_HDR + (size_t)ZM_LEAF * total) return ZM_E_LENGTH;
        if (!(len > ZM_CHUNK * (total - 1u) && len <= ZM_CHUNK * total && len <= ZM_CPO_MAX))
            return ZM_E_LENGTH;
        uint8_t id[32];
        zm_id_from_leaves(len, (const uint8_t (*)[ZM_LEAF])(f + ZM_MANIFEST_HDR), total, id);
        if (have && have(id, ctx)) return ZM_E_HAVE;
        if (slot_find(rx, id)) return ZM_OK;
        zm_slot *s = slot_alloc(rx, now);
        if (!s) return ZM_E_NO_SLOT;
        memset(s, 0, sizeof *s);
        s->used = true; memcpy(s->sid, id, 8); s->total = total; s->length = len;
        memcpy(s->leaves, f + ZM_MANIFEST_HDR, (size_t)ZM_LEAF * total);
        s->last_ms = now;
        return ZM_OK;
    }
    if (t == ZM_T_FRAG) {
        if (n < ZM_FRAG_HDR + 1) return ZM_E_LENGTH;
        uint8_t idx = f[3], total = f[4]; uint16_t clen = rd16(f + 6);   /* f[2] reserved, ignored */
        const uint8_t *sid = f + 8, *chunk = f + ZM_FRAG_HDR;
        if (f[5] != 0 || total < 1 || total > ZM_MAX_CHUNKS || idx >= total)
            return ZM_E_HEADER;
        if (clen < 1 || clen > ZM_CHUNK || (size_t)ZM_FRAG_HDR + clen != n) return ZM_E_LENGTH;
        if (idx < total - 1 && clen != ZM_CHUNK) return ZM_E_LENGTH;
        if (have && have(sid, ctx)) return ZM_E_HAVE;
        uint8_t lf[ZM_LEAF];
        zm_leaf(idx, chunk, clen, lf);
        if (total == 1) {                       /* self-certifying single-chunk object */
            uint8_t one[1][ZM_LEAF]; memcpy(one[0], lf, ZM_LEAF);
            zm_id_from_leaves(clen, (const uint8_t (*)[ZM_LEAF])one, 1, out_id);
            if (memcmp(out_id, sid, 8) != 0) { rx->n_bad_leaf++; return ZM_E_LEAF; }
            if (zm_validate_cpo(chunk, clen) != ZM_OK) { rx->n_rejected++; return ZM_E_CPO; }
            *out_cpo = chunk; *out_len = clen; rx->n_complete++;
            return ZM_COMPLETE;
        }
        zm_slot *s = slot_find(rx, sid);
        if (!s) { rx->n_no_manifest++; return ZM_E_NO_MANIFEST; }
        if (total != s->total || memcmp(lf, s->leaves[idx], ZM_LEAF) != 0) {
            rx->n_bad_leaf++; return ZM_E_LEAF;
        }
        memcpy(s->buf + (size_t)idx * ZM_CHUNK, chunk, clen);
        s->have_mask |= (1u << idx);
        s->last_ms = now;
        if (s->have_mask == ((1u << s->total) - 1u)) {
            s->used = false;                      /* slot freed; buffer valid until next call */
            if (zm_validate_cpo(s->buf, s->length) != ZM_OK) { rx->n_rejected++; return ZM_E_CPO; }
            zm_id_from_leaves(s->length, (const uint8_t (*)[ZM_LEAF])s->leaves, s->total, out_id);
            *out_cpo = s->buf; *out_len = s->length; rx->n_complete++;
            return ZM_COMPLETE;
        }
        return ZM_OK;
    }
    if (t == ZM_T_SDB) return ZM_OK;              /* handled by zm_parse_sdb in the scheduler */
    return ZM_E_TYPE;
}

zm_rc zm_parse_sdb(const uint8_t *f, size_t n, zm_sdb *o) {
    static const uint8_t zero[8] = {0};
    if (n != ZM_SDB_LEN || f[0] != ZM_MAGIC || f[1] != ((ZM_VER << 4) | ZM_T_SDB)) return ZM_E_HEADER;
    if ((f[2] & 0xF1) || f[3]) return ZM_E_HEADER;
    o->congestion = (f[2] >> 1) & 7;
    memcpy(o->salt, f + 4, 4);
    for (unsigned b = 0; b < ZM_BUCKETS; b++) o->digest[b] = rd16(f + 8 + 2 * b);
    o->n_wants = 0;
    for (unsigned i = 0; i < ZM_WANTS; i++) {
        const uint8_t *w = f + 8 + 2 * ZM_BUCKETS + 8 * i;
        if (memcmp(w, zero, 8) != 0) memcpy(o->wants[o->n_wants++], w, 8);
    }
    return ZM_OK;
}

uint16_t zm_bucket_digest(const uint8_t salt[4], const uint8_t (*sids)[8], size_t n) {
    zm_sha_ctx c; uint8_t h[32];
    sha_init(&c); sha_update(&c, salt, 4);
    for (size_t i = 0; i < n; i++) sha_update(&c, sids[i], 8);
    sha_final(&c, h);
    return (uint16_t)(h[0] | (h[1] << 8));
}
