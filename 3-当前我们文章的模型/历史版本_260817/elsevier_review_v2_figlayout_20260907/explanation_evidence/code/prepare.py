from pathlib import Path
import json,csv,hashlib,shutil,re
import numpy as np
from scipy.io import loadmat

TMP=Path(__file__).resolve().parent;ROOT=TMP.parents[1]
SOURCE=ROOT.parent/'260817/elsevier_review_v2_20260907'
NEW=ROOT.parent/'260817/elsevier_review_v2_figlayout_20260907'
assert not NEW.exists(),'Refuse to overwrite a previous layout package'
for d in ['submit_figure','supplementary_data','explanation_evidence/baseline','explanation_evidence/data','explanation_evidence/code','explanation_evidence/validation']:(NEW/d).mkdir(parents=True,exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
protected={str(p.resolve()):sha(p) for p in SOURCE.rglob('*') if p.is_file()}
(TMP/'protected_v2.json').write_text(json.dumps(protected,ensure_ascii=False,indent=2),encoding='utf-8')
for p in SOURCE.iterdir():
    if p.is_file() and p.suffix in ['.tex','.bib','.bbl','.cls','.sty','.bst','.jpeg']:shutil.copy2(p,NEW/p.name)
for p in (SOURCE/'submit_figure').glob('*.pdf'):shutil.copy2(p,NEW/'submit_figure'/p.name)
for p in (SOURCE/'supplementary_data').iterdir():
    if p.is_file():shutil.copy2(p,NEW/'supplementary_data'/p.name)
for name in ['main.tex','main.pdf'] :shutil.copy2(SOURCE/name,NEW/'explanation_evidence/baseline'/name)
for name in ['fig12_horizontal_modes.pdf','fig15_peak_drift.pdf','fig16_modal_shares.pdf']:shutil.copy2(SOURCE/'submit_figure'/name,NEW/'explanation_evidence/baseline'/name)
for name in ['new_horizontal_modes.csv','new_modes_frequencies.csv','new_peak_drift.csv','new_modal_shares.csv','new_actuator_share_contributions.csv']:shutil.copy2(SOURCE/'revision_evidence/data'/name,NEW/'explanation_evidence/data'/name)

def readcsv(name):return list(csv.DictReader((SOURCE/'revision_evidence/data'/name).open(encoding='utf-8-sig')))
expected_share={(int(x['division']),x['method'],int(x['physical_dof'])):float(x['share']) for x in readcsv('new_modal_shares.csv')}
checks=[];modal=[];models=[]
def check(name,value,tolerance=1e-10):
    passed=abs(value)<=tolerance;checks.append({'check':name,'error':float(value),'tolerance':tolerance,'passed':bool(passed)});assert passed,(name,value)
for div in [1,2]:
    d=loadmat(NEW/'supplementary_data'/f'division_{"I"*div}_matrices.mat');M=d['M_full'];perm=np.r_[d['master_dofs'].ravel(),d['slave_dofs'].ravel()].astype(int)-1
    influence=np.zeros(15);influence[[0,5,10]]=1
    for method,key in [('Full','full'),('Guyan','guyan'),('CB','cb')]:
        # Independent numerical route: eig(M^-1 K), compared with prior generalized eig results.
        ev,vec=np.linalg.eig(np.linalg.solve(d['M_'+key],d['K_'+key]));idx=np.argsort(ev.real);ev=ev[idx];vec=vec[:,idx].real
        check(f'imaginary eigenvalues {div}/{method}',max(abs(ev.imag)),1e-7)
        if key!='full':
            expanded=np.empty((15,vec.shape[1]));expanded[perm,:]=d['T_'+key]@vec;vec=expanded
        vec=vec/np.sqrt(np.sum(vec*(M@vec),axis=0));vec*=np.where(vec[10,:]>=0,1,-1)
        V=vec[:,:5];gamma=V.T@M@influence;weights=gamma**2/sum(gamma**2)
        shares_by_mode=np.diag(M)[:,None]*V**2;shares_by_mode/=shares_by_mode.sum(axis=0)
        weighted=shares_by_mode*weights;shares=weighted.sum(axis=1)
        check(f'sum modal weights {div}/{method}',sum(weights)-1)
        check(f'sum physical shares {div}/{method}',sum(shares)-1)
        for j,value in enumerate(shares,1):check(f'physical share {div}/{method}/{j}',value-expected_share[div,method,j])
        models.append({'division':div,'method':method,'frequencies_hz':(np.sqrt(ev.real)/(2*np.pi))[:5].tolist(),'gamma':gamma.tolist(),'weights':weights.tolist(),'mass_diagonal':np.diag(M).tolist(),'expanded_modes':V.tolist(),'coordinate_fraction_per_mode':shares_by_mode.tolist(),'weighted_contribution_per_mode':weighted.tolist(),'shares':shares.tolist()})

drift=[];expected_drift={(int(x['division']),x['excitation'],x['method'],int(x['storey'])):float(x['peak_drift_percent']) for x in readcsv('new_peak_drift.csv')}
for div in [1,2]:
    for excitation in ['eq','chirp']:
        a=np.loadtxt(NEW/'supplementary_data'/f'response_division_{div}_{excitation}.csv',delimiter=',',skiprows=1)
        for k,method in enumerate(['Full','Guyan','CB']):
            x=a[:,[1+k,4+k,7+k]]
            for floor in [1,2,3]:
                lower=x[:,floor-2] if floor>1 else np.zeros(len(x));upper=x[:,floor-1]
                relative=upper-lower;n=int(np.argmax(np.abs(relative)));peak=abs(relative[n])/635*100
                check(f'peak drift {div}/{excitation}/{method}/{floor}',peak-expected_drift[div,excitation,method,floor])
                drift.append({'division':div,'excitation':excitation,'method':method,'storey':floor,'peak_drift_percent':float(peak),'peak_time_s':float(a[n,0]),'upper_displacement_mm':float(upper[n]),'lower_displacement_mm':float(lower[n]),'signed_relative_displacement_mm':float(relative[n]),'peak_relative_displacement_mm':float(abs(relative[n])),'height_mm':635})

contributions=[]
for div in [1,2]:
    full=next(m for m in models if m['division']==div and m['method']=='Full')['shares'];acts=[1,6] if div==1 else[1,11]
    for method in ['Guyan','CB']:
        red=next(m for m in models if m['division']==div and m['method']==method)['shares'];rel=[(red[j-1]-full[j-1])/full[j-1] for j in acts]
        contributions.append({'division':div,'method':method,'actuated_dofs':acts,'full_shares':[full[j-1] for j in acts],'reduced_shares':[red[j-1] for j in acts],'relative_changes':rel,'delta_E':sum(rel),'full_total_actuated_share':sum(full[j-1] for j in acts),'reduced_total_actuated_share':sum(red[j-1] for j in acts),'total_actuated_relative_change':(sum(red[j-1] for j in acts)-sum(full[j-1] for j in acts))/sum(full[j-1] for j in acts)})
data={'models':models,'drifts':drift,'actuator_contributions':contributions,'source_version':'elsevier_review_v2_20260907','formula_source':'main.tex Eqs. (4.3) and (4.4)','full_dofs':15,'selected_modes':5,'layout':'1 row x 4 columns; vertically elongated panels'}
(NEW/'explanation_evidence/data/explanation_calculations.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
(NEW/'explanation_evidence/validation/independent_numeric_checks.json').write_text(json.dumps({'status':'PASS','checks_passed':len(checks),'max_error':max(abs(x['error']) for x in checks),'checks':checks},ensure_ascii=False,indent=2),encoding='utf-8')
(NEW/'explanation_evidence/protected_v2.json').write_text(json.dumps(protected,ensure_ascii=False,indent=2),encoding='utf-8')
shutil.copy2(__file__,NEW/'explanation_evidence/code/prepare.py')
print(json.dumps({'new_package':str(NEW),'checks':len(checks),'full_weights':models[0]['weights'],'example_drift':next(x for x in drift if x['division']==2 and x['excitation']=='chirp' and x['method']=='Guyan' and x['storey']==3),'example_shares':contributions[2]},ensure_ascii=False,indent=2))
