# Combined development build 2026.10.24

Local Windows x64 Release build integrating upstream 58e5324b0 with the completed fork additions:

- Selective Flash-sector persistence, automatic five-second retries after failed writes, and AM29F010/SD Mapper v1 integration.
- Developer state restore with refreshed untouched ROM assets and preserved saved Flash sectors.
- Windows ROM replacement, no-reset media refresh, and F12 media reload with a full power cycle.
- V9968 extended VRAM, palette and sprite support, adapted to upstream sprite status timing.
- Approved October 2 Makoto native audio, hardware-checked sample RAM behavior, individual voice controls and older fork sound-state readers.

The October 2 Makoto implementation is retained deliberately. Upstream's newer WIP YM2608 restructuring is not substituted for it. The unapproved merged audio-ownership experiment is also excluded.

Use the complete package and its launchers. It includes its matching resources, C-BIOS, dependency licenses, source archive and SHA-256 checksums. Commercial firmware and game ROMs are not bundled. This build has not been published as a GitHub release.

The portable package includes VALIDATION.json with the checks run against this build.
V9968 remains experimental; these checks do not establish full hardware conformance.
