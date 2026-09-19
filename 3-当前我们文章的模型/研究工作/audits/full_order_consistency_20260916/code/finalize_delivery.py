from pathlib import Path
import ast, csv, hashlib, json, sys

OUT = Path(__file__).resolve().parents[1]
ROOT = OUT.parents[1]
RES = OUT / 'results'
REPORT = ROOT / 'reports/原完整框架基准与两套模型一致性核查汇报.html'

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def read(path):
    return json.loads(path.read_text('utf-8'))

sources = read(OUT / 'source_manifest.json')
assert len(sources) == 29
for row in sources:
    assert sha(Path(row['source'])) == row['sha256'], row['source']
    if row['copy']:
        assert sha(OUT / row['copy']) == row['sha256'], row['copy']
protected = []
for name in ['case1_v1_standard_guyan_20260916', 'case2_v1_divisionII_delays_20260916']:
    folder = ROOT / 'cases' / name
    manifest = read(folder / 'delivery_manifest.json')
    for row in manifest['files']:
        assert sha(folder / row['path']) == row['sha256'], row['path']
    protected.append(dict(case=name, verified_files=len(manifest['files'])))
assert sum(x['verified_files'] for x in protected) == 450
protection = dict(status='PASS', source_files_unchanged=len(sources), previous_cases=protected)
(RES / 'source_protection_after.json').write_text(json.dumps(protection, ensure_ascii=False, indent=2), 'utf-8')
print('SOURCE_PROTECTION_PASS', 29, 450)
if '--seal' not in sys.argv:
    sys.exit(0)

algebra = read(RES / 'algebra_checks.json')
assert algebra['status'] == 'PASS' and algebra['checks'] == 134
assert len(algebra['tests']) == 134 and all(x['passed'] for x in algebra['tests'])
assert algebra['tolerance'] == 1e-10 and algebra['max_normalized_residual'] <= 1e-10
matlab = read(RES / 'matlab_source_checks.json')
assert matlab['status'] == 'PASS' and matlab['new_time_integrations'] == 0
rows = list(csv.DictReader((RES / 'error_decomposition.csv').open(encoding='utf-8-sig')))
assert len(rows) == 72
for path in (OUT / 'code').glob('*.py'):
    ast.parse(path.read_text('utf-8'), filename=str(path))
browser = read(RES / 'report_qa.json')
pdf = read(RES / 'print_qa.json')
assert browser['status'] == pdf['status'] == 'PASS'
assert browser['visualReview'] == pdf['visual_review'] == 'PASS'
assert pdf['pages'] == 10
assert browser['report_sha256'] == sha(REPORT)
assert pdf['source_report_sha256'] == sha(REPORT)
for path in OUT.rglob('*.json'):
    read(path)
summary = dict(status='PASS', algebra_checks=134,
    max_normalized_residual=algebra['max_normalized_residual'], tolerance=1e-10,
    existing_equal_delay_decompositions=72, source_files_unchanged=29,
    previous_delivery_files_unchanged=450, new_time_integrations=0,
    report_offline_desktop_mobile_visual='PASS', print_visual_pages=10,
    model_unification='not implemented; differences documented for the next research decision',
    external_review='not performed', report=str(REPORT), report_sha256=sha(REPORT))
(RES / 'delivery_checks.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), 'utf-8')
files = [dict(path=str(p.relative_to(OUT)), bytes=p.stat().st_size, sha256=sha(p))
    for p in sorted(OUT.rglob('*')) if p.is_file()
    and p.name != 'delivery_manifest.json' and '__pycache__' not in p.parts]
(OUT / 'delivery_manifest.json').write_text(json.dumps(dict(status='PASS',
    files=files, delivered_files=len(files), report=dict(path=str(REPORT), sha256=sha(REPORT))),
    ensure_ascii=False, indent=2), 'utf-8')
print('DELIVERY_PASS', len(files), 'audit files; 10 print pages; report verified')
