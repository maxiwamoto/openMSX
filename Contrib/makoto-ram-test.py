"""Compare sample-RAM saves, legacy loading, debugger access and rewind storage."""
import argparse,base64,gzip,hashlib,importlib.util,json,re,tempfile,time,xml.etree.ElementTree as ET,zlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('m',ROOT/'Contrib/makoto-test.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
p=argparse.ArgumentParser(__doc__);p.add_argument('--baseline',type=Path,required=True);p.add_argument('--candidate',type=Path,required=True);p.add_argument('--firmware-dir',type=Path,required=True);a=p.parse_args()
out=Path(tempfile.mkdtemp(prefix='makoto-ram-',dir=ROOT/'derived'));rom=out/'test.rom';rom.write_bytes(m.image(0x40));report={}
def step(e,s):
 e.command(f'after time {s} {{set pause on}}; set pause off');deadline=time.monotonic()+120
 while e.command('set pause')!='true':assert time.monotonic()<deadline
def sound(path):return ET.fromstring(gzip.decompress(path.read_bytes())).find('.//device[@type="Makoto"]/sound')
def ram(node):
 blob=node.find('ram')
 if blob is None:return bytes(int(x.text) for x in node)
 assert blob.get('encoding')=='gz-base64';return zlib.decompress(base64.b64decode(blob.text))
for label,exe in [('baseline',a.baseline),('candidate',a.candidate)]:
 run=out/label;run.mkdir();e=m.Emulator(exe,run,a.firmware_dir,rom,'ASCII16')
 try:
  e.command('set pause on; ext Makoto');saved=out/(label+'.oms');e.command('store_machine [machine] '+m.tcl_path(saved));xml=gzip.decompress(saved.read_bytes());report[label]={'state_gzip_bytes':saved.stat().st_size,'state_xml_bytes':len(xml),'sample_items':len(sound(saved).findall('sampleRAM/item'))}
  e.command('reverse start');step(e,20)
  detail=e.command('reverse debug');(out/(label+'-reverse.txt')).write_text(detail)
  report[label]['rewind_inline_bytes']=int(re.search(r'total size: (\d+)',detail).group(1))
  report[label]['snapshots']=int(e.command('llength [dict get [reverse status] snapshots]'));e.command('reverse stop')
  if label=='candidate':
   # Give the old array fixture nontrivial values across the full 256 KiB.
   old=ET.fromstring(gzip.decompress((out/'baseline.oms').read_bytes()));items=old.findall('.//device[@type="Makoto"]/sound/sampleRAM/item');assert len(items)==262144
   pattern=bytes((i*29+(i>>10))&255 for i in range(262144))
   for item,v in zip(items,pattern):item.text=str(v)
   fixture=out/'legacy-pattern.oms';source=gzip.decompress((out/'baseline.oms').read_bytes());fixture.write_bytes(gzip.compress(source[:source.index(b'<serial')]+ET.tostring(old)))
   e.command('set old [machine]; set new [restore_machine '+m.tcl_path(fixture)+']; delete_machine $old; activate_machine $new')
   data=bytes.fromhex(e.command('binary encode hex [debug read_block {Makoto ADPCM RAM} 0 262144]'));assert data==pattern
   e.command('debug write {Makoto ADPCM RAM} 262143 165');assert e.command('debug read {Makoto ADPCM RAM} 262143')=='165'
   migrated=out/'migrated.oms';e.command('store_machine [machine] '+m.tcl_path(migrated));want=pattern[:-1]+bytes([165]);assert ram(sound(migrated).find('sampleRAM'))==want
   report['migration']='v5 array loaded with all 262144 patterned bytes exact; debugger last-byte write and new blob save exact'
   # Blob-backed RAM must participate in native rewind, including debug writes.
   e.command('reverse start');step(e,.6);t=e.command('machine_info time');step(e,.6)
   e.command('debug write {Makoto ADPCM RAM} 262143 90; reverse goto '+t)
   assert e.command('debug read {Makoto ADPCM RAM} 262143')=='165';report['rewind']='RAM restored to pre-edit value'
 finally:e.close()
report['rewind_scope']='Inline snapshot bytes only; delta-block storage is separate and not included by reverse debug.'
(out/'results.json').write_text(json.dumps(report,indent=2));print(out);print(json.dumps(report,indent=2))
