# Makoto review follow-up — 2026-09-30

The native-stream version is being integrated into PR #2209 following Wouter's
reply. This update fixes duplicate-device names and fresh-core prescaler restore,
uses `std::array` for unchanged rhythm data, and simplifies source mixing.

FM/rhythm/ADPCM voices now use raw sums without an internal 16-bit clamp.
`MakotoMix` is removed. SSG gain and the former integer 2/3 scale move to mixer
amplification/software volume; there is no per-source-sample gain or rounding
remainder redistribution. The 2/3 factor remains as numerical normalization to
preserve the previously tested balance, not as a claimed hardware circuit gain.
The separate linear SSG trim remains available. Prescalers 2/3 at 8 MHz remain
modeled according to YMFM, but Wouter notes that they are outside the datasheet's
specification; these rates have not been verified on physical Makoto.

## Incremental performance

Five alternating paired runs, 60 emulated seconds per case, Windows x64,
MSVC Release, Panasonic turbo R. These are whole-process CPU-time medians.
The comparison is **native streams before vs after these simplifications**,
not the earlier 1 MHz release comparison. No other test/build ran concurrently.

| Case | Before | After | Change |
|---|---:|---:|---:|
| No Makoto | 3.172 s | 3.063 s | -3.4% |
| Idle Makoto | 4.234 s | 4.156 s | -1.8% |
| Bustling Town | 5.734 s | 5.672 s | -1.1% |
| Channel tools | 6.406 s | 6.031 s | -5.9% |

Normal-playback and idle changes are within run variation; no reliable extra
speedup is claimed there. Channel-tool CPU fell in all five pairs, by about
0.3–8.1%. The no-device variation and one slower baseline first run limit
precision. The earlier native-stream change itself measured approximately
20.5% less normal-playback CPU and 37.6% less channel-tool CPU versus 1 MHz.
Those earlier and current percentages are different comparisons, not additive.

## Clipping and audio

The earlier instrumented survey covered approximately 20 seconds of each of
37 tracks: 740,088,259 output samples / 41,116,015 FM updates, zero internal
clips, peak raw amplitude 5013. This is an excerpt survey, not a whole-game or
all-software guarantee. Its per-track counts are included in the JSON report.

A deliberately coherent six-FM-voice stress signal reaches 98016 and crosses
the old 16-bit range on 156250 side-samples out of 200000. The new path matches
the raw channel sum exactly; its difference from the old clamp is intentional.
At ordinary test levels the peak is 3072 and no side-sample exceeds the range.
Final host mixing may still clip, depending on volume and other sound devices.

For Thunder, Shop, Bustling Town and Lao Shi, both builds restore the **same**
musical snapshot, warm the resamplers for 0.2 s, then record 20 s. The largest
sample difference is one 16-bit PCM count on every track; RMS differences are
0.0183, 0.0910, 0.1060 and 0.0692 counts. Neither build clips in these recordings.
These are numerical comparisons, not another blind listening result. Fresh-boot
recordings had differing start phases, so those were not used for exact matching.

## Correctness and build scope

- Two identical Makoto extensions and two instances at different I/O ranges
  work with unique settings, debugger entries and IRQ probes. RAM/registers and
  simultaneous IRQs remain independent across save/load and removal.
- Removing the wrapper's duplicate `set_fidelity()` initially broke fresh-core
  restore at non-default prescalers. The core now rebuilds its derived sampling
  configuration after load. All 9 fidelity/prescaler combinations match for
  the next 4096 samples, without changing serialized fields.
- Native vs mixed paths in the updated core match over 1.08 million source
  samples at all prescalers, with all 16 voices. A key-off negative control
  produces 107967 differences. The older adapter test and core-prefix hash pass.
- Timer/BUSY/IRQ, debugger, save/load, rewind, pitch, channel tools, all percussion
  voices, RAM read/write and unfinished-writer state tests pass. V4/V5 diagnostic
  ROMs match the photographed hardware results on emulated MSX2 and turbo R.
- Fork states v6 and v7 migrate successfully to native clocks. Older compatibility
  code remains in the fork; the upstream initial format remains clean version 1.

The native candidate was built via the normal MSVC solution. The upstream
Makoto translation unit was compiled separately and linked against the fork's
shared test objects (the changed core and GUI files are identical); its own
extension, tests and state format were exercised. This is not a clean standalone
upstream build or non-Windows validation; CI is still required for those.

Raw numbers, executable SHA256 values and survey counts:
[makoto-review-2026-09-30-results.json](makoto-review-2026-09-30-results.json).
The comparison programs accept locally supplied music assets; none are committed.
