from pathlib import Path
import ast,hashlib,json,zipfile
import numpy as np
from scipy.io import loadmat
OUT=Path(__file__).resolve().parents[1];ROOT=OUT.parents[1]
TMP=ROOT/'temp/unified_full15_equal_delay_20260916';RES=OUT/'results'
REVIEW=ROOT/'pro_reviews/unified_full15_equal_delay_20260916'
REPORT=ROOT/'reports/完整框架等时滞统一模型方案汇报.html'
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def read(p):return json.loads(p.read_text('utf-8'))
for row in read(OUT/'source_manifest.json'):
    assert sha(Path(row['source']))==row['sha256']
    assert sha(OUT/row['copy'])==row['sha256']
protected=[]
for row in read(RES/'protection_before.json'):
    folder=Path(row['folder']);m=read(folder/'delivery_manifest.json')
    for f in m['files']:assert sha(folder/f['path'])==f['sha256'],f['path']
    if 'report' in m and isinstance(m['report'],dict):
        assert sha(Path(m['report']['path']))==m['report']['sha256']
    protected.append(dict(folder=str(folder),unchanged_files=len(m['files'])))
assert sum(x['unchanged_files'] for x in protected)==487
(RES/'protection_after.json').write_text(json.dumps(dict(status='PASS',sources=7,previous_files=protected),ensure_ascii=False,indent=2),'utf-8')
repeat=TMP/'independent_review_copy/results';validation=[]
for name,num in [('validation_python.json',1066),('validation_matlab.json',432),('validation_error_identities.json',24)]:
    a=read(RES/name);b=read(repeat/name)
    key='checks' if name=='validation_matlab.json' else 'tests'
    assert a['status']==b['status']=='PASS' and a[key]==b[key]==num
    assert a['max_normalized_residual']<=1e-10 and b['max_normalized_residual']<=1e-10
    validation.append(dict(file=name,checks=num,max_normalized_residual=a['max_normalized_residual'],independent_repeat='PASS'))
a=loadmat(RES/'operators.mat');b=loadmat(repeat/'operators.mat')
for k in a:
    if not k.startswith('__'):assert np.array_equal(a[k],b[k]),k
for name in ['browser_qa.json','pdf_qa.json']:
    d=read(RES/name);assert d['status']==d['visual']=='PASS'
    assert d['report_sha256']==sha(REPORT)
    assert d['theory_pdf_sha256']==sha(OUT/'theory/unified_full15.pdf')
for p in (OUT/'code').glob('*.py'):ast.parse(p.read_text('utf-8'),filename=str(p))
assert not list(OUT.rglob('__pycache__'))
assert set(p.suffix for p in (OUT/'theory').iterdir())=={'.tex','.pdf'}
result=dict(status='PASS',validation=validation,total_checks=1522,
    all_tests_tolerance=1e-10,max_normalized_residual=max(x['max_normalized_residual'] for x in validation),
    frozen_sources_unchanged=7,prior_delivery_files_unchanged=487,
    independent_temp_repeat='PASS',exported_matrices_repeat='bitwise equal',
    theory_pdf_pages=7,report_print_pages=10,visual_qa='PASS',
    new_time_histories=0,new_pole_scans=0,route_adoption='pending user research decision',
    pro_review='prepared locally; not sent or received',report_sha256=sha(REPORT),
    theory_pdf_sha256=sha(OUT/'theory/unified_full15.pdf'))
(RES/'delivery_checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf-8')
files=[dict(path=str(p.relative_to(OUT)),sha256=sha(p),bytes=p.stat().st_size)
    for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='delivery_manifest.json']
manifest=dict(status='PASS',files=files,delivered_files=len(files),
    report=dict(path=str(REPORT),sha256=sha(REPORT)))
(OUT/'delivery_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf-8')
archive=REVIEW/'unified_full15_review.zip'
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
    for p in sorted(OUT.rglob('*')):
        if p.is_file():z.write(p,str(p.relative_to(OUT)))
    z.write(REVIEW/'REVIEW_REQUEST.md','REVIEW_REQUEST.md')
    z.write(REPORT,'完整框架等时滞统一模型方案汇报.html')
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    for f in files:assert hashlib.sha256(z.read(f['path'].replace('\\','/'))).hexdigest()==f['sha256']
    assert z.read('theory/unified_full15.pdf')==(OUT/'theory/unified_full15.pdf').read_bytes()
state=dict(status='prepared_locally',sent=False,receiver_read=False,response_received=False,
    archive=dict(path=str(archive),bytes=archive.stat().st_size,sha256=sha(archive)),
    request_sha256=sha(REVIEW/'REVIEW_REQUEST.md'),package_manifest_sha256=sha(OUT/'delivery_manifest.json'),
    theory_pdf_sha256=sha(OUT/'theory/unified_full15.pdf'),theory_tex_sha256=sha(OUT/'theory/unified_full15.tex'))
(REVIEW/'review_manifest.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),'utf-8')
print('DELIVERY_PASS',len(files),'audit files; 1522 checks; 487 previous files unchanged; zip',archive.stat().st_size,'bytes')
