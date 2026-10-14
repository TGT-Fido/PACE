"""Create disposable synthetic test data. Requires reportlab; never use live data."""
import io,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'app'))
from server import Store
from reportlab.pdfgen import canvas
if len(sys.argv)!=2:raise SystemExit('Usage: python create_browser_fixture.py EMPTY_DATA_DIRECTORY')
root=Path(sys.argv[1]).resolve()
if root.exists() and any(root.iterdir()):raise SystemExit('Refusing to use a nonempty directory')
s=Store(root)
for i,name in enumerate(['Website refresh','Archive tools','Design system','Photo portfolio','Language practice','Reading plan','Studio setup','Learning journal','Project Atlas','Field notes','Design guide','Release checklist']):
 p=s.create_project({'name':name});s.update({'id':p['id'],'changes':{'category':['Technology','Creative','Learning'][i%3],'summary':'Synthetic project for browser checks.','milestone':'Review the draft.','color':['#3d87e7','#9871df','#28a69e'][i%3]}})
 b=io.BytesIO();c=canvas.Canvas(b,pagesize=(400,500));c.drawString(40,450,name);c.drawString(40,420,'Search keyword: lantern');c.acroForm.checkbox(name='reviewed',x=45,y=350,checked=False);c.drawString(70,355,'Reviewed');c.showPage();c.save();(s.projects/name/'Overview.pdf').write_bytes(b.getvalue())
 if i==1:(s.projects/name/'Reference.pdf').write_bytes(b.getvalue())
print('Created synthetic data:',root)
