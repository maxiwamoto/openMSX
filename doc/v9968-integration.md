# Experimental V9968 integration

This branch integrates [buppu3/openMSX](https://github.com/buppu3/openMSX),
`msx2pp` commit `14215c7395649c3981fcc56733d0720acc11c1fd`, including its
`v9968` history through `194a769d98efd02c8a66a35e50e8e7790eb85efe`.
The V9968 implementation is buppu3's work; the merge retains that history.
The author's introduction is preserved in [v9968-upstream-readme.md](v9968-upstream-readme.md).
This integration adds compatibility with the newer upstream V9938 timing
implementation, versioned state serialization, regression checks, and a GT configuration.
It retains this fork's Flash persistence, media reload and F12 power cycle.

## Trying the sprite extension

Use `Start-openMSX-V9968.cmd` in the experimental Windows package, or select
`Panasonic_FS-A1GT_V9968` in the machine menu. It needs the same user-supplied
firmware as the ordinary FS-A1GT. `Panasonic_FS-A1ST_V9968` is also available.
These are emulated machine variants with the **primary** VDP replaced; they do
not imply that a stock Panasonic contains this hardware.

Software can enable **S16, register 20 bit 7**, for sixteen mode-2 hardware
sprites per scanline instead of eight. No new sprite artwork, extended palette,
or sprite mode 3 is required. The total remains 32 hardware sprites. Multi-layer
characters consume more than one sprite per scanline, so S16 does not guarantee
sixteen full characters or remove CPU bottlenecks.

The separate `HRA_V9968` extension uses its own ports at 88h and video output.
A game that only accesses the primary VDP at 98h will not automatically use it.
For primary-VDP software testing, use one of the machine variants above.

## Compatibility and scope

Normal machine definitions retain their V9938/V9958. The integration keeps the
recent upstream access-slot model for those VDPs, scales it to the shared internal
clock, and keeps the public debugger/TAS cycle counters in their original
21-MHz units. The raster viewer converts between those units and the finer clock.
The new VDP's `<timing>0</timing>` follows buppu3's V9968 access timing;
`<timing>1</timing>` selects V9958 timing while its HS bit is off.

Old ordinary-VDP states are accepted, with conversion of stored tick fields.
New states store the full extended palette, partial palette writes, command
cache and extended command state. States created by this build are not intended
for older openMSX binaries. Compatibility with earlier experimental buppu3
states is not established. Use a separate test profile.

The imported implementation contains more features than S16. Testing here is
focused on basic sprites and preserving existing fork behavior; it is not full
V9968 hardware conformance testing. Extended debugger views and advanced modes
still need broader testing.

## Validation on Windows x64

Build: Visual Studio v145, Release, existing shared third-party dependencies.

- `Contrib/v9968-integration-test.py`: loads a pre-integration V9938 state;
  checks VDP identity, 256 KiB VRAM, overflow on sprite 9 without S16 and sprite
  17 with S16, full palette plus unfinished RGB write save/restore, upper-VRAM
  HMMV and in-flight command save/restore, and an external V9968 beside the
  primary VDP.
- `Contrib/hard-reset-test.py`: all seven ROM, Flash mapper, IPS, shared gzip
  ROM, raw disk and gzip disk cases pass, including actual global power off/on.
- `Contrib/flash-persistence-test.py`: nineteen isolated sessions each on
  ASCII16-X and Yamanooto pass, covering persistence, updated ROM contents,
  save-state rollback, erase persistence, corrupt data and replacement failure.
- A private game validation boots on V9938, V9958, V9968 and V9968_OLD and runs
  180 updates in a crowded room on each. Ordinary bitmap/palette output matches
  the previous build. Its sprite admission code passes 256 layouts at each limit.

The private ROM and commercial machine firmware are not included in packages.
