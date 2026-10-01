# Makoto owned-control-layer experiment — 2026-10-01

This follows [Wouter’s control-layer proposal](https://github.com/openMSX/openMSX/pull/2209#discussion_r4155414498).

This is a local experiment on `codex/makoto-owned-ym2608`. The working reference
is preserved at `e7f7afaae404905178d65176aba0f618a8afb424`, on
`codex/makoto-native-streams`, with a separate executable/runtime copy under
`derived/owned-core-baseline`. The experiment was subsequently selected for integration into the fork and
upstream PR; the measurements below describe the preserved experiment builds.

## Implementation

`MakotoYM2608` is an openMSX-owned adaptation of YMFM's YM2608 control layer,
retaining Aaron Giles's BSD-3-Clause attribution. It contains the register/IRQ
control logic and directly owns the existing FM, SSG and ADPCM engines. It does
not inherit from `ymfm::ym2608` and has no 1 MHz generation function, fidelity
selection, repeated-sample machinery or SSG resampler.

- Symmetric `FmPart` and `SsgPart` devices own their resamplers and clocks.
- FM/rhythm/ADPCM output uses 13 channels; SSG uses three mono channels.
- Separate channels write directly into host buffers; the 32-integer output
  cache and change flag are gone from the production path.
- Normal playback renders each engine once into a local stereo sum. Channel
  tools use the separate-voice path. Neither path has an aggregate int16 clamp.
- Compile-time combined/separate loops move constant decisions outside the
  source-sample loop, including on MSVC.
- Debugger peeks receive BUSY explicitly instead of temporarily changing the
  wrapper's `contextTime`.
- The extra SSG trim and its custom GUI row are removed. Standard mixer controls
  provide FM and SSG levels.

The lower engines retain the verified CPU sample-RAM fixes and debugger/cache
patches. The old modified `ymfm::ym2608` and `MakotoNativeChip` are retained as
comparison references in `Contrib/makoto-reference/`. The vendored YM2608 class
is restored to the pinned revision, while the listed lower-engine patches remain.
No synthesis algorithm was rewritten.

True silence skipping is still deferred: clocks and status continue advancing
while output is silent. Zero-filled power-on sample RAM remains a deterministic
emulator policy, explicitly documented as unverified on hardware. Prescalers
2/3 are checked for software consistency, not claimed to match an 8 MHz chip
running outside its datasheet specification.

## Volume conversion and listening

The old SSG output multiplied two controls. The equivalent standard setting is
`new SSG_volume = old SSG_volume * old psg_volume / 100`. The tests use old
20/50 and new 10, an exact conversion. They do not normalize recordings afterward.

Local listening launchers:

- `derived/Run-Makoto-Owned-Core-TurboR.cmd`: experimental executable, private
  profile, FM 75 / SSG 38.
- `derived/Run-Makoto-Preserved-TurboR.cmd`: preserved executable, separate
  profile, FM 75 / SSG 75 / old trim 50.

38 is the nearest integer to the former effective SSG level of 37.5, so the
listening launcher has a 1.33% SSG-only level rounding difference. This does not
apply to the exact-level automated comparisons. Existing user profiles and
other launchers are unchanged. A fresh generic extension starts both standard
sliders at openMSX's usual 75; adjust SSG when reproducing an old trimmed setup.

## State compatibility

Fork sound-state version 9 drops the old channel cache. It accepts version 8
music states, and retains the older migration code. The core keeps its 1134-byte
layout for compatibility, reading/discarding former cached FM/resampler fields
and writing zeros into that padding. No redundant resampler object is retained.
Version 8 to 9 musical continuation and version 9 save/restore/rewind are tested.
This run does not claim an exhaustive retest of every earlier preview format.
The preserved older executable cannot load new version 9 states.

## Validation

- 1.08 million source samples matched the previous core, with all 16 voices,
  actual rhythm reconstruction data, ADPCM RAM, noise/envelope, live writes
  and prescalers 6/3/2. Periodic cloned states check the combined path against
  separate voice sums. The key-off negative control detects 107,967 differences.
- Four 20-second recordings (Thunder, Shop, Bustling Town, Lao Shi) resume the
  exact same baseline snapshots, warm up 0.2 seconds and record at equivalent
  levels. All four final recordings match exactly: maximum/RMS PCM difference
  zero, no clipped samples. This is numerical comparison, not a blind test.
- Timer/BUSY/IRQ, debugger peeks/register edits, state/rewind, two-device
  independence, prescaler pitch and live channel controls pass.
- All six rhythm voices, pan/mute/key-off, mid-voice state continuation and the
  fork's optional rhythm override pass.
- V4/V5 ROM probes complete with and without Makoto on emulated MSX2 and turbo R.
  Results agree with the existing physical Sanyo/turbo-R photographs, including
  stale CPU write-buffer reads and inclusive end/limit behavior.
- Full Windows x64 MSVC Release build passes. Linux/macOS builds are not run
  for this local experiment.

## Reproduction

Build with the normal openMSX build system (the MSVC project includes the new
source). The local build command is `derived/build-owned-core.cmd`.

The new source test is `Contrib/makoto-owned-core-test.cc`; compile as C++20
with `src/sound/MakotoYM2608.cc`, `Contrib/makoto-reference/ReferenceYM2608.cc`
and the vendored `ymfm_opn.cpp`, `ymfm_ssg.cpp`
and `ymfm_adpcm.cpp`, using include paths `src`, `src/sound`, `src/3rdparty/ymfm`.

The existing `makoto-audio-state-compare.py` and `makoto-workload-benchmark.py`
accept `--baseline`/`--candidate` or paired `--build` arguments respectively,
plus a locally supplied BIOS directory, 37-track ROM and manifest. No game ROM,
BIOS or music recordings are committed.

Performance measurements and machine-readable evidence are recorded below.

## Performance results

Five alternating baseline/candidate pairs, 60 emulated seconds per case,
Windows x64 MSVC Release, Panasonic turbo R, dummy audio, renderer disabled,
separate profiles. No other tests or builds ran concurrently. These are
whole-emulator CPU-time medians, not emulated Z80/R800 driver timings.

| Workload | Preserved baseline | Final candidate | Change |
|---|---:|---:|---:|
| No Makoto | 2.968750 s | 3.031250 s | +2.1% |
| Idle Makoto | 4.046875 s | 3.750000 s | -7.3% |
| Bustling Town | 5.718750 s | 5.312500 s | -7.1% |
| Channel tools active | 6.031250 s | 5.859375 s | -2.8% |

Normal playback used less CPU in all five pairs (about 4.8–9.5% per pair).
Idle and channel-tool results varied more: four of five pairs improved, one
regressed slightly. The no-Makoto median varies by +2.1%, illustrating host
noise. The initial extraction without the combined-engine fast path measured
3.3% less playback CPU and 3.7% less channel-tool CPU in a separate session;
those percentages must not be added to this table.

The final result is a modest measurable gain with exact matching in the tested
audio excerpts, and a simpler active control layer. It does not yet implement
true silent-engine suspension or demonstrate accuracy on every chip feature.

[Machine-readable measurements and regression evidence](makoto-owned-core-results.json)
include executable SHA256 values, both benchmark sessions and audio differences.

## Integration cleanup

The old patched control layer and inherited wrapper now live only in
`Contrib/makoto-reference/`, with their original BSD attribution. They are
compiled into standalone reference tests, never the emulator. The vendored
`ym2608` class has been restored to the pinned upstream revision. Lower engine
RAM fixes and debugger helpers remain; see `src/3rdparty/ymfm/README.openmsx`.
