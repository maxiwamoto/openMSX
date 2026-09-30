# Makoto native-stream experiment — 2026-09-30

Experimental branch: `codex/makoto-native-streams`, based on fork release commit
`ad6afbc95b72ecbcfcf8f0b55b30790dde6fd0a6`. No changes pushed to master or the
upstream PR. Full measurements: [JSON](makoto-native-stream-results.json).

## Outcome

The proposed split is worth continuing. Five alternating paired runs measured
20.5% less whole-emulator CPU time for actual music and 37.6% less with separate
channel buffers active. Idle improves 9.2%; its remaining cost is still too high
to recommend adding Makoto to every Boosted machine by default.

This measures host emulator cost, not the Z80/R800 music driver's frame budget.
The user compared playback and reported no audible difference. This was informal
listening, not a blind test, and does not establish that playback sounds better.

## Implementation

Wouter proposed separate native FM/ADPCM and SSG streams in
[PR #2209](https://github.com/openMSX/openMSX/pull/2209#issuecomment-5906221421).
The subclass approach follows
[madscient's prototype](https://github.com/openMSX/openMSX/pull/2209#issuecomment-5910617531)
(`openMSX_Y8960` revision `d84efe46ef759b525e57cc36a59c04f40e73c15a`).

The wrapper bypasses YMFM's combined 1 MHz generator, using its protected clock
methods. No additional YMFM core changes are needed. Our existing channel taps,
hardware transfer fixes, debugger peeks and built-in rhythm samples remain.

| Prescaler | FM + rhythm + ADPCM (stereo) | SSG (mono) |
|---|---:|---:|
| 6 | 8 MHz / 144 | 250 kHz |
| 3 | 8 MHz / 72 | 500 kHz |
| 2 | 8 MHz / 48 | 1 MHz |

The host API takes integer rates, so FM rates are rounded to the nearest Hz
(less than 10 ppm at the normal setting). Both resamplers update on address-only
prescaler writes and debugger writes. `updateStream()` already flushes the
whole mixer, including both devices; a second call is unnecessary.

All 16 voices remain available: `Makoto` channels 1–6 are FM, 7 is ADPCM-B,
8–13 are rhythm; `Makoto SSG` channels 1–3 are SSG. SSG mono centre-pan gain is
compensated so equal device volumes retain the previous calibrated balance.
The existing `makoto_psg_volume` trim remains for this experiment. UI/control
consolidation is deferred: `Makoto_volume` now affects FM/ADPCM only, and
`Makoto SSG_volume` affects SSG. This is not yet a replacement for the physical
master knob controlling both parts together.

State version 8 stores both native sample clocks. Fork versions 1–7 still have
load paths; versions 6 and 7 were exercised here. Old core/RAM/timer state and
the saved clock timestamp are preserved, while native periods are reconstructed.
Their old 1 MHz sample-hold phase cannot be resumed identically. Fresh native
states preserve exact chip/clock continuation. Host resampler histories are not
serialized, consistent with the existing integration.

## Performance

Windows x64, MSVC v145 Release, same machine/profile/firmware, Turbo-R R800,
renderer disabled, dummy audio, unthrottled emulation, 60 emulated seconds per
case, five alternating baseline/native pairs. Bustling Town from the supplied
37-track ROM; ROM and executable hashes are in the JSON. No game assets are
included in this repository report. Other emulation tests and builds were not
run concurrently with the benchmark.

| Workload | Current release CPU seconds | Native CPU seconds | Reduction |
|---|---:|---:|---:|
| No Makoto | 2.9844 | 3.0313 | control / run variation |
| Makoto idle in BASIC | 4.5938 | 4.1719 | 9.2% |
| Bustling Town | 7.2500 | 5.7656 | 20.5% |
| Bustling Town, channel tools | 10.0156 | 6.2500 | 37.6% |

Values are medians. Paired reductions range 6.2–9.4% idle, 18.5–25.8% music and
34.5–39.0% channel tools. Both FM and SSG use separate channel buffers in the
channel-tools case. Whole-emulator ratios versus each build's no-Makoto baseline
are 1.539 → 1.376 idle, 2.429 → 1.902 music and 3.356 → 2.062 with channel tools.
These are local results, not a universal speedup or the other fork's measurements.

## Verification

- 1,080,000 source sample comparisons: zero differences at prescalers 6, 3, 2.
  All 16 voices exercised, including actual built-in rhythm samples, synthetic
  sample RAM, SSG noise/envelope and register changes while playing. Deliberately
  keying off native FM detects 107,967 differences (negative control).
- V4/V5 diagnostic results still match the photographed Makoto hardware.
  MSX2 and Turbo-R both complete, with/without the extension, and leave IRQ clear.
- Timer A/B, BUSY, peeks, CPU IRQ, save/load, rewind and reset checks pass.
- Channel isolation, stereo FM pan, combined/separate SSG level, every 64 KB RAM
  quarter, pending CPU-write latch, version rejection and v6/v7 legacy saves pass.
- Live prescalers 6 → 3 → 2 → 6 measure 976.61 / 1953.06 / 3906.68 / 976.61 Hz
  for expected 976.56 / 1953.13 / 3906.25 / 976.56 Hz. Exact chip/clock continuation
  after save/load at each setting and rewind across a later prescaler write pass.
- Matched 20-second recordings: Thunder (bank 12), Shop (3), Bustling Town (5),
  Lao Shi (2). No output clipping; whole-recording RMS changes by less than 0.7%.
  Native and old WAVs are not bit-identical because host resampling differs.
  This is a labelled A/B comparison, not a completed blind listening test.

## Remaining work before proposing upstream replacement

Informal listening found no audible difference. Still explicitly judge rate-switch transitions.
Recreating resamplers discards filter history; the pitch/state tests do not prove
that every switch is inaudible. Hardware analogue/DAC frequency response is a
separate question; these measurements do not settle the ZOH discussion.

Confirm the preferred two-device controls/channel naming with Wouter. Preserve
our fork's legacy-state path, while upstream can still start from version 1.
Run upstream platform CI after agreement; this experimental build was compiled
and tested locally on Windows only.

## Reproduction

`Contrib/makoto-native-core-test.cc` links with `ymfm_opn.cpp`, `ymfm_ssg.cpp`
and `ymfm_adpcm.cpp`, using include paths `src` and `src/sound`.
`Contrib/makoto-native-stream-test.py` accepts `--openmsx` and `--firmware-dir`.
The existing integration, V4/V5 and timer tests use the same executable.

`Contrib/makoto-workload-benchmark.py --build baseline=... --build native=...`
accepts `--rom`, `--manifest`, `--firmware-dir`, `--seconds 60 --repeats 5`.
`Contrib/makoto-native-listening.py` uses the same arguments without `--repeats`
and produces local WAVs plus an HTML player. Supply your own firmware and music.
