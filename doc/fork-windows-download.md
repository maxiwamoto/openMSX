# Windows x64 development build

This is an experimental build of maxiwamoto/openMSX, not an official openMSX release.
It includes sector-based Flash persistence, Windows ROM replacement, reload/reset,
and development save-state restore. The Flash format is proposed upstream and may change.

## Start here

1. Extract the complete Windows x64 ZIP into a writable folder (Windows 10/11).
2. Double-click **Start-openMSX.cmd**. Use this launcher every time for this copy.
3. The launcher keeps settings, saves and screenshots in **profile/** beside the executable.
   It does not use your normal openMSX profile. Close this copy before moving its folder.
4. C-BIOS is included and can run compatible cartridge games. For real MSX machine
   definitions, put your own legally obtained firmware in **profile/share/systemroms/**.
   No commercial firmware or game ROMs are included.
5. Load your game. For ASCII16-X Flash tests, choose the **ASCII16-X** mapper.
   Use the game's save function, close openMSX normally, and reopen through the launcher.

Back up valuable saves. Do not share this profile with older openMSX builds: they do
not understand the experimental sparse Flash format. You can copy compatible older
saves into this separate profile, keeping the originals. Legacy full-chip saves remain
conservative full-chip snapshots and can still hide ROM updates; see the Flash guide.

The executable is unsigned. Running openmsx.exe directly instead of the launcher uses
openMSX's normal profile selection. Keep openmsx.exe, ogg.dll, vcruntime140.dll and share/
together. The Visual C++ runtime DLL is included; Windows supplies the Universal CRT.

## Developer shortcuts

- **Alt+F8:** save a test point.
- **Ctrl+Shift+R:** reload the ROM from disk and reset.
- **Ctrl+Shift+F7:** restore the test point using current ROM assets, preserving saved
  RAM/VRAM and game-written Flash. Save before asset unpacking; layouts must be compatible.

Ordinary reset keeps the loaded ROM snapshot. Ordinary state loading is unchanged.
Read doc/flash-persistence.md and doc/development-state-restore.md for exact behavior.

## Source and verification

BUILD.json records the source commit, build configuration and executable hashes.
The release provides SHA256SUMS.txt and a matching source ZIP containing the project,
build recipes and original dependency archives. Licenses are in doc/GPL.txt,
doc/cbios.txt and doc/licenses/. The source ZIP is for developers; players need only
the Windows ZIP. Downloads: https://github.com/maxiwamoto/openMSX/releases

To rebuild, follow doc/manual/compile.html (MSVC v145, x64 Release). The build uses
build/msvc/openmsx.sln and dependencies listed in build/3rdparty/3rdparty.props.
The dependency archives can be placed in derived/3rdParty/download before running
python build/thirdparty_download.py windows; use the upstream MSVC build instructions
for preparation/build order. Package the resulting clean checkout with
Contrib/package-development-windows.py --help. Supply ogg.dll and the Microsoft x64
vcruntime140.dll from your Visual Studio VC/Redist installation.
