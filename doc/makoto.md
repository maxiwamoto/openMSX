# Makoto / YM2608 prototype

This local development branch adds an experimental Makoto extension on top of
our V9968, Flash-save and media-reload fork. It is not a hardware-validated release.

## Implemented

- I/O ports 14h–17h with both OPNA register banks and BUSY status.
- YM2608 FM, SSG and ADPCM engines from Aaron Giles's BSD-licensed YMFM.
- Timer A/B events scheduled in emulated time, independently of host audio buffers.
- 256 KiB sample RAM (capacity confirmed by the cartridge owner).
- Native openMSX stereo audio, recording, register inspection and save states.
- Separate `makoto_master_volume` (combined output) and `makoto_psg_volume` settings,
  each 0–100, defaulting to Master 50 and SSG 50. These follow the Master Vol. / SSG Vol. labels on the supplied PCB photo;
  the analogue calibration remains provisional.
- Optional CSV tracing of writes, status reads, timer overflows and IRQ changes.

The pinned YMFM source and BSD license are under `src/3rdparty/ymfm`.
Only the OPN/SSG/ADPCM subset is vendored, without modifications.

## Run

Add `-ext Makoto` when starting openMSX, or run `ext Makoto` in the console.
For the Illusion City test ROM, select ASCII16. Use bank 12 for thunder and
bank 11 for the two opening themes. The ROM itself is unchanged by this work.

Console controls:

```
set makoto_master_volume 50
set makoto_psg_volume 50
soundlog start makoto.wav
soundlog stop
```

The ordinary sound-chip volume setting controls the final combined output.
Register history is available as the `Makoto registers` debuggable.

## Hardware details still being checked

The current configuration uses a nominal 8 MHz clock. The owner has asked
SuperSoniqs for the schematic/technical details. IRQ is disconnected by default
until the current board revision is confirmed; chip timer flags still work for polling.
The older Project Makoto Final.pdf schematic (revision 4.22, dated 2020)
connects YM2608 IRQ to the MSX slot and places the master control after mixing.
The supplied 2025 PCB photos confirm Master Vol. / SSG Vol., YM2608B and
YM3016-D, but do not by themselves establish unchanged IRQ wiring or clock.
GPIO reads return FFh and are not connected to the MSX keyboard/joysticks.
RAM capacity is confirmed; addressing and ADPCM transfer behavior still need
hardware tests. FM/SSG balance is adjustable, not yet calibrated.

YM2608's internal percussion needs its separate 8192-byte rhythm ROM. It is
not supplied with this branch. The extension accepts an optional `<rom>` entry
with filename `ym2608_adpcm_rom.bin`; without it, rhythm samples are silent.
The Illusion City opening tests use FM and SSG and do not need that ROM.

## Trace format

Copy Makoto.xml to a private extension, and add a `tracefile` element inside
`Makoto` naming a local CSV output file. Each row has:

```
ticks,event,address,value
```

One second is 3579545 * 960 ticks. Events are `write` (register 0–511), `read`
(port offset 0–3), `timer` (A=0/B=1), `irq` and `reset`. Values are decimal.
Tracing is off by default and can produce large files during polling.
Use separate trace files per run. Do not restore a state with tracing enabled:
the restored extension currently opens the same trace filename again.

## Verification

`Contrib/makoto-test.py` exercises BUSY, both timers, cancellation, debugger
peeks and save-state continuation using a synthetic cartridge and isolated
profile. It takes `--openmsx` and `--firmware-dir` arguments. No game assets
are part of the test or fork.

The private Illusion City project additionally captures the unchanged native
ROM's writes and WAV output and compares musical writes against the original
PC-98 game capture. It excludes GPIO/timer setup differences, aligns on the
same musical events and accounts for 7.9872 MHz versus 8 MHz clock rates.
Matching values do not establish matching timing or analogue sound balance.

## Sources

- https://github.com/aaronsgiles/ymfm (revision 81aec25ccbb98f4873a255f7551ac4dadac59b4a)
- https://map.grauw.nl/resources/msx_io_ports.php (Makoto port allocation)
- https://supersoniqs.com/ (hardware description)

## Local results, 2026-09-25

BUSY, timer A/B, cancellation, side-effect-free debugger peeks, exact chip/timer
save-state continuation, and reset passed. Same-rate audio reinitialization
preserves the chip sample clock. Host resampler buffers are not serialized;
this does not establish bit-identical WAV samples immediately across a restore.

The unchanged demo matched all 20,469 compared musical register writes on each
of Panasonic FS-A1GT and Sanyo PHC-70FD2: 1,927 thunder, 15,789 Theme A, and
2,753 Theme B. There were no demo hardware errors or clipped recorded samples.
After clock-rate correction, native playback lagged the PC-98 reference by
approximately 41 ms (thunder), 70 ms (Theme A), and 54 ms (Theme B) at the final
compared events. These are opening excerpts, not whole-game validation.
Listening and analogue calibration against the physical cartridge remain outstanding.

The Windows executable uses MSVC v145 targeted compilation/linking after
integration fixes. The unchanged VDPAccessSlots object and resource were reused
from the V9968 base build. A clean full build and non-Windows builds have not
been verified. The source is published in this fork; it is not installed over the usual build.

Additional hardware references:
- https://github.com/denjhang/MSX-makoto-to-RE2-YM2608 (older Makoto schematic)
- https://github.com/denjhang/RE2-YM2608 (related board and chip documentation)

## Listening defaults update

Master 50 / SSG 50 is the latest owner-selected balance after testing on R800.
The earlier 50/30 setting partly compensated for overloaded Z80 playback. The extension mix gain is
192000 instead of the initial 12000: a common 16x (+24.08 dB) boost, preserving
the FM/SSG ratio. This is a listening default, not analogue hardware calibration.

## Replay timing research

See [the CPU, ROM/RAM and listening findings](makoto-replay-findings.md) and
[the numerical test results](makoto-replay-results.json). These concern the local
PC-98 music port, not a claim that the original PC-98 player is inefficient.
The game ROMs, extracted music, instrument banks and proprietary drivers are not
included. New profiles default to 50/50; existing saved settings take precedence.
