/*
 * ZEMIZDAT ZB-1 — Arduino variant for arduino-esp32 (core 2.0.x and 3.x).
 * Module: ESP32-S3-MINI-1-N8 (8 MB quad flash, no PSRAM).
 * Feather-style pin names. Source of truth for the mapping: ../../../pinmap.csv
 *
 * Prototype USB IDs below are Espressif's development defaults (0x303A). A product
 * must obtain its own PID (Espressif allocates PIDs under its VID for ESP products).
 */
#ifndef Pins_Arduino_h
#define Pins_Arduino_h

#include <stdint.h>
#include "soc/soc_caps.h"

#define USB_VID          0x303A
#define USB_PID          0x1001
#define USB_MANUFACTURER "ZEMIZDAT project"
#define USB_PRODUCT      "ZB-1"
#define USB_SERIAL       ""

/* ---- on-board functions ------------------------------------------------------ */
#define ZB1_BTN_BOOT      0    /* BOOT / user button, active low, 10k pull-up */
#define ZB1_VBAT_SENSE    2    /* VBAT/2 via 1M/1M divider, ADC1_CH1 */
#define ZB1_I2C_SDA       8    /* STEMMA-QT + MAX17048 (optional) */
#define ZB1_I2C_SCL       18
#define ZB1_SD_D2         9
#define ZB1_SD_D3         10   /* = CS in SPI mode */
#define ZB1_SD_CMD        11   /* = MOSI in SPI mode */
#define ZB1_SD_CLK        12   /* = SCK in SPI mode */
#define ZB1_SD_D0         13   /* = MISO in SPI mode */
#define ZB1_SD_D1         14
#define ZB1_XTAL32_P      15   /* 32.768 kHz crystal (BLE low-power clock) */
#define ZB1_XTAL32_N      16
#define ZB1_SD_PWR_EN     21   /* TPS22917 load switch, active high, RTC GPIO */
#define ZB1_SD_DETECT     26   /* card-detect switch, active low, 100k pull-up */
#define ZB1_LED           47   /* red user LED, ~1 mA, active high */

/* defaults used by SD_MMC when the board defines BOARD_HAS_SDMMC (boards.txt) */
#define SDMMC_CLK ZB1_SD_CLK
#define SDMMC_CMD ZB1_SD_CMD
#define SDMMC_D0  ZB1_SD_D0
#define SDMMC_D1  ZB1_SD_D1
#define SDMMC_D2  ZB1_SD_D2
#define SDMMC_D3  ZB1_SD_D3

static const uint8_t LED_BUILTIN = ZB1_LED;
#define BUILTIN_LED LED_BUILTIN
#define LED_BUILTIN LED_BUILTIN

/* ---- Feather header ------------------------------------------------------------ */
static const uint8_t TX = 43;
static const uint8_t RX = 44;

static const uint8_t SDA = ZB1_I2C_SDA;
static const uint8_t SCL = ZB1_I2C_SCL;

static const uint8_t SS   = 38;   /* D10 */
static const uint8_t MOSI = 42;
static const uint8_t MISO = 48;
static const uint8_t SCK  = 41;

static const uint8_t A0 = 4;
static const uint8_t A1 = 5;
static const uint8_t A2 = 6;
static const uint8_t A3 = 7;
static const uint8_t A4 = 1;
/* A5 position is not connected on ZB-1 (pin budget, see pinmap.csv) */

static const uint8_t D5  = 17;
static const uint8_t D6  = 39;
static const uint8_t D9  = 40;
static const uint8_t D10 = 38;
static const uint8_t D11 = 33;    /* exposed on MINI-1-N8 (datasheet pin table) */
static const uint8_t D12 = 34;    /* exposed on MINI-1-N8 (datasheet pin table) */
static const uint8_t D13 = ZB1_LED;

static const uint8_t T1 = 1;
static const uint8_t T4 = 4;
static const uint8_t T5 = 5;
static const uint8_t T6 = 6;
static const uint8_t T7 = 7;

#endif /* Pins_Arduino_h */
