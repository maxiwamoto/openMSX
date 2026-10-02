# Makoto review work — 2026-10-02

Working release preserved at 500fd548a (rom-dev-2026.10.01). Experiments use
codex/makoto-review-oct02; no experimental executable replaces that release.

## Build and cleanup

Optimized Clang reproduced the missing FM template symbol. Explicitly
instantiating fm_engine_base<opna_registers> in ymfm_opn.cc fixes the link where
all register-template definitions are available. The .cpp wrappers are removed;
third-party sources now use .cc directly. Sound GUI changes are fully reverted.

The owned control code uses openMSX member/function naming and braces. FmPart
and SsgPart register at the end of their concrete constructors and unregister
in their own destructors. A failed constructor therefore never runs a destructor
that unregisters a nonexistent device. The shared base no longer needs a
registered flag. Its initial zero clock period makes clockInitialized redundant.

## State layout

Fork sound-state version 10 stores address, IRQ mask and flag control natively,
then four checked engine blobs (FM 804, SSG 56, ADPCM-A 192, ADPCM-B 54 bytes).
Temporary engine buffers do not participate in pointer-based delta tracking.
The fork retains its historical reader; upstream keeps only the new format.
Real version-8 and version-9 states preserve exact control, engine, RAM, IRQ,
BUSY and timer values when converted, and resume successfully. All four engine
blobs reject truncated data. Failed FM/SSG registration leaves no stale settings.
Timer/state/rewind, prescaler continuation and channel/RAM integration tests pass.

The standalone engine comparison still matches 1,080,000 samples, with the
negative key-off control detecting 107,967 mismatches. Performance experiments
and final audio comparisons are recorded below when complete.


## Loop and ownership experiments

Five alternating-order runs, each measuring 60 emulated seconds, gave these
median whole-process CPU seconds on Windows/MSVC Release:

| Build | No Makoto | Silent BASIC | Music | Channel tools |
| --- | ---: | ---: | ---: | ---: |
| Cleanup baseline | 4.250 | 6.594 | 11.359 | 12.688 |
| Separate FM/B/rhythm loops | 4.281 | 6.641 | 11.203 | 12.813 |
| Engines inside audio parts | 4.125 | 6.438 | 11.469 | 12.813 |

These differences are not convincing performance gains. Run-to-run scatter
exceeds the roughly 1% median changes; one split-loop music run was an outlier.
Desktop scheduling and independently booted playback phases limit small
percentage comparisons. These are host costs, not MSX driver frame time.
We keep the separate loops for clarity. The larger ownership experiment stays
on codex/makoto-merged-experiment rather than becoming part of this PR update.

The merged experiment moves FM/ADPCM engines into FmPart and SSG into SsgPart,
and keeps the exact native state layout through a lightweight serialization
view. It passes all runtime hardware/state/prescaler/channel/RAM and failed-
construction tests. Real v8/v9 saves migrate exactly. Four 20-second excerpts
from the preserved release (Thunder, Shop, Bustling Town, Lao Shi) produce
zero PCM difference and zero clipped samples after 0.2 s resampler warm-up.
Its retained standalone MakotoYM2608 test exercises the pre-merge class only;
merged production coverage comes from the full emulator checks above.

Raw runs, executable hashes and audio results are in the adjacent results JSON.
The GitHub build matrix for 860a75d91 passed Linux, both macOS targets, both
Windows toolchains and unit tests. SonarCloud's quality gate reports duplicated
lines (6%, threshold 3%), not a failed security/reliability rating. Vendor and
reference code have not been rewritten merely to silence that metric.
