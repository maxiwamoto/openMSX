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


## Optional merged-engine experiment

Branch codex/makoto-merged-experiment moves the FM/ADPCM engines into FmPart,
the SSG engine into SsgPart, and the control registers into MakotoSound. It
removes the rendering delegation. A lightweight serialization view retains
exactly the same native chip subrecord and old-state reader.

This branch is an experiment, not a replacement release. The separate
MakotoYM2608 files remain for the pre-merge standalone differential test;
that test does not exercise the merged production device. The merged device
passes the runtime timer/IRQ/BUSY/debugger/state/rewind, native-prescaler,
RAM-transfer, channel-isolation and failed-construction suites. Actual fork
version-8 and version-9 states convert byte-exactly and resume. Four 20-second
excerpts restored from the preserved release (Thunder, Shop, Bustling Town,
Lao Shi) have zero PCM difference and no clipped samples after 0.2 s warm-up.

Benchmark results are recorded separately after the alternating runs finish.
