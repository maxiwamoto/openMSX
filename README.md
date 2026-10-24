# openMSX: Makoto, V9968 and ROM/disk development

**Makoto / YM2608: tested playback and review cleanup.**
FM and SSG now run at their own sample rates. An openMSX-owned adaptation of
the YMFM control layer writes directly to the host mixer, retaining the proven
FM/SSG/ADPCM synthesis engines and hardware-verified sample-RAM corrections.

The final extraction used about 7% less whole-emulator CPU during the measured
music workload than our previous native-stream experiment. Four tested music
excerpts match exactly at equivalent levels. All 16 voice controls, independent
timers, debugger controls and filter-free playback remain available.
[Measurements and limits](doc/makoto-owned-core-experiment.md) ·
[Setup](doc/makoto.md) · [Hardware results](doc/makoto-review-2026-09-29.md).
Analogue clipping and headphone-load response remain uncalibrated.

The October 2 update cleans up device lifetime handling and uses native
control-field serialization with four checked engine-state blobs. Older fork
saves remain supported. The approved playback is preserved; this cleanup
does not claim an additional speed gain. [Validation and experiments](doc/makoto-review-2026-10-02.md).

**Experimental V9968 support:** integrates buppu3's V9968 emulation, including
S16 (16 sprites per scanline), alongside this fork's development features.
[Setup, attribution and validation](doc/v9968-integration.md).
Use **Start-openMSX-Makoto.cmd** for a Turbo-R with Makoto, or
**Start-openMSX-Makoto-V9968.cmd** to enable both in the same machine.

**Update an ASCII16-X or Yamanooto game ROM while keeping its in-game Flash saves.** This
public fork also lets Windows developers rebuild an inserted ROM and return
to a saved test point with updated graphics or text.

**Local Windows x64 build: 2026.10.24.** See `doc/all-additions-2026-10-24.md` for the integrated features and validation.

Version **2026.10.24** retains Makoto, V9968, Flash persistence and development
reload features. FM and SSG use standard mixer sliders; the extra SSG trim is
removed. Our tested listening balance is FM 75 / SSG 38. See the
[volume conversion and upgrade instructions](doc/fork-windows-download.md).

The matching source is supplied in the local source ZIP. These changes are proposed
upstream, and the Flash persistence format is still experimental.

## What problem does this solve?

Previously, after a game wrote to Flash, openMSX could persist the entire Flash
chip. On the next launch, that saved image could hide a newer ROM with the same
filename: you supplied version 2, but the emulator continued running version 1.
Deleting the persistent image exposed the new ROM, but also removed its saves.

This fork remembers **which Flash sectors the game has programmed or erased**.
On the next load, it combines:

| Part of the Flash chip | Contents come from |
| --- | --- |
| Sectors untouched by the game | The current ROM file |
| Sectors the game programmed or erased | The persistent Flash save |

For example, if a game stores progress in a dedicated save sector, you can
replace its ROM with an updated build and load that build while keeping the
save sector. The game must still understand its earlier save format.

**An update inside a saved sector remains hidden by that sector's saved
contents.** Game code/assets and save data must occupy separate **erase
sectors**, not merely separate mapper banks.

## How saving works

Use the game's own Flash-save function. The emulator records which erase sectors the guest has modified. On restart, those sectors come from the save and untouched sectors come from the current ROM.

Persistence now uses a compressed openMSX XML archive containing the full chip image, chip identifier, sector geometry and modification flags. The usual cartridge filename is `game.rom.SRAM.flash`. Keeping a full image also permits factory-ROM fallback where supported; it does not override newer ROM content in untouched sectors.

Dirty data is written after five seconds and on normal cartridge removal or exit. Failed timed writes retry every five seconds without requiring another guest write. Writes use a temporary file followed by replacement. Corrupt or incompatible files prevent mounting, preserving the existing data.

## Trying it and keeping existing saves

Use the complete local package and **Start-openMSX.cmd** for its separate profile. Select `ASCII16-X` or `Yamanooto` as appropriate. Game code and save data must occupy different erase sectors.

The load order is the new `.flash` archive, the previous `.sparse` prototype, then legacy raw `.SRAM`. Earlier files remain untouched. Sparse modification flags are preserved; raw images lack history, so all writable sectors are conservatively treated as modified and may still hide updated ROM code. Older builds cannot read the new archive: do not alternate versions against the same profile.

See [Flash persistence](doc/flash-persistence.md) for format, migration and test details, and [this local build](doc/all-additions-2026-10-24.md) for validation.

## Faster graphics and translation testing

Windows no longer holds the inserted ROM file open in a way that prevents
rebuilding it. The running cartridge keeps its loaded snapshot until you
explicitly reload or restore.

