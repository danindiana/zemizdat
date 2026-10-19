/* ZEMIZDAT-PROTO-1.0 core receive path (C99, zero heap).
 * Portable part only: parsing, per-fragment verification, reassembly, SDB parsing,
 * bucket digests. Radio, flash and clock are platform hooks (see zm_platform_*).
 */
#ifndef ZM_CORE_H
#define ZM_CORE_H
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

#define ZM_MAGIC        0x5Au
#define ZM_VER          1u
#define ZM_T_SDB        0x1u
#define ZM_T_FRAG       0x2u
#define ZM_T_MANIFEST   0x3u
#define ZM_FRAME_MAX    236u
#define ZM_FRAG_HDR     16u
#define ZM_CHUNK        220u
#define ZM_CPO_HDR      12u
#define ZM_META_MAX     256u
#define ZM_CPO_MAX      4064u
#define ZM_MAX_CHUNKS   19u
#define ZM_LEAF         8u
#define ZM_MANIFEST_HDR 6u
#define ZM_BUCKETS      64u
#define ZM_WANTS        4u
#define ZM_SDB_LEN      (8u + 2u * ZM_BUCKETS + 8u * ZM_WANTS)
#ifndef ZM_SLOTS
#define ZM_SLOTS        4u      /* RA4M1 profile: 4 x ~4.2 KiB; ESP32-S3/nRF52840: 8 */
#endif

typedef enum {
    ZM_OK = 0, ZM_E_ENVELOPE, ZM_E_VERSION, ZM_E_TYPE, ZM_E_HEADER, ZM_E_LENGTH,
    ZM_E_LEAF, ZM_E_NO_MANIFEST, ZM_E_NO_SLOT, ZM_E_HAVE, ZM_E_CPO, ZM_COMPLETE
} zm_rc;

typedef struct {
    bool     used;
    uint8_t  sid[8];
    uint8_t  total;
    uint16_t length;
    uint8_t  leaves[ZM_MAX_CHUNKS][ZM_LEAF];
    uint32_t have_mask;
    uint32_t last_ms;
    uint8_t  buf[ZM_MAX_CHUNKS * ZM_CHUNK];     /* 4180 B; flash-backed on small MCUs */
} zm_slot;

typedef struct {
    zm_slot  slot[ZM_SLOTS];
    uint32_t timeout_ms;
    uint32_t n_bad_leaf, n_no_manifest, n_complete, n_rejected;
} zm_rx;

/* platform hook: true if a committed record with this sid64 exists (or is tombstoned
 * by the user). Implemented by the store; binary search over the sorted index. */
typedef bool (*zm_have_fn)(const uint8_t sid[8], void *ctx);

void   zm_sha256(const uint8_t *d, size_t n, uint8_t out[32]);
void   zm_leaf(uint8_t idx, const uint8_t *chunk, uint16_t n, uint8_t out[ZM_LEAF]);
void   zm_id_from_leaves(uint16_t len, const uint8_t (*leaves)[ZM_LEAF], uint8_t n, uint8_t out[32]);
zm_rc  zm_validate_cpo(const uint8_t *cpo, uint16_t n);
void   zm_rx_init(zm_rx *rx, uint32_t timeout_ms);

/* Process one received frame. On ZM_COMPLETE, *out_cpo / *out_len / out_id describe a
 * verified canonical object living in rx-owned memory until the next call. */
zm_rc  zm_rx_frame(zm_rx *rx, const uint8_t *f, size_t n, uint32_t now_ms,
                   zm_have_fn have, void *ctx,
                   const uint8_t **out_cpo, uint16_t *out_len, uint8_t out_id[32]);

/* SDB */
typedef struct {
    uint8_t  congestion;
    uint8_t  salt[4];
    uint16_t digest[ZM_BUCKETS];
    uint8_t  wants[ZM_WANTS][8];
    uint8_t  n_wants;
} zm_sdb;
zm_rc  zm_parse_sdb(const uint8_t *f, size_t n, zm_sdb *out);
/* digest of one bucket from a sorted run of sid64s (streamed from the flash index) */
uint16_t zm_bucket_digest(const uint8_t salt[4], const uint8_t (*sids)[8], size_t n);

#endif
