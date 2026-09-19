"""Full-reference-driven parameter selection and matched dynamics.

Run only after the revised theory review is recorded. Input/output units are SI.
The work directory is explicit so exploratory or validation runs stay in temp.
"""
import argparse,json,time,hashlib
from pathlib import Path
import numpy as np
from scipy import linalg as la
from scipy.optimize import minimize_scalar,linear_sum_assignment
from scipy.signal import find_peaks
from full15_model import *

def eigensystem(F,n,h=H):
    A,b=state_space(F,n,h);Ab,Tb=la.matrix_balance(A,permute=False,scale=True)
    z,vlb,vrb=la.eig(Ab,left=True,right=True);vr=Tb@vrb;vl=la.solve(Tb.T,vlb)
    resid=la.norm(A@vr-vr*z,axis=0)/((la.norm(A,'fro')+abs(z))*la.norm(vr,axis=0))
    assert np.max(resid)<=1e-9
    residual_abs=la.norm(Ab@vrb-vrb*z,axis=0)/la.norm(vrb,axis=0)
    overlaps=abs(np.sum(vlb.conj()*vrb,axis=0))
    condition=la.norm(vlb,axis=0)*la.norm(vrb,axis=0)/np.maximum(overlaps,1e-300)
    bounds=condition*(residual_abs+32*np.finfo(float).eps*la.norm(Ab,'fro'))
    near=(abs(z)>.9)&(abs(abs(z)-1)<=np.maximum(1e-8,10*bounds))
    refined=[]
    if np.any(near):
        import mpmath as mp
        with mp.workdps(70):
            diag=1/np.sqrt(np.diag(F.K));D=np.diag(diag)
            Mh,C0,K0,UcS,UkS=[mp.matrix((D@a@D).tolist()) for a in [algorithm_mass(F,h),F.C0,F.K0,F.Uc@F.S,F.Uk@F.S]]
            hh=mp.mpf(h)
            def detfun(zz):
                dv=(1-1/zz)/hh;da=(zz-2+1/zz)/(hh*hh)
                return mp.det(da*Mh+dv*C0+K0+zz**(-n)*(dv*UcS+UkS))
            for k in np.flatnonzero(near):
                start=mp.mpc(complex(z[k]));root=mp.findroot(detfun,(start,start+mp.mpc('1e-12','1e-12')),tol=mp.mpf('1e-50'),maxsteps=100)
                if abs(root-start)>mp.mpf('1e-5'):raise RuntimeError('High precision root matching is ambiguous')
                if abs(abs(root)-1)<mp.mpf('1e-24'):raise RuntimeError('Unit-circle root remains numerically critical')
                refined.append(dict(index=int(k),change=float(abs(root-start)),modulus=str(abs(root)),precision_digits=70))
                z[k]=complex(root)
    j=int(np.argmax(abs(z)));rho=float(abs(z[j]));dominant=z[j]
    O=state_output(F,n);residues=np.full((3,len(z)),np.nan+0j)
    for k in range(len(z)):
        denom=np.vdot(vl[:,k],vr[:,k])
        if abs(denom)>1e-14:residues[:,k]=(O@vr[:,k])*(np.vdot(vl[:,k],b)/denom)
    char_res=[]
    for k,zk in enumerate(z):
        # Very small roots are checked by the state residual above; negative
        # powers in the characteristic matrix become ill-conditioned near zero.
        if abs(zk)<.1:continue
        q=vr[:F.order,k];Mh=algorithm_mass(F,h)
        dv=(1-1/zk)/h;da=(zk-2+1/zk)/h**2
        terms=[da*Mh,dv*F.C0,F.K0,zk**(-n)*(dv*F.Uc+F.Uk)@F.S]
        denom=sum(la.norm(a,2) for a in terms)*la.norm(q)
        cr=float(la.norm(sum(terms)@q)/max(denom,1e-300));char_res.append(cr)
    assert max(char_res,default=0)<=1e-9
    critical=np.flatnonzero(abs(z)>.9)
    return dict(z=z,vr=vr,residues=residues,rho=rho,stable=bool(rho<1),
                ambiguous=bool(rho==1),decay=float(-np.log(rho)/h),
                frequency_hz=float(abs(np.angle(dominant))/(2*np.pi*h)),
                max_eigen_residual=float(max(resid)),max_characteristic_residual=max(char_res,default=0),
                dominant_balanced_condition=float(condition[j]),dominant_uncertainty_estimate=float(bounds[j]),
                high_precision_refinements=refined)

