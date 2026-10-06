#!/usr/bin/env python3
"""Check upstream sprite-status timing with the fork's VDP clock and S16 mode."""
import argparse
import base64
import json
from pathlib import Path
import re
import runpy
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
H = runpy.run_path(str(ROOT / 'Contrib/rom-replacement-test.py'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--openmsx', type=Path, required=True)
    parser.add_argument('--firmware-dir', type=Path, required=True)
    args = parser.parse_args()
    out = Path(tempfile.mkdtemp(prefix='sprite-timing-', dir=ROOT / 'derived'))
    rom = out / 'synthetic.rom'
    rom.write_bytes(H['image'](0x37))
    results = []
    samples = []
    for model in ('V9938', 'V9968'):
        run = out / model
        run.mkdir()
        e = H['Emulator'](args.openmsx, run, args.firmware_dir, rom, 'ASCII16')

        def regs(values):
            e.command('; '.join(f'debug write {{VDP regs}} {r} {v}' for r, v in values.items()))

        def blob(address, data):
            encoded = base64.b64encode(data).decode()
            e.command(f'debug write_block {{physical VRAM}} {address} [binary decode base64 {{{encoded}}}]')

        def at_cycle(line, cycle, clear=False):
            # Public VDP counters retain 21-MHz units even with CLK_MUL=4.
            current = int(e.command('machine_info VDP_cycle_in_frame'))
            delta = (line * 1368 + cycle - current) % (262 * 1368)
            if delta == 0:
                delta = 262 * 1368
            # Debugger reads peek, so use real Z80 IN instructions to clear S#0
            # before the tested scanline; otherwise leave the VDP alone.
            e.command('reg PC ' + ('0xc100' if clear else '0xc200'))
            e.command(f'set sample_ready 0; after time {delta / (3579545 * 6):.12f} '
                      '{set sample_status [debug read {VDP status regs} 0]; '
                      'set sample_line [machine_info VDP_line_in_frame]; '
                      'set sample_cycle [machine_info VDP_cycle_in_line]; '
                      'set sample_ready 1; set pause on}; set pause off')
            until = time.monotonic() + 20
            while e.command('set sample_ready') != '1':
                assert time.monotonic() < until, 'Timed out sampling VDP status'
                time.sleep(0.005)
            sample = dict(zip(('status', 'line', 'cycle'), map(int, e.command(
                'list $sample_status $sample_line $sample_cycle').split())))
            assert sample['line'] == line, sample
            # Tcl callbacks can run at the end of the current Z80 instruction.
            assert cycle <= sample['cycle'] <= cycle + 96, sample
            samples.append({'model': model, 'target_cycle': cycle, 'clear': clear, **sample})
            return sample['status']

        try:
            if model == 'V9968':
                machines = run / 'home/share/machines'
                machines.mkdir(exist_ok=True)
                config = (ROOT / 'share/machines/Philips_NMS_8250.xml').read_text()
                config = re.sub(r'<VDP id="VDP">.*?</VDP>',
                    '<VDP id="VDP"><version>V9968</version><vram>256</vram>'
                    '<io base="0x98" num="5" type="O"/><io base="0x98" num="5" type="I"/>'
                    '<timing>0</timing></VDP>', config, flags=re.S)
                (machines / 'Test_V9968.xml').write_text(config)
                e.command('set old [machine]; set new [create_machine]; '
                          '${new}::load_machine Test_V9968; activate_machine $new; delete_machine $old; '
                          'carta insert ' + H['tcl_path'](rom) + ' -romtype ASCII16; set power on')
                e.advance(3)
            # Run only controlled RAM loops so BIOS cannot rewrite VDP setup.
            e.command('set pause on; '
                      'debug write_block memory 0xc100 [binary decode hex f3db99c301c1]; '
                      'debug write_block memory 0xc200 [binary decode hex f3c301c2]; reg PC 0xc200')
            # Screen 5, NTSC, no scroll, eight-pixel sprites and no VBlank IRQ.
            regs({0: 6, 1: 0x40, 2: 0x1f, 5: 0xef, 6: 0xf, 8: 8, 9: 0,
                  11: 0, 15: 0, 18: 0, 23: 0})
            if model == 'V9968':
                regs({20: 0, 25: 0})
            blob(0x7800, bytes([255]) * 32)
            blob(0x7400, bytes([15]) * 512)
            e.command('set pause off')
            e.advance(.1)
            e.command('set pause on')
            assert e.command('debug read {VDP regs} 9') == '0'
            line_zero = int(e.command('expr {[machine_info VDP_line_in_frame] - [machine_info VDP_msx_y_pos]}'))
            line = line_zero + 80
            for count, s16, threshold in ((9, False, 444), (17, True, 700)):
                if s16 and model != 'V9968':
                    continue
                if model == 'V9968':
                    regs({20: 128 if s16 else 0})
                sat = bytes(sum(([80, (i * 16) % 256, 0, 0] for i in range(count)), [])) + bytes([216, 0, 0, 0])
                blob(0x7600, sat)
                at_cycle(line, 20, clear=True)
                assert not (at_cycle(line, threshold - 120) & 0x40), 'Overflow raised too early'
                status = at_cycle(line, threshold + 80)
                assert status & 0x5f == 0x40 | (count - 1), ('Missing/wrong early overflow', status)
                results.append(f'{model}: sprite {count} overflow appears during its scanline at the scaled read time')

            # Put the only collision on sprite 9 with S16, beyond the legacy
            # eight-sprite collision limit, and on sprite 2 for a normal VDP.
            s16 = model == 'V9968'
            if s16:
                regs({20: 128})
            xs = [160, 0, 16, 32, 48, 64, 80, 96, 160] if s16 else [160, 160]
            blob(0x7600, bytes(sum(([80, x, 0, 0] for x in xs), [])) + bytes([216, 0, 0, 0]))
            at_cycle(line, 20, clear=True)
            assert not (at_cycle(line, 800) & 0x20), 'Collision raised before the beam reached it'
            assert at_cycle(line, 1100) & 0x20, 'Collision missing during the scanline'
            results.append(f'{model}: collision follows the beam' + (' and includes sprites beyond eight in S16' if s16 else ''))
        finally:
            e.close()
            (out / 'results.json').write_text(json.dumps({'passed': results, 'samples': samples}, indent=2))
    print(json.dumps(results, indent=2))
    print('Results:', out)


if __name__ == '__main__':
    main()
