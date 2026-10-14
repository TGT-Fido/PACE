"""Run: python docs/tools/build_update.py 6.0.1 https://host/PACE_App_6.0.1.zip"""
import hashlib,json,sys,zipfile
from pathlib import Path
root=Path(__file__).resolve().parents[2];version,url=sys.argv[1:3]
if (root/'app/VERSION').read_text().strip()!=version:raise SystemExit('Update app/VERSION and server.VERSION first')
output=root/('PACE_App_'+version+'.zip')
with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
 for f in sorted((root/'app').rglob('*')):
  if f.is_file() and '__pycache__' not in f.parts and f.suffix!='.pyc':z.write(f,f.relative_to(root))
manifest={'format':'PACE-update-1','version':version,'url':url,'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'notes':'Read the release notes before installing.'}
(root/'latest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(output)
