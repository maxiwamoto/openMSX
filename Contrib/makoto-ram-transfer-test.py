"""Check that the Makoto RAM transfer comparison both completes and displays results.

Uses fresh profiles, synthetic ROM data and dummy audio. Supply your own BIOS.
A RAM signature alone is insufficient: v1 completed its measurements but hung
inside BIOS display setup because the probe left the Makoto IRQ asserted.
"""
import argparse
import importlib.util
import json
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("makoto_test", ROOT / "Contrib/makoto-test.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--openmsx", type=Path, required=True)
    parser.add_argument("--firmware-dir", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    args = parser.parse_args()
    out = Path(tempfile.mkdtemp(prefix="makoto-probe-boot-", dir=ROOT / "derived"))
    results = []
    for machine in ("Philips_NMS_8250", "Panasonic_FS-A1GT"):
        for present in (False, True):
            run = out / (machine + ("-makoto" if present else "-absent"))
            run.mkdir()
            e = m.Emulator(args.openmsx, run, args.firmware_dir, args.rom,
                           "ASCII16", machine=machine)
            try:
                e.command("set pause on")
                if present:
                    e.command("ext Makoto")
                e.command("reset; set pause off")
                e.advance(6)
                e.command("set pause on")
                raw = bytes.fromhex(e.command(
                    "binary encode hex [debug read_block memory 0xc100 80]"))
                screen = bytes.fromhex(e.command(
                    "binary encode hex [debug read_block VRAM 0 960]"))
                assert raw[:4] == b"MKT4", "Probe did not complete"
                assert b"MAKOTO RAM COMPARISON V4" in screen, "Title not displayed"
                assert b"Cold boot. Please photo all results." in screen, "Results incomplete"
                assert raw[4] == (0 if present else 1), "Unexpected timeout/presence result"
                irq = None
                if present:
                    irq = e.command("debug probe read Makoto.IRQ")
                    assert irq == "0", "Probe left the Makoto IRQ asserted"
                    assert raw[72:76] == bytes(4), "A transfer method timed out"
                    expected = {
                        16: bytes(8),
                        24: bytes([8]) * 8,
                        32: bytes([0xC8]) * 8,
                        40: bytes([0xC8]) * 8,
                        48: bytes(range(0xC1, 0xC9)),
                        56: bytes(range(0xC1, 0xC9)),
                    }
                    for offset, value in expected.items():
                        assert raw[offset:offset + 8] == value, f"Physical V4 mismatch at {offset:#x}"
                row = {"machine": machine, "makoto": present, "display_complete": True,
                       "irq": irq, "timeout": raw[4], "result_bytes": raw.hex()}
                results.append(row)
                (run / "screen.txt").write_text("\n".join(
                    screen[i:i + 40].decode("ascii", errors="replace") for i in range(0, 960, 40)))
                print(json.dumps(row), flush=True)
            finally:
                e.close()
    (out / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    print(out)


if __name__ == "__main__":
    main()
