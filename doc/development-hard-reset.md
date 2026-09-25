# F12: hard reset with media reload

In this fork, **F12** runs `dev_hard_reset`: it powers the MSX off, reloads inserted ROM cartridges and file-backed floppy images from disk, and powers on again. It uses no Ctrl/Shift MSX keys. The previous Ctrl+Shift+R default is removed. F12 replaces the stock mute shortcut; mute remains available through the audio menu or console `toggle mute` (Cmd+U also remains on macOS).

A normal reset or plain `set power off; set power on` keeps existing cartridge objects and their ROM snapshots. The reload step is what makes a rebuilt ROM visible.

## Scope

- Reloads all inserted ROM cartridges in their existing slots with the same mapper and IPS patches.
- Remounts file-backed floppy images, including ordinary DSK and compressed DSK.GZ, with their IPS patches.
- Releases all floppy references before reopening disk images, and all ROM references before reopening cartridges. This also refreshes a shared compressed image mounted in multiple slots/drives, provided no other emulator machine holds that cache entry.
- Uses normal cartridge SRAM/Flash persistence when removing/recreating devices. This does not erase save files or discard programmed Flash sectors.
- With no reloadable media inserted, performs an off/on power cycle.
- Leaves RAM disks and directory-backed disks mounted. Does not refresh system firmware, hard disks, tapes, or media mounted in another machine.

The restart deliberately discards current gameplay state. For asset refresh while preserving CPU/RAM state, the separate `reload_media` command remains available with its documented limits.

## Existing profiles

Saved custom bindings override defaults. To select these bindings explicitly, enter in the openMSX console:

```tcl
bind F12 dev_hard_reset
unbind CTRL+SHIFT+R
save_settings
```

To restore the upstream F12 mute action, use `bind F12 {toggle mute}` and `save_settings`. The hard reset command remains callable from the console.

## Error handling and limitations

All ROM/disk source and patch paths are checked for existence, readability and nonzero length before changing power. Missing or empty build output therefore leaves the current machine running. File-format corruption or an insertion failure can still occur after power-off: the command restores power in a `finally` block but cannot roll back the old running machine or media already ejected.

This does not change Windows file-sharing permissions. A writable mounted DSK can still block atomic host replacement/rename; eject it before a tool that requires those operations. F12 reloads files that were successfully written. Disk insertion uses normal permissions; temporary write protection imposed when loading a state with a mismatched disk checksum is not explicitly retained.

File identity caching can still miss very rapid rewrites with unchanged whole-second timestamps. This change does not alter the existing FilePool timestamp behavior. Other running machines can retain shared decompression cache entries.

## Validation

Run with a local firmware directory containing the NMS8250 BIOS, sub-ROM and disk ROM:

```text
python Contrib/hard-reset-test.py --firmware-dir /path/to/systemroms --openmsx /path/to/openmsx.exe
```

Seven synthetic-media scenarios passed on Windows:

- ASCII16, ASCII16-X and Yamanooto: ordinary off/on retained the old ROM; hard reset booted the updated bytes and retained the mapper.
- IPS-patched ROM: the patch stayed applied after reload.
- A shared gzip ROM in both cartridge slots: both picked up the new image.
- Ordinary DSK and gzip DSK in both floppy drives: both exported the updated asset byte-for-byte after a disk-only restart.

The suite traces the global `::power` setting and requires actual off/on transitions. It also traces ROM/floppy commands to require that they run while power is off. The suite also checks the F12 binding, removal of Ctrl+Shift+R, missing/empty ROM preflight, and restart with no ROM inserted. Disk tests enable a second drive in a disposable NMS8250 configuration. Tests execute the bound command rather than injecting physical keyboard events. The previous Flash persistence validation remains separate; these cases do not replace it.

## File-mapping experiment

The separate Windows experiment recorded all **462 cases**, including read-only and copy-on-write mappings, sharing masks, handle lifetime, overwrite/truncation/replacement operations, and buffered-read controls. This was an API experiment on Windows 11 build 26200 / NTFS, not a timing benchmark.

[Download the complete HTML/CSV/JSON report and reproduction scripts](https://github.com/maxiwamoto/openMSX/releases/download/rom-dev-2026.09.24.3/windows-mapping-462-cases.zip).

## Tcl power-setting correction

The initial 2026.09.24.3 command used `set power off/on` inside a Tcl procedure. That created a local variable, so media reloaded without changing the real global power setting. Version 2026.09.24.4 corrects the command to explicitly write `::power`. The earlier reload-only assertions missed this; the global power and media-command traces now cover it.
