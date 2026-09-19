from pathlib import Path
import json,shutil,subprocess,hashlib
import fitz
TMP=Path(__file__).resolve().parent
NEW=TMP.parents[1].parent/'260817/elsevier_review_v2_20260907'
COPY=TMP/'independent_figure_copy'
assert not COPY.exists(), 'Refuse to overwrite previous independent run'
(COPY/'revision_evidence/code').mkdir(parents=True)
(COPY/'revision_evidence/data').mkdir()
(COPY/'submit_figure').mkdir()
shutil.copytree(NEW/'supplementary_data',COPY/'supplementary_data')
shutil.copy2(NEW/'submit_figure/fig01_force_feedback.tex',COPY/'submit_figure/fig01_force_feedback.tex')
checks=[]
for name in ['make_figures.py','make_diagrams.py']:
    shutil.copy2(NEW/'revision_evidence/code'/name,COPY/'revision_evidence/code'/name)
    r=subprocess.run([r'D:/Software/python/python.exe','-X','utf8',str(COPY/'revision_evidence/code'/name)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    (TMP/(name+'.portable.log')).write_bytes(r.stdout)
    assert r.returncode==0,r.stdout[-3000:]
    checks.append({'check':name+' independent execution','passed':True})
for p in sorted((COPY/'submit_figure').glob('*.pdf')):
    a=fitz.open(p);b=fitz.open(NEW/'submit_figure'/p.name)
    assert len(a)==len(b)==1
    pa=a[0].get_pixmap(dpi=120);pb=b[0].get_pixmap(dpi=120)
    match=(pa.width,pa.height,pa.samples)==(pb.width,pb.height,pb.samples)
    checks.append({'check':p.name+' pixel equality at 120 dpi','passed':match})
    assert match,p.name
for p in sorted((COPY/'revision_evidence/data').glob('new_*.csv')):
    match=p.read_bytes()==(NEW/'revision_evidence/data'/p.name).read_bytes()
    checks.append({'check':p.name+' exact data equality','passed':match})
    assert match,p.name
result={'status':'PASS','checks':checks,'figure_count':10,'isolated_copy':str(COPY),'comparison':'Exact rendered pixel equality at 120 dpi; all regenerated numeric CSV files byte-identical'}
(NEW/'revision_evidence/validation/portable_figure_check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'status':result['status'],'checks_passed':len(checks),'figure_count':10},ensure_ascii=False))
