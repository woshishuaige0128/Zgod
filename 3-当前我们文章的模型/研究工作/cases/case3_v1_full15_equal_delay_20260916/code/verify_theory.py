"""Targeted checks for the additional omitted-block and derivative formulas."""
import argparse,json
from pathlib import Path
import numpy as np
from scipy import linalg as la
from full15_model import *

def main(out):
    checks=[];frame,_,_,gain=load_sources();alpha,beta=frame['rayleigh']
    def check(name,a,b,scale):
        val=float(la.norm(a-b)/max(scale,1e-300));checks.append(dict(name=name,residual=val,tolerance=1e-10,passed=val<=1e-10))
    for d in [1,2]:
        for controlled in [False,True]:
            F=full_model(d,gain if controlled else None);W,_=cb_basis(F,15-len(RETAINED[d]))
            for m in [0,3]:
                T,_=cb_basis(F,m);R=project(F,T,f'CB{m}');r=R.order;Q=W[:,r:]
                for s in [0,2+19j,-.5+37j]:
                    tau=4*H;Z=continuous(F,s,tau);Zor=Q.T@Z@T
                    pred=(s*s+alpha*s)*Q.T@F.M@T+(np.exp(-s*tau)-1)*Q.T@(s*(F.C-F.C0)+(F.K-F.K0))@T
                    check(f'd{d}_g{controlled}_m{m}_Zor_{s}',Zor,pred,la.norm(Q)*la.norm(Z)*la.norm(T))
                for n in [0,1,4,5]:
                    for freq in [3.,9.,20.]:
                        z=np.exp(2j*np.pi*freq*H);Z=characteristic(F,z,n);Zr=characteristic(R,z,n)
                        qf=la.solve(W.T@Z@W,W.T@F.f);qr=la.solve(Zr,R.f)
                        Y=F.Y0+z**(-n)*F.Jd@F.S;ref=Y@la.solve(Z,F.f)
                        e=Y@T@qr-ref;Zro=T.T@Z@Q
                        check(f'd{d}_g{controlled}_m{m}_discrete_Schur_n{n}_f{freq}',e,(Y@T@la.solve(Zr,Zro)-Y@Q)@qf[r:],la.norm(ref))
                        er,_=residual_error(F,R,z,n)
                        check(f'd{d}_g{controlled}_m{m}_discrete_residual_n{n}_f{freq}',e,er,la.norm(ref))
            s=-.7+28j;tau=4*H;ds=1e-2;dt=1e-5
            Zs=2*s*F.M+F.C0+np.exp(-s*tau)*(F.Uc-tau*(s*F.Uc+F.Uk))@F.S
            Zt=-s*np.exp(-s*tau)*(s*F.Uc+F.Uk)@F.S
            # Fourth-order central differences reduce cancellation in the
            # large controlled stiffness while preserving the 1e-10 threshold.
            Ds=(-continuous(F,s+2*ds,tau)+8*continuous(F,s+ds,tau)-8*continuous(F,s-ds,tau)+continuous(F,s-2*ds,tau))/(12*ds)
            Dt=(-continuous(F,s,tau+2*dt)+8*continuous(F,s,tau+dt)-8*continuous(F,s,tau-dt)+continuous(F,s,tau-2*dt))/(12*dt)
            check(f'd{d}_g{controlled}_continuous_s_derivative',Zs,Ds,la.norm(Zs))
            check(f'd{d}_g{controlled}_continuous_tau_derivative',Zt,Dt,la.norm(Zt))
    result=dict(status='PASS' if all(c['passed'] for c in checks) else 'FAIL',count=len(checks),maximum_residual=max(c['residual'] for c in checks),checks=checks)
    out.mkdir(parents=True,exist_ok=True);(out/'theory_validation.json').write_text(json.dumps(result,indent=2),'utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='checks'}));print('failures',[c for c in checks if not c['passed']])
    if result['status']!='PASS':raise SystemExit(1)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);main(p.parse_args().out)
