#!/usr/bin/env python3
"""Synthetic V9968/legacy integration checks; uses isolated profiles only."""
import argparse, base64, gzip, json, runpy, tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
H = runpy.run_path(str(ROOT / 'Contrib/rom-replacement-test.py'))
Emulator, tcl_path = H['Emulator'], H['tcl_path']

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--openmsx', type=Path, required=True)
    p.add_argument('--baseline', type=Path)
    p.add_argument('--firmware-dir', type=Path, required=True)
    a = p.parse_args()
    out = Path(tempfile.mkdtemp(prefix='v9968-check-', dir=ROOT/'derived'))
    rom = out / 'synthetic.rom'; rom.write_bytes(H['image'](0x37))
    results = []
    old = out/'upstream.oms'
    if a.baseline:
        d=out/'baseline'; d.mkdir()
        e=Emulator(a.baseline,d,a.firmware_dir,rom,'ASCII16')
        try:
            e.command('store_machine [machine] '+tcl_path(old))
            results.append('Legacy baseline save created')
        finally:e.close()
    d=out/'candidate'; d.mkdir()
    e=Emulator(a.openmsx,d,a.firmware_dir,rom,'ASCII16')
    def regs(values, name='VDP regs'):
        e.command('; '.join(f'debug write {{{name}}} {r} {v}' for r,v in values.items()))
    def blob(name,start,data):
        v=base64.b64encode(data).decode()
        e.command(f'debug write_block {{{name}}} {start} [binary decode base64 {{{v}}}]')
    def read(name,start,size):
        return e.command(f'binary encode hex [debug read_block {{{name}}} {start} {size}]')
    def palette():
        path=out/'palette-snapshot.oms'
        e.command('store_machine [machine] '+tcl_path(path))
        xml=ET.fromstring(gzip.decompress(path.read_bytes()))
        return [int(x.text) for x in xml.findall('.//palette/item')]
    def restore(path):
        e.command('set old [machine]; set new [restore_machine '+tcl_path(path)+']; delete_machine $old; activate_machine $new')
    try:
        # Public cycle counters retain their documented 21-MHz units.
        e.command('set pause on')
        line=int(e.command('machine_info VDP_line_in_frame'))
        frame=int(e.command('machine_info VDP_cycle_in_frame'))
        cycle=int(e.command('machine_info VDP_cycle_in_line'))
        assert frame//1368==line and frame%1368==cycle
        e.command('set pause off')
        results.append('Debugger/TAS cycle counters retain 21-MHz units')
        if old.exists():
            restore(old);e.expect(0x37,rom.read_bytes())
            assert int(e.command('debug size {physical VRAM}'))==131072
            results.append('Pre-integration V9938 state loads and continues')
        # A built-in V9968 fixture using already available Philips firmware.
        machines=d/'home/share/machines';machines.mkdir(exist_ok=True)
        config=(ROOT/'share/machines/Philips_NMS_8250.xml').read_text()
        import re
        config=re.sub(r'<VDP id="VDP">.*?</VDP>', '<VDP id="VDP"><version>V9968</version><vram>256</vram><io base="0x98" num="5" type="O"/><io base="0x98" num="5" type="I"/><timing>0</timing></VDP>',config,flags=re.S)
        (machines/'Test_V9968.xml').write_text(config)
        e.command('set old [machine];set new [create_machine];${new}::load_machine Test_V9968;activate_machine $new;delete_machine $old;carta insert '+tcl_path(rom)+' -romtype ASCII16;set power on')
        e.advance(3)
        assert int(e.command('debug size {physical VRAM}'))==262144
        regs({21:0,15:1})
        assert int(e.command('debug read {VDP status regs} 1'))&62==6
        regs({21:1})
        assert int(e.command('debug read {VDP status regs} 1'))&62==4
        results.append('V9968 has 256 KiB VRAM and switchable VDP ID')
        # Test the actual emulated scanline overflow flag, independent of renderer.
        regs({0:6,1:0x62,2:0x1f,5:0xef,6:0xf,8:8,9:0x80,11:0,20:0})
        blob('physical VRAM',0x7800,bytes([255])*32)
        blob('physical VRAM',0x7400,bytes([15])*512)
        def sprites(count,s16):
            regs({20:128 if s16 else 0})
            sat=bytes(sum(([80,(i*16)%256,0,0] for i in range(count)),[]))+bytes([216,0,0,0])
            blob('physical VRAM',0x7600,sat)
            e.advance(.05)
            regs({15:0})
            blob('memory',0xc100,bytes.fromhex('f3 21 01 c0 db 99 47 e6 40 28 f9 b6 77 78 e6 5f 32 02 c0 c3 04 c1'))
            blob('memory',0xc001,bytes(2))
            e.command('reg PC 0xc100')
            e.advance(.05)
            return int(e.command('debug read memory 0xc002'))
        assert sprites(9,False)&0x5f==0x48
        assert sprites(16,True)&0x40==0
        assert sprites(17,True)&0x5f==0x50
        results.append('S16 raises mode-2 overflow from ninth to seventeenth sprite')
        # Persist an interrupted RGB5 palette write, including the extended index.
        regs({20:0x90,16:200})
        e.command('debug write ioports 0x9a 31;debug write ioports 0x9a 7')
        state=out/'v9968-palette.oms';e.command('store_machine [machine] '+tcl_path(state))
        e.command('debug write ioports 0x9a 19');expected=palette()
        assert len(expected)==256 and expected[200]==(7<<10)|(31<<5)|19
        restore(state);e.command('debug write ioports 0x9a 19')
        assert palette()==expected
        results.append('256-entry palette and unfinished RGB write survive save/load')
        # HMMV above 128 KiB, then a save in the middle of a larger command.
        regs({20:0x81,21:0,0:6,1:0x62})
        e.advance(.02)
        regs({36:0,37:0,38:0,39:6,40:0,41:1,42:128,43:0,44:0x5a,45:0,46:0xc0})
        e.advance(.1)
        assert read('physical VRAM',0x30000,16384)=='5a'*16384
        regs({38:0,39:4,42:0,43:2,44:0xa5})
        e.command('set pause on;debug write {VDP regs} 46 0xc0')
        state=out/'v9968-command.oms';e.command('store_machine [machine] '+tcl_path(state))
        e.command('set pause off');e.advance(.1)
        expected=read('physical VRAM',0x20000,65536)
        restore(state);e.command('set pause off');e.advance(.1)
        assert read('physical VRAM',0x20000,65536)==expected=='a5'*65536
        results.append('Extended VRAM commands and in-flight command save/load')
        e.command('ext HRA_V9968')
        assert int(e.command('debug size {physical V9968 VRAM}'))==262144
        results.append('External V9968 cartridge can coexist with primary VDP')
    finally:
        e.close()
        (out/'results.json').write_text(json.dumps(results,indent=2)+'\n')
    print('\n'.join('PASS: '+r for r in results));print(out)
if __name__=='__main__':main()
