"""Reference-selected critical-frequency and omitted-load diagnostics."""
import argparse,json
from pathlib import Path
import numpy as np
from scipy import linalg as la
from scipy.optimize import minimize_scalar
from scipy.signal import find_peaks
from full15_model import *
from case_dynamics import eigensystem

def main(out):
    dyn=json.loads((out/'dynamics.json').read_text('utf-8'));rows={};arrays={}
    for d in [1,2]:
        D=dyn['divisions'][str(d)];models=family(d);F=models['Full15'];n=D['selection']['near_n']
        first=D['selection']['first_full_unstable_n'];critical=eigensystem(F,first)
        j=int(np.argmax(abs(critical['z'])));cf=critical['frequency_hz']
        # A reference-only window, centred at its first unstable root frequency.
        fg=np.linspace(.8*cf,1.2*cf,1601);FR=np.array([frequency_response(F,f,n) for f in fg]);peaks,_=find_peaks(la.norm(FR,axis=1))
        if len(peaks):
            idx=peaks[np.argmin(abs(fg[peaks]-cf))]
            opt=minimize_scalar(lambda f:-la.norm(frequency_response(F,f,n)),bounds=(fg[idx-1],fg[idx+1]),method='bounded')
            peak=float(opt.x)
        else:peak=None
        arrays[f'd{d}_frequency']=fg
        vals={}
        for name,R in models.items():
            hh=np.array([frequency_response(R,f,n) for f in fg]);arrays[f'd{d}_{name}']=hh
            vals[name]=dict(frf_norm_error_pct=float(100*la.norm(hh-FR)/la.norm(FR)))
            if name!='Full15':
                pred=np.array([residual_error(F,R,np.exp(2j*np.pi*f*H),n)[0] for f in fg])
                residual=float(la.norm(hh-FR-pred)/la.norm(FR));assert residual<=1e-10
                vals[name]['residual_identity']=residual
        ret=RETAINED[d];con=np.array([i for i in range(15) if i not in ret])
        Kcc=F.K[np.ix_(con,con)];qfull=la.solve(F.K,F.f);T,_=cb_basis(F,0);qg=T@la.solve(T.T@F.K@T,T.T@F.f)
        loadcorr=np.zeros(15);loadcorr[con]=la.solve(Kcc,F.f[con])
        loadres=float(la.norm(qfull-qg-loadcorr)/la.norm(qfull));assert loadres<=1e-10
        Lfull=F.Yn@qfull;Lg=F.Yn@qg;Lcb=models['CB3'].Yn@la.solve(models['CB3'].K,models['CB3'].f)
        rows[str(d)]=dict(n=n,tau_s=n*H,first_unstable_tau_s=first*H,critical_frequency_hz=cf,
            critical_input_output_residue_abs=np.abs(critical['residues'][:,j]).tolist(),
            common_stable_reference_peak_hz=peak,window_hz=[float(fg[0]),float(fg[-1])],models=vals,
            internal_force_norm=float(la.norm(F.f[con])),static_omitted_load_identity_residual=loadres,
            static_relative_error_pct=dict(Guyan=(100*(Lg-Lfull)/Lfull).tolist(),CB3=(100*(Lcb-Lfull)/Lfull).tolist()))
    np.savez_compressed(out/'critical_mechanism.npz',**arrays)
    (out/'critical_mechanism.json').write_text(json.dumps(dict(status='PASS',divisions=rows),indent=2),'utf-8')
    print(json.dumps(rows),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=Path);main(p.parse_args().out)
