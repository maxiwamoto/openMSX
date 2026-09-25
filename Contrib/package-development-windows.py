#!/usr/bin/env python3
"""Package a clean fork checkout and a matching Windows x64 Release build.

Run from the repository root. Only tracked runtime resources are included;
profiles, commercial firmware, game ROMs and build backups are never copied.
"""
import argparse
import hashlib
import io
import json
import re
import shutil
import subprocess
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
DEPENDENCIES = {
    'freetype-2.13.3': ('freetype-2.13.3.tar.gz', ['LICENSE.TXT', 'docs/FTL.TXT', 'docs/GPLv2.TXT']),
    'glew-2.2.0': ('glew-2.2.0.tgz', ['LICENSE.txt']),
    'libogg-1.3.5': ('libogg-1.3.5.tar.gz', ['COPYING']),
    'libpng-1.6.44': ('libpng-1.6.44.tar.gz', ['LICENSE']),
    'libtheora-1.1.1': ('libtheora-1.1.1.tar.gz', ['COPYING']),
    'libvorbis-1.3.7': ('libvorbis-1.3.7.tar.gz', ['COPYING']),
    'SDL2-2.32.10': ('SDL2-2.32.10.tar.gz', ['LICENSE.txt']),
    'SDL2_ttf-2.22.0': ('SDL2_ttf-2.22.0.tar.gz', ['LICENSE.txt']),
    'tcl8.6.15': ('tcl8.6.15-src.tar.gz', ['license.terms', 'libtommath/LICENSE']),
    'zlib-1.3.1': ('zlib-1.3.1.tar.gz', ['LICENSE']),
}


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args])


def copy(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', required=True, help='Release label, e.g. 2026.09.24')
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--ogg', type=Path, required=True)
    parser.add_argument('--vcruntime', type=Path, required=True, help='x64 vcruntime140.dll from VS VC/Redist')
    parser.add_argument('--third-party', type=Path, required=True, help='Directory containing download/ and src/')
    parser.add_argument('--out', type=Path, required=True, help='New output directory; must not already exist')
    args = parser.parse_args()
    if not re.fullmatch(r'[0-9A-Za-z][0-9A-Za-z._-]*', args.version):
        parser.error('Invalid release label')
    if git('status', '--porcelain', '--untracked-files=no').strip():
        parser.error('Commit tracked changes before packaging')
    commit = git('rev-parse', 'HEAD').decode().strip()
    args.out.mkdir(parents=True, exist_ok=False)
    name = 'openmsx-rom-dev-' + args.version + '-windows-x64'
    stage = args.out / name
    stage.mkdir()
    copy(args.exe, stage / 'openmsx.exe')
    copy(args.ogg, stage / 'ogg.dll')
    copy(args.vcruntime, stage / 'vcruntime140.dll')
    # Whitelist tracked resources; never recurse over a user's runtime profile.
    files = git('ls-files', '-z').decode().split(chr(0))
    for filename in filter(None, files):
        path = Path(filename)
        target = None
        if filename.startswith('share/') and path.name != '.gitignore':
            target = filename
        elif filename.startswith('Contrib/cbios/'):
            target = 'share/machines/' + filename[len('Contrib/cbios/'):]
        elif filename.startswith('Contrib/cbios-old/'):
            target = 'share/systemroms/cbios-old/' + filename[len('Contrib/cbios-old/'):]
        elif filename.startswith('doc/manual/') and path.suffix in ('.html', '.css', '.png'):
            target = filename
        elif filename in ('doc/GPL.txt', 'doc/authors.txt', 'doc/release-notes.txt',
                          'doc/release-history.txt', 'doc/flash-persistence.md',
                          'doc/windows-rom-replacement.md', 'doc/development-state-restore.md',
                          'doc/yamanooto-validation.md', 'doc/development-hard-reset.md',
                          'doc/v9968-integration.md', 'doc/v9968-upstream-readme.md'):
            target = filename
        if target:
            copy(ROOT / filename, stage / target)
    for filename in ('src/3rdparty/imgui/LICENSE.txt', 'src/3rdparty/ImGuiFileDialog/LICENSE'):
        copy(ROOT / filename, stage / 'doc/licenses' / filename)
    copy(ROOT / 'Contrib/README.cbios', stage / 'doc/cbios.txt')
    copy(ROOT / 'Contrib/Start-openMSX.cmd', stage / 'Start-openMSX.cmd')
    copy(ROOT / 'Contrib/Start-openMSX-V9968.cmd', stage / 'Start-openMSX-V9968.cmd')
    copy(ROOT / 'doc/fork-windows-download.md', stage / 'START-HERE.md')
    copy(ROOT / 'README.md', stage / 'README.md')
    for dependency, (_, licenses) in DEPENDENCIES.items():
        for license_file in licenses:
            copy(args.third_party / 'src' / dependency / license_file,
                 stage / 'doc/licenses' / dependency / license_file)
    (stage / 'doc/licenses/Microsoft-runtime.txt').write_text(
        'vcruntime140.dll is Microsoft Visual C++ Redistributable Code, supplied\n'
        'unmodified from Visual Studio VC/Redist, Copyright Microsoft Corporation.\n'
        'It is not part of the GPL-covered openMSX source. Windows 10/11 provides\n'
        'the Universal CRT system components.\n', encoding='utf-8')
    metadata = {
        'release': args.version, 'commit': commit,
        'source': 'https://github.com/maxiwamoto/openMSX/commit/' + commit,
        'platform': 'Windows x64', 'configuration': 'Release', 'toolset': 'MSVC v145',
        'experimental': True, 'third_party_versions': list(DEPENDENCIES),
        'sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in (stage / 'openmsx.exe', stage / 'ogg.dll', stage / 'vcruntime140.dll')},
    }
    (stage / 'BUILD.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
    binary = args.out / (name + '.zip')
    with ZipFile(binary, 'w', ZIP_DEFLATED, compresslevel=9) as archive:
        for file in sorted(stage.rglob('*')):
            if file.is_file():
                archive.write(file, file.relative_to(args.out).as_posix())
    # Corresponding project source includes the build scripts and dependency patches.
    source = args.out / ('openmsx-rom-dev-' + args.version + '-source.zip')
    with ZipFile(io.BytesIO(git('archive', '--format=zip', 'HEAD'))) as project:
        with ZipFile(source, 'w', ZIP_DEFLATED, compresslevel=6) as archive:
            for entry in project.infolist():
                if not entry.is_dir():
                    archive.writestr('openmsx/' + entry.filename, project.read(entry))
            for archive_name, _ in DEPENDENCIES.values():
                archive.write(args.third_party / 'download' / archive_name,
                              'dependency-archives/' + archive_name)
            archive.writestr('BUILD-COMMIT.txt', commit + '\n')
    sums = ''.join(hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + p.name + '\n'
                   for p in (binary, source))
    (args.out / 'SHA256SUMS.txt').write_text(sums, encoding='ascii')
    print(json.dumps({'commit': commit, 'binary': str(binary), 'source': str(source)}, indent=2))


if __name__ == '__main__':
    main()
