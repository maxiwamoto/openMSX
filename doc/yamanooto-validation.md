# Yamanooto Flash and ROM-development validation

Tested on Windows on 2026-09-24 against release `rom-dev-2026.09.24`, commit
`9806b70975c68d945a02f334bebb6bc54789cae6`. No emulator runtime changes were
needed: Yamanooto uses the shared AmdFlash implementation already patched in
that release. The new changes add repeatable Yamanooto test coverage.

## Findings

The unpatched `21.0-547-gdc4c3be79` executable reproduced the full-chip save
masking an updated ROM. The published build passed all 30 Flash test sessions:
programming and erasing from RAM, persistence across restart, visibility of a
rebuilt ROM's untouched sectors, state restoration (including an operation in
progress), legacy save migration, corrupt-file rejection, and failed file
replacement. The same 30 sessions also passed again for ASCII16-X.

Windows host-file overwrite, truncation, replacement, rename and deletion all
passed with Yamanooto inserted. The running cartridge keeps its loaded snapshot.
`reload_rom` (console command) loads the updated ROM, retains the Yamanooto mapper,
and resets the machine; ordinary reset keeps the current snapshot. Slot B and
invalid-file handling also passed. Existing ASCII16, ASCII16-X, gzip and IPS
replacement tests and the existing reload cases remained green.

The optional `loadstate_dev` / Ctrl+Shift+F7 workflow is still **ASCII16-X only**.
Normal Yamanooto save-state restore works, but does not refresh the state's old
Flash image from an updated ROM. Extending that development workflow is separate
work in Debugger.cc and _savestate.tcl.

## Reproduce

Use generated ROMs and an isolated profile, with locally supplied Philips NMS
8250 firmware. Assemble Contrib/flash-persistence-ram.asm as described in
[Flash persistence](flash-persistence.md).

```text
python Contrib/flash-persistence-test.py --mapper Yamanooto --openmsx /path/to/unpatched/openmsx.exe --firmware-dir /path/to/systemroms --baseline
python Contrib/flash-persistence-test.py --mapper Yamanooto --openmsx /path/to/published/openmsx.exe --firmware-dir /path/to/systemroms --ram-routines /path/to/flash-persistence-ram.bin --legacy-fixtures /path/to/baseline-artifacts
python Contrib/rom-replacement-test.py --openmsx /path/to/published/openmsx.exe --firmware-dir /path/to/systemroms
python Contrib/reload-rom-test.py --openmsx /path/to/published/openmsx.exe --firmware-dir /path/to/systemroms
```

The Flash harness uses Yamanooto's configuration/write-enable registers and
8 KiB bank windows. Unlock commands remain at 4AAAh/4555h in CPU page 1;
RAM-executed programming targets physical 020100h through CPU address 8100h in
page 2. The S29GL064N90TFI04 has different timing from ASCII16-X's chip, so the
test allows longer erase completion and captures pending programming relative
to the actual data write rather than a guessed instruction time.

## Boundaries

- Tested direct ROM insertion with `-romtype Yamanooto`, not installation through
  a loader into the blank The_SCC_Alliance_Yamanooto extension.
- These are emulation tests, not verification on a physical cartridge. Upper
  Flash banks and every configuration/SCC mode are not covered by this suite.
- Persistence tracks erase sectors. Saved sectors override the updated ROM:
  keep code/assets separate from save sectors. Legacy full-chip saves have no
  change history, so conservative migration still masks the entire old image.
  Use a fresh separate profile for development tests; preserve existing saves.
- A game built for ASCII16's 16 KiB mapping needs a Yamanooto mapper/save-driver
  adaptation for its 8 KiB Konami mapping, plus real-hardware verification.

## Upstream context

A GitHub issue search on 2026-09-24 found no separate Yamanooto Flash-persistence
report. Issues #1964 and #1934 concern SCC+/PSG; closed #1992 concerns mapper/SCC
behavior. The shared persistence problem is already described in
[issue #2083](https://github.com/openMSX/openMSX/issues/2083), addressed by our
[draft PR #2206](https://github.com/openMSX/openMSX/pull/2206), building on Grauw's
work. No new issue or external comment was posted for this investigation.

## Local evidence

All paths below are relative to this checkout's ignored derived directory:

- Original failure and legacy fixtures: flash-baseline-pv194nnj
- Yamanooto, 30 passing sessions: flash-regression-btl_ovxt
- ASCII16-X, 30 passing sessions: flash-regression-xg8o6w9b
- Windows replacement matrix: rom-replacement-q_hwdx0v
- Reload matrix: reload-rom-9fybjle1
