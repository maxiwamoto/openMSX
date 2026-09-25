#!/usr/bin/env python3
"""Validate F12 media reload/power-cycle using synthetic media and isolated profiles."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import runpy
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
helpers = runpy.run_path(str(ROOT / 'Contrib/rom-replacement-test.py'))
Emulator, image, tcl_path = (helpers[n] for n in ('Emulator', 'image', 'tcl_path'))


def running(emu):
    return emu.command('expr {!!$power}') == '1'


def bindings(emu):
    assert 'dev_hard_reset' in emu.command('bind F12')
    assert emu.command('catch {bind CTRL+SHIFT+R}') == '1'


def hard_reset(emu):
    # A procedure-local "power" variable reloads media but never powers off.
    # Observe the actual global setting and the state during every media command.
    emu.command('set ::power_events {}; set ::media_power_events {}')
    emu.command('proc ::record_power {args} {lappend ::power_events [expr {!!$::power}]}')
    emu.command('proc ::record_media_power {args} {lappend ::media_power_events [expr {!!$::power}]}')
    emu.command('trace add variable ::power write ::record_power')
    emu.command('set ::traced_media {}; foreach media [machine_info media] {if {[string match cart? $media] || [string match disk? $media]} {trace add execution $media enter ::record_media_power; lappend ::traced_media $media}}')
    try:
        emu.command('dev_hard_reset')
        assert emu.command('set ::power_events') == '0 1', 'Global power did not cycle off/on'
        assert emu.command('expr {1 ni $::media_power_events}') == '1', 'Media changed while power was on'
        assert running(emu)
    finally:
        emu.command('trace remove variable ::power write ::record_power')
        emu.command('foreach media $::traced_media {trace remove execution $media enter ::record_media_power}')


def stamp(path):
    future = time.time() + 3
    os.utime(path, (future, future))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--openmsx', type=Path, default=ROOT/'derived/x64-VC-Release/install/openmsx.exe')
    parser.add_argument('--firmware-dir', type=Path, required=True)
    args = parser.parse_args()
    out = Path(tempfile.mkdtemp(prefix='hard-reset-', dir=ROOT/'derived'))
    reports = {}
    for name, mapper in [('ascii16','ASCII16'), ('ascii16x','ASCII16-X'), ('yamanooto','Yamanooto'), ('gzip-shared','ASCII16'), ('ips','ASCII16')]:
        folder = out/name
        folder.mkdir()
        compressed = name == 'gzip-shared'
        rom = folder/('test.rom.gz' if compressed else 'test.rom')
        old, new = image(0x11), image(0x22)
        encode = (lambda data: gzip.compress(data)) if compressed else (lambda data: data)
        rom.write_bytes(encode(old))
        patch = None
        expected = 0x22
        if name == 'ips':
            patch = folder/'test.ips'
            patch.write_bytes(b'PATCH\x00\x10\x00\x00\x01\x33EOF')
            expected = 0x33
        emu = Emulator(args.openmsx,folder,args.firmware_dir,rom,mapper,patch)
        try:
            bindings(emu)
            media = emu.command('machine_info media carta')
            for invalid in ('missing','empty'):
                rom.unlink(missing_ok=True)
                if invalid == 'empty': rom.write_bytes(b'')
                assert emu.command('catch {dev_hard_reset}') == '1'
                assert running(emu)
                assert emu.command('machine_info media carta') == media
            rom.write_bytes(encode(old))
            if compressed:
                emu.command('cartb '+tcl_path(rom)+' -romtype ASCII16')
            rom.write_bytes(encode(new))
            stamp(rom)
            emu.command('set power off; set power on')
            emu.advance(3)
            assert int(emu.command('debug read memory 0xc000')) == (0x33 if patch else 0x11)
            hard_reset(emu)
            emu.advance(3)
            assert int(emu.command('debug read memory 0xc000')) == expected
            assert emu.command('dict get [machine_info media carta] mappertype') == mapper
            if patch:
                assert emu.command('lindex [dict get [machine_info media carta] patches] 0').replace('\\','/') == patch.as_posix()
            if compressed:
                expected_hash = hashlib.sha1(new, usedforsecurity=False).hexdigest()
                for slot in ('carta','cartb'):
                    assert emu.command('dict get [machine_info media '+slot+'] actualSHA1') == expected_hash
                emu.command('cartb eject')
            emu.command('carta eject')
            hard_reset(emu)
            assert running(emu)
            reports[name] = ['F12 binding and old shortcut removal','global power off/on; media reloaded while off','missing/empty source preflight','plain off/on retains old snapshot','hard reset boots updated ROM and preserves mapper/patches','no-ROM power cycle']
            if compressed: reports[name].append('both cartridges refresh shared compressed source')
            print('PASS',name,flush=True)
        finally:
            emu.close()
    for compressed in (False,True):
        name = 'gzip-disk-shared' if compressed else 'disk-shared'
        folder = out/name
        folder.mkdir()
        # Enable a second drive in this disposable machine definition only.
        machine_dir = folder/'home/share/machines'
        machine_dir.mkdir(parents=True)
        config = (ROOT/'share/machines/Philips_NMS_8250.xml').read_text()
        assert '<drives>1</drives>' in config
        (machine_dir/'Philips_NMS_8250.xml').write_text(config.replace('<drives>1</drives>','<drives>2</drives>'))
        rom = folder/'test.rom'
        rom.write_bytes(image(0x11))
        emu = Emulator(args.openmsx,folder,args.firmware_dir,rom,'ASCII16')
        try:
            bindings(emu)
            disk, asset = folder/'test.dsk', folder/'asset.bin'
            original, updated = bytes(range(128))*4, bytes(reversed(range(128)))*4
            asset.write_bytes(original)
            emu.command('diskmanipulator create '+tcl_path(disk)+' 720')
            emu.command('diska '+tcl_path(disk))
            emu.command('diskmanipulator import diska '+tcl_path(asset))
            emu.command('diska eject')
            raw = disk.read_bytes()
            offset = raw.index(original)
            assert raw.count(original) == 1
            if compressed:
                disk = folder/'test.dsk.gz'
                disk.write_bytes(gzip.compress(raw))
            emu.command('diska '+tcl_path(disk)+'; diskb '+tcl_path(disk))
            newraw = raw[:offset]+updated+raw[offset+512:]
            if compressed:
                disk.write_bytes(gzip.compress(newraw))
            else:
                with disk.open('r+b') as stream: stream.write(newraw)
            stamp(disk)
            # Disk-only reboot, with two references to the same source/cache.
            emu.command('carta eject')
            hard_reset(emu)
            assert running(emu)
            for drive in ('diska','diskb'):
                export = folder/('export-'+drive)
                export.mkdir()
                emu.command('diskmanipulator export '+drive+' '+tcl_path(export))
                assert (export/'asset.bin').read_bytes() == updated
                assert emu.command('dict get [machine_info media '+drive+'] target').replace('\\','/') == disk.as_posix()
            reports[name] = ['global power off/on; media reloaded while off','both drives refresh same source','updated disk asset matches byte-for-byte','disk-only power cycle']
            print('PASS',name,flush=True)
        finally:
            emu.close()
    (out/'results.json').write_text(json.dumps(reports,indent=2)+'\n',encoding='utf-8')
    print('Artifacts:',out)


if __name__ == '__main__':
    main()
