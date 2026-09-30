"""Count DAC clipping in a supplied 37-track test ROM using a diagnostic build."""
import argparse,hashlib,importlib.util,json,struct,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(name,file):
 s=importlib.util.spec_from_file_location(name,ROOT/'Contrib'/file);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
m=load('m','makoto-test.py');w=load('w','makoto-workload-benchmark.py')
p=argparse.ArgumentParser(__doc__);p.add_argument('--openmsx',type=Path,required=True);p.add_argument('--firmware-dir',type=Path,required=True);p.add_argument('--rom',type=Path,required=True);p.add_argument('--manifest',type=Path,required=True);p.add_argument('--seconds',type=float,default=20);a=p.parse_args()
out=Path(tempfile.mkdtemp(prefix='makoto-clipping-',dir=ROOT/'derived'));songs=json.loads(a.manifest.read_text())['songs'];report={'rom_sha256':hashlib.sha256(a.rom.read_bytes()).hexdigest(),'seconds_per_track':a.seconds,'tracks':[]}
e=m.Emulator(a.openmsx,out,a.firmware_dir,a.rom,'ASCII16',machine='Panasonic_FS-A1GT')
try:
 e.command('set pause on; ext Makoto; set mute off; set Makoto_volume 20; set makoto_psg_volume 50; reset');w.step(e,15)
 # Muting one host channel forces the separate-channel path. Chip synthesis is unchanged.
 e.command('set Makoto_ch1_mute true')
 for i,song in enumerate(songs):
  e.command(f"debug write memory 0xD200 {i}; debug write memory 0xD201 {song['default_bank']-1}; debug write {{Makoto profile}} 0 0; keymatrixdown 8 1")
  w.step(e,.1);e.command('keymatrixup 8 1');w.step(e,a.seconds-.1)
  counts=struct.unpack('<7Q',bytes.fromhex(e.command('binary encode hex [debug read_block {Makoto profile} 0 56]')))
  row=dict(track=i+1,name=song.get('display_name',song['name']),bank=song['default_bank'],samples=counts[0],fm_updates=counts[1],clipped_left=counts[2],clipped_right=counts[3],peak_raw_left=counts[4],peak_raw_right=counts[5],mix_updates=counts[6],hardware_error=int(e.command('debug read memory 0xD203')))
  assert row['hardware_error']==0;report['tracks'].append(row);print(json.dumps(row),flush=True)
finally:
 e.close();(out/'results.json').write_text(json.dumps(report,indent=2))
print(out)
