"""Independent response QA, fixed-physical-delay refinement, export to MATLAB."""
import argparse,json
from pathlib import Path
import numpy as np
from scipy.io import savemat,loadmat
from scipy import linalg as la
from full15_model import *
from case_dynamics import eigensystem,compact

def main(out):
    dyn=json.loads((out/'dynamics.json').read_text('utf-8'))
    resp=json.loads((out/'responses.json').read_text('utf-8'))
    _,inputs,_,_=load_sources();t=inputs['time'];u=inputs['eq_on_grid']
    checks=[];refinements={};exports=[]
    def check(name,value,tolerance):
        checks.append(dict(name=name,value=float(value),tolerance=tolerance,passed=bool(value<=tolerance)))
    for d in [1,2]:
        D=dyn['divisions'][str(d)];R=resp['divisions'][str(d)];models=family(d)
        for e in R['tones']:
            for name,v in e['models'].items():
                check(f'd{d} n{e["n"]} f{e["frequency_hz"]} {name} amplitude',max(v['steady_prediction']['amplitude_error_pct']),.5)
                check(f'd{d} n{e["n"]} f{e["frequency_hz"]} {name} phase',max(v['steady_prediction']['phase_error_deg']),.5)
                check(f'd{d} n{e["n"]} f{e["frequency_hz"]} {name} free frequency',v['free_identification']['frequency_error_pct'],.5)
                check(f'd{d} n{e["n"]} f{e["frequency_hz"]} {name} free decay',v['free_identification']['decay_error_pct'],2.)
        slow=R['slow_chirp'];assert slow['converged']
        for name,v in slow['runs'][-1]['models'].items():
            check(f'd{d} {name} slow FRF',v['quasisteady_complex_error_pct'],1.)
            check(f'd{d} {name} slow speed convergence',v['change_from_previous_pct'],1.)
        n=D['selection']['near_n'];refinements[str(d)]={}
        for name,F in models.items():
            raw=np.load(out/R['earthquake'][str(n)]['file'])[name]
            # MATLAB uses these validated physical coefficients but independently
            # implements force balance, its own linear solve, and history shifts.
            exports.append(dict(name=f'd{d}_{name}',n=n,h=H,M=F.M,C=F.C,K=F.K,C0=F.C0,K0=F.K0,
                Uc=F.Uc,Uk=F.Uk,S=F.S,f=F.f,Yn=F.Yn,Y0=F.Y0,Jd=F.Jd,u=u[:-1],expected=raw))
            values={1:raw};items={}
            for factor in [2,4]:
                tt=np.arange((len(t)-1)*factor+1)*(H/factor);uu=np.interp(tt,t,u)
                yy,_=simulate(F,n*factor,uu[:-1],H/factor);values[factor]=yy[::factor]
                assert len(values[factor])==len(t)
                items[str(factor)]=dict(h=H/factor,tau_s=n*H,to_original_step=error_metrics(raw[:,3:],values[factor][:,3:]))
            items['half_to_quarter']=error_metrics(values[2][:,3:],values[4][:,3:])
            items['base_to_quarter']=error_metrics(values[1][:,3:],values[4][:,3:])
            # Refinement is evidence, not a manufactured pass criterion.
            refinements[str(d)][name]=items
            np.savez_compressed(out/f'd{d}_{name}_step_refinement.npz',t=t,h1=values[1],h2=values[2],h4=values[4])
        # Full-reference near-boundary candidates remain visible even when the
        # reduced models predict instability. No steady-state response is assigned.
        records=[]
        for n in sorted(set([D['selection']['proposed_normal_n'],D['selection']['proposed_near_n']])):
            records.append(dict(n=n,tau_s=n*H,models={name:compact(eigensystem(F,n)) for name,F in models.items()}))
        D['reference_candidate_assessment']=records
    savemat(out/'matlab_case_inputs.mat',dict(cases=np.array(exports,dtype=object)),long_field_names=True,oned_as='column',do_compression=True)
    (out/'case_validation.json').write_text(json.dumps(dict(status='PASS' if all(c['passed'] for c in checks) else 'FAIL',checks=checks,step_refinement=refinements,matlab='pending'),indent=2),'utf-8')
    (out/'dynamics.json').write_text(json.dumps(dyn,ensure_ascii=False,indent=2),'utf-8')
    print('Response checks',len(checks),'PASS',all(c['passed'] for c in checks),flush=True)
    print('Step refinement',json.dumps(refinements),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=Path);main(p.parse_args().out)
