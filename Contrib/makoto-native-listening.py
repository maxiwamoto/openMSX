"""Record matched real-software excerpts for local listening; supply your own ROM."""
import argparse,hashlib,html,importlib.util,json,tempfile,time,wave
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('makotest',ROOT/'Contrib/makoto-test.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
p=argparse.ArgumentParser(__doc__)
p.add_argument('--build',action='append',required=True)
p.add_argument('--firmware-dir',type=Path,required=True)
p.add_argument('--rom',type=Path,required=True);p.add_argument('--manifest',type=Path,required=True)
p.add_argument('--seconds',type=float,default=20)
a=p.parse_args();songs=json.loads(a.manifest.read_text())['songs']
out=Path(tempfile.mkdtemp(prefix='makoto-native-listening-',dir=ROOT/'derived'))
selected=[(i,s) for i,s in enumerate(songs) if any(term in s.get('display_name',s['name']).upper() for term in ('SHOP','BUSTLING','LAO','THUNDER'))]
assert len(selected)>=3
report={'rom_sha256':hashlib.sha256(a.rom.read_bytes()).hexdigest(),'seconds':a.seconds,'recordings':[]}
def step(e,seconds):
 e.command(f'after time {seconds} {{set pause on}}; set pause off')
 deadline=time.monotonic()+90
 while e.command('set pause')!='true':assert time.monotonic()<deadline
for label,exe in (item.split('=',1) for item in a.build):
 for track,song in selected:
  run=out/f'{label}-{track+1:02d}';run.mkdir()
  e=m.Emulator(Path(exe),run,a.firmware_dir,a.rom,'ASCII16',machine='Panasonic_FS-A1GT')
  try:
   e.command('set pause on; ext Makoto; set mute off; set volume 50; set Makoto_volume 20; set [lindex [info vars ?akoto_psg_volume] 0] 50')
   if e.command('info exists {Makoto SSG_volume}')=='1':e.command('set {Makoto SSG_volume} 20')
   e.command('reset');step(e,15)
   # Start recording before the same timed keypress on both builds.
   wav=out/f'{label}-{track+1:02d}.wav'
   e.command('soundlog start '+m.tcl_path(wav))
   e.command(f"debug write memory 0xD200 {track}; debug write memory 0xD201 {song['default_bank']-1}; keymatrixdown 8 1")
   step(e,.1);e.command('keymatrixup 8 1')
   assert e.command('debug read memory 0xD202')=='1'
   step(e,a.seconds)
   assert e.command('debug read memory 0xD203')=='0'
   e.command('soundlog stop')
   with wave.open(str(wav)) as f:
    rate=f.getframerate();data=np.frombuffer(f.readframes(f.getnframes()),dtype='<i2').astype(float)
   assert np.max(abs(data))<32767
   row={'build':label,'track':track+1,'name':song.get('display_name',song['name']),'bank':song['default_bank'],'file':wav.name,'sample_rate':rate,'rms':float(np.sqrt(np.mean(data*data))),'peak':float(np.max(abs(data)))}
   report['recordings'].append(row);print(json.dumps(row),flush=True)
  finally:e.close()
(out/'results.json').write_text(json.dumps(report,indent=2))
parts=['<!doctype html><meta charset="utf-8"><title>Makoto native-stream comparison</title><style>body{font:18px system-ui;max-width:980px;margin:40px auto;padding:20px;background:#141923;color:#eee}table{width:100%;border-collapse:collapse}td,th{padding:14px;border-bottom:1px solid #445}audio{max-width:100%}p{line-height:1.5}</style><h1>Makoto: current release vs native streams</h1><p>Same ROM, bank, volume and timed start. No loudness normalization. These are labelled comparisons, not a blind listening test. Native output is resampled differently; source chip samples match, but WAV files are not expected to be identical.</p><table><tr><th>Track</th><th>Current release</th><th>Native streams</th></tr>']
for track,song in selected:
 parts.append('<tr><td>'+html.escape(song.get('display_name',song['name']))+'</td>')
 for label in ('baseline','native'):
  parts.append(f'<td><audio controls preload="none" src="{label}-{track+1:02d}.wav"></audio></td>')
 parts.append('</tr>')
parts.append('</table>');(out/'index.html').write_text(''.join(parts),encoding='utf-8')
print(out)
