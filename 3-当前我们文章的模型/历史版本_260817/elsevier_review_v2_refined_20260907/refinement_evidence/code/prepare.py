from pathlib import Path
import hashlib,json,shutil
TMP=Path(__file__).resolve().parent;ROOT=TMP.parents[1]
SOURCE=ROOT.parent/'260817/elsevier_review_v2_figlayout_20260907'
NEW=ROOT.parent/'260817/elsevier_review_v2_refined_20260907'
assert not NEW.exists(),'Refusing to replace an existing refined version'
for name in ['submit_figure','supplementary_data','refinement_evidence/baseline','refinement_evidence/data','refinement_evidence/code','refinement_evidence/validation']:(NEW/name).mkdir(parents=True,exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
protected={str(p.resolve()):sha(p) for p in SOURCE.rglob('*') if p.is_file()}
(NEW/'refinement_evidence/protected_previous.json').write_text(json.dumps(protected,ensure_ascii=False,indent=2),encoding='utf-8')
for p in SOURCE.iterdir():
 if p.is_file() and p.suffix in ['.tex','.bib','.bbl','.cls','.sty','.bst','.jpeg']:shutil.copy2(p,NEW/p.name)
for folder in ['submit_figure','supplementary_data']:
 for p in (SOURCE/folder).iterdir():
  if p.is_file():shutil.copy2(p,NEW/folder/p.name)
for p in (SOURCE/'explanation_evidence/data').iterdir():
 if p.is_file():shutil.copy2(p,NEW/'refinement_evidence/data'/p.name)
for name in ['main.tex','main.pdf']:shutil.copy2(SOURCE/name,NEW/'refinement_evidence/baseline'/name)
for name in ['fig12_horizontal_modes.pdf','fig16_modal_shares.pdf']:shutil.copy2(SOURCE/'submit_figure'/name,NEW/'refinement_evidence/baseline'/name)
shutil.copy2(__file__,NEW/'refinement_evidence/code/prepare.py')
print(json.dumps({'source_protected':len(protected),'new':str(NEW)},ensure_ascii=False))
