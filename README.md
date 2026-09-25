# openMSX: Flash saves and ROM/disk development

**Experimental V9968 branch:** integrates buppu3's V9968 emulation, including
S16 (16 sprites per scanline), alongside this fork's development features.
[Setup, attribution and validation](doc/v9968-integration.md).
The download below is the earlier stable fork build and does not include V9968.

**Update an ASCII16-X or Yamanooto game ROM while keeping its in-game Flash saves.** This
public fork also lets Windows developers rebuild an inserted ROM and return
to a saved test point with updated graphics or text.

**[Download the Windows x64 build](https://github.com/maxiwamoto/openMSX/releases/tag/rom-dev-2026.09.24.4)**
for this fork. Extract the ZIP and run **Start-openMSX.cmd**; it uses a separate
profile beside the executable. [Setup and shortcuts](doc/fork-windows-download.md).

Version **2026.09.24.4** fixes the F12 power-cycle bug: media reload now runs
with the actual MSX power setting off, followed by power-on.

The source is available in this fork's `master` branch. These changes are proposed
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

Use the game's own save function as usual; no new save command is required.
This implements persistence for games that already write to emulated Flashâ€”it
does not add an in-game save feature to games that lack one.

- Only guest-programmed or erased sectors are persisted. An erased sector
  remains erased across restarts, even if a newer ROM contains data there.
- Dirty data is written after a five-second real-time delay and when the
  cartridge is removed or the emulator closes normally. A fresh profile that
  has never written Flash does not create a save file.
- The host ROM file is left unchanged. Saves live in the active openMSX
  profile's persistence directory, with `.sparse` added to the usual filename,
  for example `game.rom.SRAM.sparse`.
- Sector metadata and data share one checksummed file. The loader validates it
  before applying it; corrupt data produces an error instead of silently
  starting with an empty save. Writes use a temporary file and replacement.

For the emulated 8 MiB ASCII16-X chip, one modified 64 KiB sector needs
**66,231 bytes** of persistent storage instead of an entire 8 MiB chip image.
This is selective storage, not compression of the game ROM.

## Trying it and keeping existing saves

[Download the Windows build](https://github.com/maxiwamoto/openMSX/releases/tag/rom-dev-2026.09.24.4)
and use its **Start-openMSX.cmd** launcher for a separate test profile. Other
platforms can [build from source](doc/manual/compile.html). Load the game
with the appropriate mapperâ€”`ASCII16-X` for an ASCII16-X cartridgeâ€”then save
inside the game. Close and reopen it to check persistence. After replacing the
ROM at the same path, reopen/reload the cartridge to run the new build.

**Existing full-chip `.SRAM` saves are preserved, but are not automatically
converted into a known set of save-only sectors.** They have no modification
history, so this build conservatively treats every writable sector as saved.
They can therefore still hide updated ROM content. Writing them in the new
file format does not recover that missing history.

Keep your existing saves; do not delete a persistence folder just to try this
feature. A separate fresh profile allows testing the new behavior without
altering the old data. Older builds do not understand this fork's sparse files
or newer Flash state metadata, so do not share one profile between old and new
builds. If both `.SRAM` and `.SRAM.sparse` exist, the sparse file takes precedence.

The changes use the shared AmdFlash implementation, but automated validation
covers **ASCII16-X and Yamanooto on Windows**, with 30 Flash sessions for each.
Other Flash cartridges and platforms still need broader testing. See the [Flash persistence documentation](doc/flash-persistence.md)
for sector geometry, file format, legacy compatibility and test commands.

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