def compact(e):return {k:v for k,v in e.items() if k not in ['z','vr','residues']}

def first_crossing(F,h,maximum,storage,prefix):
    rows=[];first=None
    for n in range(maximum+1):
        e=eigensystem(F,n,h);storage[f'{prefix}_n{n}_z']=e['z'];rows.append(dict(n=n,tau_s=n*h,**compact(e)))
        if first is None and not e['stable']:first=n
    if any(x['ambiguous'] for x in rows):raise RuntimeError('Unit-circle ambiguity requires independent root refinement')
    if first==0:raise RuntimeError('Reference unstable at zero delay')
    return rows,first

def main(out,review):
    evidence=json.loads(review.read_text('utf-8'))
    if not evidence.get('dependent_cases_authorized_after_review',False):raise RuntimeError('Reviewed theory is required before case execution')
    out.mkdir(parents=True,exist_ok=True);allarrays={};result=dict(protocol_sha256=hashlib.sha256((ROOT/'CASE_PROTOCOL.md').read_bytes()).hexdigest(),divisions={},h=H)
    frame,inputs,_,gain=load_sources();alpha,beta=frame['rayleigh']
    for d in [1,2]:
        start=time.time();F=full_model(d);models=family(d);D={};result['divisions'][str(d)]=D
        lf,pf=la.eigh(F.K,F.M);basefreq=np.sqrt(lf)/(2*np.pi);modal=[]
        for m in range(16-len(RETAINED[d])):
            T,fixed=cb_basis(F,m);R=project(F,T,f'CB{m}');lr,pr=la.eigh(R.K,R.M);xr=T@pr
            mac=abs(pf.T@F.M@xr)**2
            static=R.Yn@la.solve(R.K,R.f);staticfull=F.Yn@la.solve(F.K,F.f)
            modal.append(dict(internal_modes=m,order=R.order,frequency_hz=(np.sqrt(lr)/(2*np.pi)).tolist(),
                         frequency_error_pct=(100*(np.sqrt(lr/lf[:len(lr)])-1)).tolist(),
                         rayleigh_decay=(.5*(alpha+beta*lr)).tolist(),static_floors_per_unit=static.tolist(),
                         static_error_floors=(static-staticfull).tolist(),mac_diagonal=np.diag(mac).tolist()))
            allarrays[f'd{d}_m{m}_modes']=xr
        D['modal_convergence']=modal;D['full_passive_frequency_hz']=basefreq.tolist();D['fixed_interface_frequency_hz']=(np.sqrt(fixed)/(2*np.pi)).tolist()
        allarrays[f'd{d}_full_modes']=pf
        D['full_modal_participation']=dict(input=(pf.T@F.f).tolist(),floors=(F.Yn@pf).tolist(),ports=(F.S@pf).tolist(),
            stiffness_feedback=(pf.T@F.Uk).tolist(),damping_feedback=(pf.T@F.Uc).tolist())
        # Selection is based on Full15 first; reduced models cannot set the scan.
        maxn=64
        fullrows,crit=first_crossing(F,H,maxn,allarrays,f'd{d}_Full15_h1')
        while crit is None and maxn<256:
            maxn*=2;fullrows,crit=first_crossing(F,H,maxn,allarrays,f'd{d}_Full15_h1')
        if crit is None:raise RuntimeError('No first instability in predeclared range; report scope before extending')
        D['scan']={'Full15':fullrows};D['critical_intervals_s']={}
        for name,R in models.items():
            if name=='Full15':rows,c=fullrows,crit
            else:rows,c=first_crossing(R,H,maxn,allarrays,f'd{d}_{name}_h1')
            D['scan'][name]=rows;D['critical_intervals_s'][name]=None if c is None else [(c-1)*H,c*H]
        proposed_normal=max(0,int(np.floor(.5*crit)));proposed_near=crit-1
        def common_at_or_below(target):
            eligible=[n for n in range(target+1) if all(D['scan'][name][n]['stable'] for name in models)]
            return max(eligible)
        normal=common_at_or_below(proposed_normal);near=common_at_or_below(proposed_near)
        D['selection']=dict(first_full_unstable_n=crit,proposed_normal_n=proposed_normal,proposed_near_n=proposed_near,
                            normal_n=normal,near_n=near,representative_n=sorted(set([0,normal,near])),
                            rule='Full15 first crossing, then common stability only; no error maximization')
        if near==0:raise RuntimeError('No stable nonzero delay at original step; refine protocol before response cases')
        # Reference peaks, on original excitation band, shared by all methods.
        fgrid=np.linspace(.1,10,1981);D['frequency_cases']={}
        for n in D['selection']['representative_n']:
            for name,R in models.items():
                hh=np.array([frequency_response(R,f,n) for f in fgrid]);allarrays[f'd{d}_n{n}_{name}_frf']=hh
                if name!='Full15':
                    pred=np.array([residual_error(F,R,np.exp(2j*np.pi*f*H),n)[0] for f in fgrid])
                    direct=hh-allarrays[f'd{d}_n{n}_Full15_frf']
                    err=la.norm(pred-direct)/la.norm(allarrays[f'd{d}_n{n}_Full15_frf'])
                    assert err<=1e-10;allarrays[f'd{d}_n{n}_{name}_frf_error_prediction']=pred
            amp=la.norm(allarrays[f'd{d}_n{n}_Full15_frf'],axis=1);peaks,_=find_peaks(amp)
            selected=[]
            for idx in peaks[:2]:
                opt=minimize_scalar(lambda f:-la.norm(frequency_response(F,f,n)),bounds=(fgrid[idx-1],fgrid[idx+1]),method='bounded',options={'xatol':1e-10})
                selected.append(float(opt.x))
            D['frequency_cases'][str(n)]=dict(tone_frequencies_hz=selected,reference_peaks_hz=fgrid[peaks].tolist(),
                selection_status='two resolved reference peaks' if len(selected)==2 else 'fewer than two peaks; retain only observed peaks')
        allarrays['frequency_hz']=fgrid
        # The complete nested series tests dynamics as well as passive frequency.
        convergence=[];near=D['selection']['near_n'];full_near=allarrays[f'd{d}_n{near}_Full15_frf']
        for m in range(16-len(RETAINED[d])):
            T,_=cb_basis(F,m);R=project(F,T,f'CB{m}');ep=eigensystem(R,near)
            hh=np.array([frequency_response(R,f,near) for f in fgrid]);allarrays[f'd{d}_m{m}_near_frf']=hh
            info=dict(internal_modes=m,**compact(ep),frequency_norm_error_pct=float(100*la.norm(hh-full_near)/la.norm(full_near)),
                      frf_interpretation='steady' if ep['stable'] else 'formal transfer only; unstable')
            convergence.append(info)
        D['delayed_mode_convergence']=convergence
        # Grid refinement: repeat the full first-crossing search up to a fixed
        # physical neighborhood and evaluate the same physical representative tau.
        D['step_refinement']={}
        for factor in [2,4]:
            h=H/factor;refine={}
            for name,R in models.items():
                basecrit=D['critical_intervals_s'][name]
                upper=max(int(np.ceil((basecrit[1] if basecrit else crit*H)/h))+4,crit*factor+4)
                rows,c=first_crossing(R,h,upper,allarrays,f'd{d}_{name}_h{factor}')
                same=[]
                for n in D['selection']['representative_n']:
                    e=eigensystem(R,n*factor,h);same.append(dict(original_n=n,tau_s=n*H,**compact(e)))
                refine[name]=dict(critical_interval_s=None if c is None else [(c-1)*h,c*h],same_physical_delay=same,scan=rows)
            D['step_refinement'][str(factor)]=refine
        # Fixed historical output feedback: same frozen 2x4 matrix per model.
        D['controlled_supplement']={};controlled=family(d,gain=gain)
        for name,R in controlled.items():
            rows,c=first_crossing(R,H,max(16,2*crit),allarrays,f'd{d}_{name}_controlled')
            D['controlled_supplement'][name]=dict(scan=rows,critical_interval_s=None if c is None else [(c-1)*H,c*H])
        D['elapsed_seconds']=time.time()-start
        print(json.dumps(dict(division=d,selection=D['selection'],critical=D['critical_intervals_s'],seconds=D['elapsed_seconds']),ensure_ascii=False),flush=True)
        # Incremental checkpoint after each division; no partial success label.
        (out/'dynamics.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf-8');np.savez_compressed(out/'dynamics_arrays.npz',**allarrays)
    result['status']='PASS';(out/'dynamics.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf-8')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--review',type=Path,required=True);a=p.parse_args();main(a.out,a.review)
