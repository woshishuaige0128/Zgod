"""Small algebra checks for the residual and omitted-mode identities."""
import json
import numpy as np
from scipy import linalg as la
from unified_model import *

frame,audit,saved=sources();gain=saved['Full15']['gain'];tests=[]
def check(name,a,b):
    v=float(la.norm(a-b)/max(la.norm(b),1e-30))
    assert v<=1e-10,(name,v)
    tests.append(dict(name=name,normalized_residual=v,passed=True))
for d in [1,2]:
    F=full_model(d,frame,audit,gain);W,*_=cb_basis(frame,d,9 if d==1 else 10)
    for m in [0,3]:
        T,*_=cb_basis(frame,d,m);R=project(F,T);r=R.n
        for freq in [3,9,20]:
            z=np.exp(2j*np.pi*freq*H);Z=characteristic(F,z,4);Zr=characteristic(R,z,4)
            q=la.solve(Zr,R.f);x=la.solve(Z,F.f);Y=physical_output(F,z,4)
            residual=F.f-Z@T@q
            check(f'd{d}_m{m}_{freq}Hz_output_error',Y@(T@q-x),-Y@la.solve(Z,residual))
            A=W.T@Z@W;b=W.T@F.f
            Arr,Aro,Aor,Aoo=A[:r,:r],A[:r,r:],A[r:,:r],A[r:,r:]
            schur=Arr-Aro@la.solve(Aoo,Aor);load=b[:r]-Aro@la.solve(Aoo,b[r:])
            qr=la.solve(schur,load)
            check(f'd{d}_m{m}_{freq}Hz_omitted_schur',qr,la.solve(A,b)[:r])
result=dict(status='PASS',tests=len(tests),tolerance=1e-10,
    max_normalized_residual=max(x['normalized_residual'] for x in tests),checks=tests,
    new_time_histories=0,scope='frequency residual and omitted-mode Schur identities only')
(OUT/'results/validation_error_identities.json').write_text(json.dumps(result,indent=2),'utf-8')
print('ERROR_IDENTITIES_PASS',result['tests'],result['max_normalized_residual'])
