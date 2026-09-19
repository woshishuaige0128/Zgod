"""Independent augmented-state response and forced-equilibrium checks."""
import json,csv,time,sys
import numpy as np
from scipy import signal
from scipy.io import loadmat
from delay_model import *

def output_operator(m,delays):
    A,b=transition(m,delays);O=np.zeros((6,A.shape[0]));O[:3,:m.n]=m.Yp;O[3:,:m.n]=m.Yn
    for ell,delay in enumerate(delays):
        if not delay:continue
        r=m.Yp@m.S[ell];O[:3,:m.n]-=np.outer(r,m.S[ell])
        if delay==1:O[:3,m.n:2*m.n]+=np.outer(r,m.S[ell])
        else:O[:3,2*m.n+2*(delay-2)+ell]+=r
    return A,b,O

def main():
    src=Path(sys.argv[1]) if len(sys.argv)>1 else CASE/'results/matlab_run'
    models,_,_=build_models();rows=json.loads((CASE/'results/selected_delays.json').read_text('utf-8'))
    t,inputs=load_inputs();checks=[];maxrel=0;summary=[];data={};baseline={}
    for row in rows:
        delays=(row['n1'],row['n2']);tag=row['key'];data[tag]={}
        for exc,ag in inputs.items():
            data[tag][exc]={}
            for name,m in models.items():
                ref=loadmat(src/f'{tag}_{exc}_{name}.mat')
                A,b,O=output_operator(m,delays)
                _,yp,_=signal.dlsim((A,b[:,None],O,np.zeros((6,1)),DT),ag[:,None],t=t)
                physical=yp[:,:3]*1000;numerical=yp[:,3:]*1000
                re=max(relative(physical,ref['physical_mm']),relative(numerical,ref['numerical_mm']))
                ad=max(float(np.max(abs(physical-ref['physical_mm']))),float(np.max(abs(numerical-ref['numerical_mm']))))
                maxrel=max(maxrel,re);assert re<1e-9,(tag,exc,name,re)
                # Recovered first/third physical storeys equal the delayed commands.
                q=ref['q'];v=ref['v'];align=0
                for ell,floor in enumerate([0,2]):
                    d=delays[ell];command=q@m.S[ell]*1000
                    lagged=np.r_[np.zeros(d),command[:len(t)-d]] if d else command
                    align=max(align,float(np.max(abs(ref['physical_mm'][:,floor]-lagged))))
                assert align/max(1,float(np.max(abs(ref['physical_mm']))))<1e-10
                # Check actual delayed-force balance at spread time indices.
                B,c0,k0,cs,ks=operators(m);residual=0
                for k in [1,1023,7000,15000,30000,40959]:
                    force=m.force*ag[k]-c0@v[k]-k0@q[k]
                    for ell,d in enumerate(delays):
                        if k>=d:force-=cs[ell]@v[k-d]+ks[ell]@q[k-d]
                    lhs=B@(v[k+1]-v[k])/DT
                    residual=max(residual,relative(lhs,force))
                assert residual<1e-8,(tag,exc,name,residual)
                checks.append(dict(delay=tag,input=exc,model=name,relative_difference=re,max_absolute_difference_mm=ad,force_residual=residual,passed=True))
                data[tag][exc][name]={'physical_mm':ref['physical_mm'],'numerical_mm':ref['numerical_mm']}
                if tag=='n00_00':baseline[(exc,name)]=ref['physical_mm']
        print('CHECKED',tag,flush=True)
    out=CASE/'results'
    def metrics(y,ref):
        err=y-ref;span=np.ptp(ref,axis=0)
        return 100*np.sqrt(np.trapezoid(err**2,t,axis=0)/(t[-1]-t[0]))/span,np.max(abs(err),axis=0)
    for row in rows:
        tag=row['key'];payload={'time_s':t}
        for exc in inputs:
            for name in models:
                p=data[tag][exc][name]['physical_mm'];n=data[tag][exc][name]['numerical_mm']
                payload[f'{exc}_{name}_physical_mm']=p;payload[f'{exc}_{name}_numerical_mm']=n
                r19=data[tag][exc]['Uncondensed19']['physical_mm'];r15=data[tag][exc]['Full15']['physical_mm'];r0=baseline[(exc,'Full15')]
                m19,p19=metrics(p,r19);m15,p15=metrics(p,r15);m0,p0=metrics(p,r0)
                for floor in range(3):
                    fixed19=100*np.sqrt(np.trapezoid((p[:,floor]-r19[:,floor])**2,t)/40)/np.ptp(r0[:,floor])
                    summary.append(dict(key=tag,n1=row['n1'],n2=row['n2'],tau1_ms=row['tau1_ms'],tau2_ms=row['tau2_ms'],input=exc,model=name,floor=floor+1,stability=row['status'][name],rho=row['rho_'+name],nrmse_same_interface_percent=m19[floor],max_error_same_interface_mm=p19[floor],error_same_interface_fixed_scale_percent=fixed19,nrmse_full15_same_delay_percent=m15[floor],max_error_full15_same_delay_mm=p15[floor],nrmse_ideal_full15_percent=m0[floor],max_error_ideal_full15_mm=p0[floor],peak_response_mm=float(np.max(abs(p[:,floor]))),peak_interface_gap_mm=float(np.max(abs(n[:,floor]-p[:,floor])))))
        np.savez_compressed(out/f'{tag}_responses.npz',**payload)
    with (out/'response_metrics.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(summary[0]));w.writeheader();w.writerows(summary)
    (out/'response_checks.json').write_text(json.dumps({'status':'PASS','comparisons':len(checks),'max_relative_difference':maxrel,'checks':checks},indent=2),'utf-8')
    print('ALL_RESPONSE_CHECKS_PASS',len(checks),'max relative',maxrel,flush=True)

if __name__=='__main__':main()
