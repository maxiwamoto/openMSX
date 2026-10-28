# Combined development build 2026.10.28

Windows x64 Release build integrating official openMSX 22.0 (RELEASE_22_0, 13007fee0) with the completed fork additions:

- Selective Flash-sector persistence, automatic five-second retries after failed writes, and AM29F010/SD Mapper v1 integration.
- Developer state restore with refreshed untouched ROM assets and preserved saved Flash sectors.
- Windows ROM replacement, no-reset media refresh, and F12 media reload with a full power cycle.
- Mouse click-to-capture, middle-click release, clipboard compatibility while released, and release on pause/focus/machine changes.
- V9968 extended VRAM, palette and sprite support, adapted to upstream sprite status timing.
- Approved October 2 Makoto native audio, hardware-checked sample RAM behavior, individual voice controls and older fork sound-state readers.

The October 2 Makoto implementation is retained deliberately. Upstream's newer WIP YM2608 restructuring is not substituted for it. The unapproved merged audio-ownership experiment is also excluded.

Use the complete package and its launchers. It includes its matching resources, C-BIOS, dependency licenses, source archive and SHA-256 checksums. Commercial firmware and game ROMs are not bundled. The release is published at https://github.com/maxiwamoto/openMSX/releases/tag/rom-dev-2026.10.28.

Compared with the October 24 combined build, this includes the generic bitmap viewer for debuggables, the I/O read-watchpoint lifetime fix, Franky/SMS VDP viewers and frameskip, updated audio-analysis FFT, and the restored `cputrace` setting name.

The portable package includes VALIDATION.json with the checks run against this build.
V9968 remains experimental; these checks do not establish full hardware conformance.
