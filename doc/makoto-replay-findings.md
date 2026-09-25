# Makoto playback and CPU findings — 2026-09-25

These measurements concern our local music port, not the original PC-98 player's
CPU usage. [Complete numeric results and hashes](makoto-replay-results.json).
No game ROM, music/instrument assets, reference driver or recordings are included.

## Hardware and listening

The owner confirmed 256 KiB sample RAM and Master/SSG controls. The PCB photos
show YM2608B and YM3016-D. Clock and current-board IRQ wiring await the designer's
confirmation. Emulation provisionally uses 8 MHz, with IRQ disconnected by default.
The wrapper is our openMSX integration; synthesis uses the pinned BSD-licensed YMFM.

The local demo sounded substantially better on R800. Earlier 50/30 controls partly
compensated for overloaded Z80 sequencing. Latest preferred balance: Master 50 /
SSG 50, now the new-profile default. Common gain remains 192000 (16x the initial
trial). This is a listening preference, not calibrated analogue circuit modeling.
The original instrument banks matter: thunder uses bank 12 (KIKI), both opening
themes bank 11. The reported trailing thunder sound disappeared with its correct
bank. Do not compensate for wrong instruments or timer overload using the mixer.

## ROM-resident optimized replay experiments

Two local builds preserve original musical register ordering: Z80 arithmetic
tables, and R800 native multiplication. Both execute from cartridge ROM. Tables
replace tempo arithmetic and, on Z80, instrument offsets, gate duration and PRNG
multiplication. Both shorten state access, shifts, block copies and BUSY-ready I/O.

Code, tables, songs and instrument banks stay in ROM. The ASCII16 demos grow from
128 to 256 KiB, duplicating instruments to remove up to 4,493 bytes of playback
buffers. State/scratch uses 1,556 bytes plus stack; demo state reserves 32 bytes.
This has not been integrated into the game. No self-modifying code is used.

Twenty emulated seconds per entry, same bank before/after:

| CPU / track | Prior CPU | Optimized CPU | Late counter before / after |
|---|---:|---:|---:|
| Z80 / Theme A | 58.68% | 51.27% | 225 / 90 |
| Z80 / Theme B | 35.39% | 32.49% | 117 / 76 |
| R800 / Theme A | 28.55% | 25.05% | 12 / 6 |
| R800 / Theme B | 17.43% | 16.03% | 5 / 3 |

Baseline R800 already selected R800, but retained the older Z80 instruction
sequence. Machines: Sanyo PHC-70FD2 and Panasonic FS-A1GT. Percentages measure
emulated time inside sequencer calls, including chip BUSY/writes, excluding
startup priming, loading, UI, outer polling/acknowledgment and game workload.

Late means another timer overflow was pending on return. One sticky flag can
merge multiple overflows; this counter cannot count all lost periods. Busy ticks
still overrun, including on R800. Ordered writes do not guarantee correct timing.

## Original English IC.ROM baseline

The unmodified 4 MiB English game was booted on FS-A1GT, with the original sound
menu selecting FM or MIDI, then the opening demo. The game selected R800.
Machine time 120–160 seconds was profiled with actual sound-port activity.
FM used 3.67%; MIDI selection used 4.36% combined (3.10% FM service + 1.26% MIDI).
FM continues servicing in MIDI mode. Original timing includes banked dispatch.

Saved symbols were stale, so actual runtime bytes were inspected. Entry E02Dh:
FM IX high=04h/IY=8000h, return E7B5h; MIDI IX high=10h/IY=4000h, return E6EEh.
Different arrangements, update frequencies, code placement and measurement windows
prevent an exact musical comparison. These are game CPU-budget references.

Theme A has about 200 sequencer calls/second versus about 60 measured original
MSX FM service calls/second. Tables alone cannot remove translated register/state
overhead or chip I/O. A subsequent handwritten Z80 implementation is measured below; game integration
remains separate.

## Validation

- All 55 entries on each optimized CPU build matched original-driver musical
  writes in eight-second excerpts: 307,306 Z80 and 314,868 R800. Timer/SSG GPIO
  differences excluded; mixer GPIO bits masked.
- Z80: 55 x 1,200 ticks with fade and normalized state, plus stop/restart,
  temporary restore, 500 random cases and all 255 valid byte tempos passed.
- Both loaders: 660 song/bank pairings matched while former playback RAM stayed
  untouched. Exported ASM rebuilt both ROMs byte-for-byte.
- R800 ROM-mode address/data spacing was at least 3.352 us across 12,335 writes,
  above the adapter's 2.125 us target at 8 MHz. RAM execution was not tested.
- Synthetic emulator BUSY, both timers, cancellation, peeks, reset and exact chip/
  timer state continuation tests are in Contrib/makoto-test.py.
- Analogue calibration, sample-RAM transfer behavior, IRQ and broader hardware
  timing remain open. Host resampler buffers are not serialized.

These are bounded tests, not full-length coverage of every song or proof of
hardware accuracy. The copyrighted music assets and demos remain local.

## Handwritten standard-Z80 rewrite

A new local implementation replaces translated x86 register bookkeeping with
native channel/command/envelope/output/modulation routines. It uses only standard
Z80 instructions; the same ROM runs on both CPUs, with the demo selecting R800
ROM mode via the BIOS on a turbo R. Code, lookup tables and assets stay in ROM.
Replay state reserves 976 bytes (including five alignment bytes), plus 32 bytes
for demo state and the stack/BIOS workspace. No self-modifying code is used.

| CPU / track | Previous optimized CPU | Native CPU | Late counter before / after |
|---|---:|---:|---:|
| Z80 / Theme A | 51.27% | 38.65% | 90 / 33 |
| Z80 / Theme B | 32.49% | 24.75% | 76 / 14 |
| R800 / Theme A | 25.05% | 18.69% | 6 / 2 |
| R800 / Theme B | 16.03% | 11.85% | 3 / 1 |

Same 20-second measurement scope and late-counter limitations as above. The core
uses direct Z80 state access, ROM tables for tempo/instrument offsets/gate/PRNG,
and an unrolled unsigned-remainder routine. This is compatible with the original
music format and tuning data; it is not a claim of clean-room provenance.

- All 55 entries pass 1,200 ticks against original x86 writes and normalized state,
  with fade at tick 900. Stop/restart, temporary music, SSG effect restoration,
  all 255 tempos, 5,000 seeded random cases and ROM-write guards pass.
- Final ROM tests in openMSX match 309,460 Z80 and 315,461 R800 ordered musical
  writes over the 55 eight-second excerpts on each CPU. Timer/GPIO exclusions and
  mixer masking remain the same. These are not full-length song tests.
- All 660 song/bank combinations, unused former asset buffers and missing-device
  timeout pass. Standalone ASM rebuild matches the final demo byte for byte.
- Minimum R800 address-to-data spacing remains 3.352 us over 12,351 writes,
  above the 2.125 us target at nominal 8 MHz.

[Native rewrite numeric results and hashes](makoto-native-replay-results.json).
The demo, source bundle containing music assets and English game remain local.
Z80 still has overruns and R800 has occasional late ticks; the original game's
FM/MIDI service remains lighter. This is not yet an in-game replacement.
