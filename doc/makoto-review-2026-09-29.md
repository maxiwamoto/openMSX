# Makoto RAM and mixer review — 2026-09-29

Implemented locally in the fork and upstream proposal. The YMFM synthesis core,
clock, hardware gain ratio and ADPCM boundaries are unchanged. No physical-board
results are claimed for the new ADPCM probe.

## Changes

- Native `Ram` replaces the 256 KiB array: blob/delta serialization and a
  `Makoto ADPCM RAM` debugger view. Startup remains zero-filled; reset preserves
  RAM. Fork sound-state version 6 migrates versions 1–5. Upstream remains initial
  version 1 and does not carry fork migrations.
- MAX fidelity is explicit in the constructor as well as after state restore.
  YMFM already defaulted to MAX; this is clarity, not a new playback mode.
- `MakotoMix` accepts fixed-size spans. Its DAC attenuation calculation runs only
  when the raw voice sum differs from the clamped output. The clipping fallback
  remains intact.
- Whole-buffer silence detection uses integer OR accumulation. Separate-channel
  output no longer scans voices for silence. The core continues clocking while
  silent; muted active SSG can conservatively keep a combined buffer active.
- Upstream has a short user guide and separate developer notes. Dated reports
  and raw research remain in this fork.

## RAM and state results

A blank synthetic test snapshot changed from 30,250 to 10,931 bytes compressed,
and from 7,679,000 to 77,515 bytes of XML. The 262144 per-byte item nodes are gone.
The benefit depends on machine state and RAM contents; these are not universal
save sizes.

The native rewind debug report changed from 5,488,733 inline bytes / 27 snapshots
to 261,051 / 29 snapshots. That report EXCLUDES DeltaBlock storage, and snapshot
counts differ. It demonstrates removal of the repeated inline RAM payload, not
an exact measurement of total rewind memory saved.

All 262144 patterned bytes from a version-5 array fixture loaded correctly. The
new debugger can read/write the last RAM byte; a new blob snapshot retains the
change, and rewind restores its previous value. Released version-1, version-2
and version-4 snapshots also passed migration checks. Existing version-3 loading
code is retained but was not separately re-exercised in this batch.

## Clipping measurement

A temporary diagnostic binary counted the first approximately 20 seconds of
each of the 37 tracks, using each track's assigned bank. Across 740,088,259 output
samples and 41,116,015 FM updates there were **zero DAC clipping events**. The
largest absolute pre-clamp value was 5013 (Thunder), below the positive limit
32767. This covers those excerpts, not complete songs or arbitrary software.
The channel mix helper ran 80,027,292 times; caching already avoids calling it
on every 1 MHz output sample.

Synthetic stress tests exercised 430,704 clipped sample/gain cases. Their maximum
float summation difference from the direct mixed signal was 0.0117188 chip units.
All 360,000 core differential samples matched the original mixed path exactly.
The final old/new emulator comparison matched all 32,768 recorded 16-bit PCM
values per mode, plus semantic chip/RAM state, both normally and with channel
tools. No audible comparison is required for these identical recordings.

## Host CPU comparison

Windows x64 release builds; Panasonic FS-A1GT in R800 mode; dummy audio, renderer
none, no throttle. Three alternating paired runs, 40 emulated seconds per case;
table values are medians of whole-process CPU seconds. Each run has an isolated
profile. Music is Bustling Town (track 10, bank 4) from the supplied 37-track demo.
One host-channel mute activates the channel-tool path. Builds were not compiling
and no other test emulator was running during measurement.

Both comparison builds already use native Ram. This isolates the mixer changes
from the storage migration. Diagnostic counters are absent from these builds.

| Workload | Before mixer changes | Final |
|---|---:|---:|
| BASIC, no Makoto | 2.078125 | 2.140625 |
| BASIC, silent Makoto | 3.156250 | 3.125000 |
| Music, normal output | 5.203125 | 5.250000 |
| Music, channel tools | 7.312500 | 7.078125 |

Normal playback differs by less than 1%, with run variation in the control too.
Channel tools use 3.2% less CPU in this run; this is a modest local measurement,
not a guaranteed speedup. Silent Makoto costs about 46% more than no Makoto in
the final build (an earlier shorter run measured 40%). Keep the extension
optional. These are HOST costs, not Z80/R800 music-driver frame timings.

## Validation and hardware follow-up