| Action | Default Windows shortcut | Result |
| --- | --- | --- |
| Save a test point | **Alt+F8** | Save the current emulator state |
| Refresh ordinary ROM/disk assets without reset | Console: **`reload_media`** | Save/restore the machine while re-reading supported file-backed media |
| Hard reset with current media | **F12** | Reopen ROM cartridges and floppy images, then power on |
| Restore with updated ROM assets | **Ctrl+Shift+F7** | Restore the test point and refresh untouched ASCII16-X Flash from the current ROM |

F12 replaces this fork's earlier Ctrl+Shift+R shortcut and the stock F12 mute binding.
Use the audio menu or `toggle mute` in the console for mute. Saved custom bindings
take precedence; see [hard reset and media reload](doc/development-hard-reset.md).
The [462-case Windows file-mapping report](https://github.com/maxiwamoto/openMSX/releases/download/rom-dev-2026.09.24.3/windows-mapping-462-cases.zip) includes searchable HTML, raw results and reproduction scripts.

For a graphics/text change: save **before the game unpacks the asset**, rebuild
the ROM while the old version remains running, then press **Ctrl+Shift+F7**.
You can retest that segment without replaying it from the beginning.

Development restore preserves the snapshot's RAM, VRAM, CPU registers, mapper
banks and game-written Flash sectors. It restores save progress from that
snapshot, not newer progress on disk. Assets already unpacked into RAM/VRAM
remain as saved, and code/bank/RAM layouts must stay compatible. States saved
during a Flash command, or old Flash states without sector history, may be
rejected. Normal Reset and normal save-state loading retain their usual behavior.

For uncompressed disk translation work, save before an asset is read, edit the
`.dsk` in place, then restore the state. Alternatively, `reload_media` refreshes
supported media without resetting CPU/RAM. This follows Wouter's save/restore
proposal in PR #2205. Compressed `.dsk.gz` images can retain stale cache data;
use uncompressed disks for this workflow. Mounted writable disks can still
block host file replacement/rename. Flash state contents need the separate
`loadstate_dev` workflow, currently supported for ASCII16-X only.

Console equivalents are `reload_rom` and `loadstate_dev [name]`. See
[Windows ROM replacement](doc/windows-rom-replacement.md) and
[development state restore](doc/development-state-restore.md) for details.

## Testing and upstream review

Local Windows x64 testing passed 60 Flash persistence sessions (30 per mapper, including legacy saves), five ROM
replacement cases and four reload/reset cases. No-reset refresh passed for raw/gzip ROMs
and ordinary disks, including restoring an earlier state before reading an updated disk asset.
The compressed-disk cache limitation is explicitly reproduced, not counted as a passing refresh.
The existing development-restore suite covers four cases.
These cover programming/erase from RAM, restart, changed ROMs, malformed saves,
state restoration, actual decoding of updated graphics, and rejection of
unsuitable states without overwriting newer persistent saves. The tests use
synthetic ROMs and isolated profiles. No game ROMs, commercial firmware or personal saves
are distributed. The Windows package includes freely redistributable C-BIOS.

- [PR #2205: Windows buffered reads and no-reset media refresh](https://github.com/openMSX/openMSX/pull/2205)
- [Draft PR #2206: Flash persistence and development state restore](https://github.com/openMSX/openMSX/pull/2206)

The Flash work builds on **Laurens Holst (Grauw)'s** sector-persistence design
in [PR #1629](https://github.com/openMSX/openMSX/pull/1629), adapted to the current
Flash engine. The checksummed file format and developer helper API are proposals
for review, not an upstream standard.

## Original openMSX information

```text
----------------------------------------------------------------------------
openMSX - the MSX emulator that aims for perfection
----------------------------------------------------------------------------

openMSX comes with a set of HTML manuals that tell what you need to know
to install, configure and run openMSX. You can find these manuals in the
directory 'manual' inside the directory 'doc'. You can read them using
a web browser.

You can read what has changed in this and the previous releases in the
release notes. You can find the release notes of this release in the file
'release-notes.txt' in the directory 'doc'. Highlights of previous releases
can be found in 'release-history.txt'.

All source code and other works that are part of, or distributed with
openMSX are copyrighted by their respective authors. The file 'authors.txt'
contains a list of people who made works for openMSX or contributed works
to openMSX.

Some source files contain a license notice; all other source files are
licensed under the GNU Public License (GPL), of which you can find a copy
in the file 'GPL.txt'. If you got a binary release of openMSX and are
interested in the sources, please visit our home page:
    https://openmsx.org/

Happy MSX-ing!
                        the openMSX developers

----------------------------------------------------------------------------
```