Fork integration checks passed channel isolation, stereo, all four 64 KiB sample
RAM quarters, peeks and save-format rejection. Final percussion checks passed
all six voices, muting, pan, key-off, save continuation and fork-only external
ROM override. The upstream device passed timers, BUSY, IRQ, reset, peeks,
save/restore and native rewind.

The local upstream-device executable compiles the upstream Makoto translation
unit and links the existing fork host objects. It is a validation harness, not a
standalone upstream release. Linux/macOS and a clean upstream CI build remain
for the next publication.

`Contrib/makoto-hardware-test.asm` produces a 16 KiB ROM, without game assets.
It records initial flags, unmasking, an end-boundary write and a limit-boundary
read. Current emulation reproduces the three observations reported by
[madscient](https://github.com/openMSX/openMSX/pull/2209#issuecomment-5884649363):
masked initial flags, fourth byte dropped at end=0, and three-byte limit wrap.
Real Makoto testing must precede any core behavior change. Cold-power the board,
run the ROM before software initializes it, and photograph the four rows plus
the timeout indicator. No listening or speakers are needed.

[Raw measurements](makoto-review-2026-09-29-results.json) include every track and
benchmark run. Reproduction tools are `makoto-ram-test.py`,
`makoto-workload-benchmark.py`, `makoto-profile-source.py`,
`makoto-clipping-test.py` and the existing integration/mix tests under `Contrib`.
Provide your own firmware and music ROM; they are not part of this report.

## Hardware-probe boot correction

The first physical test reported a freeze on Sanyo 70FD and Turbo-R with Makoto
inserted. This was reproduced on emulated MSX2 and Turbo-R: v1 filled its results
in RAM but left the OPNA IRQ asserted. BIOS display setup then stalled. The
original RAM-only check missed the failure; those measurements were not proof
that the ROM reached its results screen.

Probe v2 masks all OPNA status interrupt sources via register 110h=1Fh after
capturing the results, before any BIOS screen/text call. The measured values
remain unchanged. `Contrib/makoto-hardware-rom-test.py` verifies the complete
results screen and released IRQ on both emulator models, with and without
Makoto. All four cases pass. Physical retesting is still needed. Emulator device
code and YMFM were not changed for this fix.

## Physical v2 results and transfer audit

The owner supplied photos from Panasonic Turbo-R and Sanyo 70FD. Both show eight
00 bytes before writes, eight 08 bytes after unmasking, eight FF bytes in the end
test, eight 00 bytes in the limit test, and timeout=00. The boot fix therefore
works on both tested hosts and the observed flag states agree with emulation.

The boundary results do NOT yet validate or invalidate YMFM's off-by-one behavior.
V2 tested BUSY only, had no baseline write/read validation, and did not follow the
complete RAM-transfer sequence on page 53 of the supplied Yamaha YM2608 manual
(`YM2608J_Translated.pdf`, under the local RE2-YM2608 reference material). That
sequence includes entering mode before programming addresses, explicit transfer
termination, flag reset and BRDY/EOS polling after each data byte. In particular,
BUSY=0 alone is not proof that the external RAM buffer transfer has completed.

V3 follows that sequence. It first writes and reads C1..C8 normally; the boundary
tests are gated on success. It also verifies B1..B8 before the limit test. Errors
separate BUSY/absent (bit 0) from BRDY wait timeout (bit 1). EE marks skipped tests.
The final screen reports baseline/seed matches and end-test write count. IRQ
sources are masked before BIOS display calls as in v2. Four emulator boot cases
(MSX2/Turbo-R, Makoto present/absent) pass, including full display checks. Physical
v3 results are pending. No emulation core behavior was changed.

The hardware transcription is in `makoto-hardware-2026-09-29-v2.json`; it preserves
photo hashes without publishing the user's photos. The V3 regression results are
in `makoto-review-2026-09-29-results.json`.

## Physical v3 result: repeated final byte

Both Sanyo 70FD and Panasonic Turbo-R return C8 in all eight baseline positions,
with no timeout. Both boundary tests were correctly skipped (EE), and the unused
reseed buffer is zero. This localizes the unresolved problem to ordinary data
transfer; it does not establish which address or buffer is responsible. No YMFM
behavior has been changed to mimic these readings.

Comparison against Grauw's Makoto VGMPlay driver found a concrete setup difference:
it explicitly writes ADPCM RESET=1 immediately before mode 60h and clears flags
with F0h between data writes. V3 stopped the previous mode but did not use that
reset. Reference source inspected via the sharksym mirror at
https://github.com/sharksym/vgmplay-sharksym/blob/master/src/drivers/Makoto.asm;
original project https://hg.sr.ht/~grauw/vgmplay-msx. These are procedure references;
new diagnostic code is independently written.

The separate V4 RAM comparison ROM retains the V3 method as row A. Row B uses
reset/ready writes with the old reader; C resets before read mode too; D keeps
the data register selected for a delayed read stream without flag writes between
reads. All rows use the same C1..C8 pattern and report separate error bytes.
This tests the setup and readback hypotheses in one physical run; it is not a
claim that the hardware problem has already been fixed. All four methods pass
on both emulated hosts, including released IRQ and complete display checks.
Physical V4 testing is pending. Original three boundary questions remain open.

## Physical v4: reset/read setup isolated

Photos from Panasonic Turbo-R and Sanyo 70FD show identical results: A and B
return C8 eight times; C and D return C1 C2 C3 C4 C5 C6 C7 C8. All four error bytes
are 00; initial status remains 00 and unmasked status 08. B and C use the same
writer. C adds the explicit ADPCM RESET=1 followed by the read-mode write after
address setup. D keeps that reset and uses continuous-register reads. Therefore
ordinary readback succeeds with either reader once the reset/mode sequence is
present. The observations apply to the tested cartridge on two hosts, not two
independent YM2608 samples or all chip revisions.

The emulator also accepts A/B, unlike this physical result. This remains a
specific hardware/emulation discrepancy to investigate separately. No core
change is made from this test alone. It would be premature to infer a complete
internal chip state machine from these eight-byte transfers.

V5 restores the original end/limit tests with the successful reset/read setup,
the V4 reset/ready writer, and the existing normal-transfer gates. The final
write preserves EOS and accepts EOS or BRDY rather than clearing completion at
the exact boundary. This small boundary-specific change still needs physical
validation. C1..C8 and B1..B8 readback must both pass and the error byte must be 00
before interpreting end/limit results. All four emulator presence/host cases
pass, including the full display and IRQ release. Physical v5 results pending.

## Physical v5: boundary differences confirmed, 2026-09-30

Both supplied photos (Sanyo 70FD and Panasonic Turbo-R) show successful baseline
C1..C8, successful reseed B1..B8, error 00, and checks 01 01 04. The tests therefore
actually reached the boundary cases with working ordinary RAM transfers.

| Test | Physical Makoto on both hosts | Emulator before fix |
|---|---|---|
| Initial status | 00 repeated | 00 repeated |
| Status after unmask | 08 repeated | 08 repeated |
| END=0000 readback | A1 A2 A3 A4 FF FF FF FF | A1 A2 A3 FF FF FF FF FF |
| LIMIT=0000 readback | B1 B2 B3 B4 B1 B2 B3 B4 | B1 B2 B3 B1 B2 B3 B1 B2 |

These establish two CPU-transfer off-by-one discrepancies in x1 memory mode:
the final byte belongs to the end block, and wrapping occurs after all four bytes
of the limit block. The current core's `at_end()` and `at_limit()` identify the
last inclusive address (3 for register value 0). CPU write checks that address
before storing, dropping the final byte. CPU read increments its pointer before
checking the limit, wrapping before that byte has been read.

The next code change should target CPU memory transfer ordering, retaining the
inclusive boundary helpers used by the ADPCM playback path. Changing those
helpers globally would also change playback behavior not covered by these tests.
The separate V4 reset/read discrepancy remains documented; these results do not
establish a complete reset/transfer state machine or behavior beyond end.
Exact EOS timing and x8/ROM modes were not measured here. No additional hardware
run is needed to establish the two observed x1 byte-transfer discrepancies.

The full transcription and ROM/photo hashes are in
[the physical v5 record](makoto-hardware-2026-09-30-v5.json). The photos remain local
and have not been published. No core patch or GitHub posting is part of recording
these results.

## CPU transfer boundary fix, 2026-09-30

Implemented in the fork and the local upstream proposal. CPU reads now test the
inclusive end/limit address before advancing. CPU writes include the final byte
and retain an address one past the end as the stopped-transfer marker. The shared
playback helpers, synthesis loop and serialized field layout are unchanged.
As before, writes after completion are ignored; exact beyond-end hardware and
EOS/BRDY timing are not newly claimed as verified. The V4 no-reset read discrepancy
remains a separate issue.

Validation:

- New `Contrib/makoto-adpcm-transfer-test.cc` fails on the original source with
  "CPU write dropped the final byte", and passes 56 cases with the fix. Covers
  physical x1 END=0/LIMIT=0 results, software cases with nonzero/high register
  values and starts, x8/fixed address shifts, ROM read addressing, dummy reads,
  full readback, and preservation of the stopped-write policy. Only the V5 x1
  cases are direct physical measurements.
- The V5 ROM now matches the photographed status, baseline, end, reseed, limit,
  error, gate and byte-count results on both emulated MSX2 and turbo R. Four
  present/absent boot cases pass, with complete screen output and IRQ released.
- Core regression: 360,000 samples, all 16 voices, unchanged 1133-byte core-state
  fingerprint 4faf7577. Mix/clipping regression also passes (430,704 cases).
- Before/after emulator comparison: 32,768 PCM values and saved chip state match
  exactly in each of the combined and channel-tools paths. This short run is an
  audio regression, not a performance benchmark. An initial invocation with
  repeats=0 failed in the benchmark summary code; rerunning with repeats=1 passed.
- Timer/IRQ/BUSY/reset, save/restore/rewind, debugger and four-quarter RAM
  integration regressions pass.

The rebuilt executable is `derived/makoto-ram-review-build/openmsx.exe`; its
pre-fix comparison executable is `openmsx-before-adpcm.exe` in the same directory.
The already-running older emulator was left alone. Source/report updates remain
local; no GitHub push or reviewer reply was made for this fix.

## V4 unfinished-writer fix, 2026-09-30

The photographed V4 discrepancy is resolved. Switching an unfinished CPU RAM
writer through mode 00h to read mode did not reset the physical transfer state:
the CPU continued to see its last written buffer byte. The core now retains an
unfinished-writer latch. Affected reads and debugger peeks return that byte
without consuming RAM or dummy reads. Reset, write completion and a newly
started playback sequence release the latch.

An isolated experiment against [YM2608-LLE](https://github.com/nukeykt/YM2608-LLE)
revision 7a2aca7b6830b96e48e3a4e1a40d15525993fa60 reproduced ten C8 reads after
60h -> 00h -> 20h. An explicit 01h -> 20h released the stale buffer. The reference
used constant external bus input, not a DRAM model; only the control/buffer
observation is evidence. RAS edges include refresh and were not interpreted as
sample reads. The physical V4 photos supply the RAM readback evidence. Reference
code remains in derived/ym2608-lle-reference and is not copied into or linked
with production YMFM/openMSX.

A Boolean is appended to the core state: 1134 bytes total, original 1133-byte
prefix unchanged. Fork sound-state version 7 loads versions 1-6 by appending
false, retaining their former read behavior for history never recorded there.
The initial upstream format includes the new field without fork migrations.

Validation:
- V4 matches the photos: A/B = C8 repeated; C/D = C1..C8. All four host/presence
  boot cases complete and release IRQ in the fork and upstream-device builds.
- V5 still matches every physical result, including both end/limit fixes.
- 56 boundary cases and six buffer/reset/peek/save cases pass. The new regression
  failed on the pre-fix core before implementation.
- 360,000 synthesis samples and all 16 voices pass. Legacy prefix FNV-1a remains
  4faf7577; the new byte is zero in the synthesis fixture.
- Mix/clipping regression passes, including 430,704 clipped sample/gain cases.
- Before/after audio matches for 32,768 PCM values per combined/channel-tools
  path; old core fields match after explicit default-byte migration. This short
  run does not establish a performance difference.
- Timers, IRQ, BUSY, reset, save/load and native rewind pass. An active stale A7
  buffer survives full device save/load and releases on reset. Actual v6 and
  patterned v5 saves retain old core fields and all RAM through migration.
  A legacy test's fixed-volume assumption (15) was corrected: the v6 audio
  fixture deliberately uses 12, so the test now checks its preserved value.

This targets the observed unfinished-write to read transition. Exact hardware
EOS/BRDY timing, beyond-end behavior and other interrupted transitions remain
outside this fix; it is not a complete bus-level emulation. Both worktrees and
the local Windows build are updated. No push or GitHub reply has been made.
