"""Coefficient, coordinate and one-step algebra checks; no forced history."""
from pathlib import Path
import json
import numpy as np
from scipy import linalg as la
from scipy.io import savemat
from unified_model import *

RES=OUT/'results';TOL=1e-10
tests=[];models=[];export={};negative=[];interface_models=[]
def rel(a,b):return float(la.norm(a-b)/max(la.norm(b),1e-30))
def check(name,a,b):
    v=rel(a,b);tests.append(dict(name=name,normalized_residual=v,passed=v<=TOL))
    assert v<=TOL,(name,v)

frame,audit,saved=sources();gain=np.asarray(saved['Full15']['gain'])
rng=np.random.default_rng(20260916)
zs=[np.exp(2j*np.pi*f*H) for f in [0.7,3,9,20]]+[.98+.07j]
for d in [1,2]:
    F=full_model(d,frame,audit,gain);B=F.R.T
    check(f'd{d}_zero_delay_C',F.C0+F.Uc@F.R,F.C+B@gain[:,2:]@F.R)
    check(f'd{d}_zero_delay_K',F.K0+F.Uk@F.R,F.K+B@gain[:,:2]@F.R)
    for k in ['M','C','K']:check(f'd{d}_original_{k}',getattr(F,k),frame[k])
    check(f'd{d}_zero_delay_output',F.Y0+F.Yd,F.Yn)
    if d==2:
        # Independent re-expression of the previous physical-coordinate Full15.
        old=saved['Full15'];oldS=old['S'];oldC0=old['C']-old['Cp']@oldS.T@oldS
        oldK0=old['K']-old['Kp']@oldS.T@oldS
        for k,new,oldv in [('C0',F.C0,oldC0),('K0',F.K0,oldK0),
          ('Uc',F.Uc,old['Cp']@oldS.T+oldS.T@gain[:,2:]),
          ('Uk',F.Uk,old['Kp']@oldS.T+oldS.T@gain[:,:2])]:check('d2_existing_Full15_'+k,new,oldv)
    all_count=9 if d==1 else 10
    TG,*_=cb_basis(frame,d,0);G=project(F,TG)
    counts=[0,3,all_count]
    for nm in counts:
        T,r,c,lam=cb_basis(frame,d,nm);R=project(F,T);name=f'd{d}_m{nm}'
        models.append(dict(division=d,internal_modes=nm,order=R.n,retained=(r+1).tolist(),
            actuation=(np.where(np.any(F.R,axis=0))[0]+1).tolist(),
            basis_condition=float(np.linalg.cond(T)),projected_mass_min_eigenvalue=float(la.eigvalsh(R.M)[0])))
        la.cholesky(R.M)
        check(name+'_CR_algorithm_mass',algorithm_mass(R),T.T@algorithm_mass(F)@T)
        check(name+'_delayed_K_factor',R.Uk@R.R,T.T@(F.Uk@F.R)@T)
        check(name+'_delayed_C_factor',R.Uc@R.R,T.T@(F.Uc@F.R)@T)
        check(name+'_input',R.f,T.T@F.f)
        if nm==0:
            for k in R.__dataclass_fields__:check(name+'_CB0_G_'+k,getattr(R,k),getattr(G,k))
        # The earlier shortcut uses a diagonal selector on reduced columns.
        # Here the retained actuator coordinates identify that shortcut solely
        # to measure why it changes the model; it is never used in R.
        E=F.R.T@F.R;ER=R.R.T@R.R
        p=np.array([1,2,3,6,7,8] if d==1 else [1,2,3,6,7,8,11,12,13])-1
        select=np.eye(15)[p];Kp=select.T@audit[f'div{d}_K_P']@select
        shortcut=T.T@Kp@T@ER
        correct=T.T@Kp@E@T
        negative.append(dict(division=d,internal_modes=nm,
            structural_delayed_K_shortcut_relative_difference=rel(shortcut,correct)))
        for n in [0,1,4,5]:
            Af,bf=augmented(F,n);Ar,br=augmented(R,n)
            hist=rng.standard_normal((n+2,R.n));force=.137
            state=np.r_[hist[0],hist[1],*[R.R@hist[i] for i in range(2,n+2)]]
            v=(hist[0]-hist[1])/H;vd=(hist[n]-hist[n+1])/H
            acc=la.solve(algorithm_mass(R),R.f*force-R.C0@v-R.K0@hist[0]-R.Uc@R.R@vd-R.Uk@R.R@hist[n])
            qnext=2*hist[0]-hist[1]+H*H*acc
            check(name+f'_n{n}_one_step', (Ar@state+br*force)[:R.n],qnext)
            for j,z in enumerate(zs):
                Zf=characteristic(F,z,n);Zr=characteristic(R,z,n)
                check(name+f'_n{n}_z{j}_Z_projection',Zr,T.T@Zf@T)
                check(name+f'_n{n}_z{j}_Y_projection',physical_output(R,z,n),physical_output(F,z,n)@T)
                s=(-.3+2j*np.pi*[.7,3,9,20,7][j])
                check(name+f'_n{n}_z{j}_continuous_projection',continuous(R,s,n*H),T.T@continuous(F,s,n*H)@T)
                q=rng.standard_normal(R.n)+1j*rng.standard_normal(R.n)
                eigenstate=np.r_[q,q/z,*[R.R@q/z**i for i in range(2,n+2)]]
                residual=(z*np.eye(len(Ar))-Ar)@eigenstate
                expected=np.r_[H*H*la.solve(algorithm_mass(R),Zr@q),np.zeros(len(Ar)-R.n)]
                check(name+f'_n{n}_z{j}_characteristic_state',residual,expected)
                if nm==all_count:
                    xf=la.solve(Zf,F.f);qr=la.solve(Zr,R.f)
                    check(name+f'_n{n}_z{j}_full_space_output',physical_output(R,z,n)@qr,physical_output(F,z,n)@xf)
                    check(name+f'_n{n}_z{j}_full_space_command',T@qr,xf)
            if nm==all_count:
                P=la.block_diag(T,T,np.eye(2*n)) if n else la.block_diag(T,T)
                check(name+f'_n{n}_state_similarity',Af@P,P@Ar)
                check(name+f'_n{n}_state_input',bf,P@br)
        export[name+'_T']=T
    export.update({f'd{d}_{k}':getattr(F,k) for k in F.__dataclass_fields__})
    # A distinct candidate preserves local substructuring and all shared DOFs.
    mode_pairs=[(0,0),(1,1),(3,1),(5,1)] if d==1 else [(0,0),(1,1),(2,2),(3,3)]
    for nn,np_ in mode_pairs:
        T,assembled,gaps,info=interface_basis(frame,audit,d,nn,np_)
        tag=f'interface_d{d}_N{nn}_P{np_}';R=project(F,T)
        interface_models.append(info);la.cholesky(R.M)
        check(tag+'_compatibility',gaps,np.zeros_like(gaps))
        for k in ['M','C','K']:check(tag+'_local_assembly_'+k,assembled[k],T.T@getattr(F,k)@T)
        if nn==np_==0:
            retained=np.array(info['retained_global'])-1;internal=[i for i in range(15) if i not in retained]
            G=np.zeros_like(T);G[retained]=np.eye(len(retained))
            G[internal]=-la.solve(F.K[np.ix_(internal,internal)],F.K[np.ix_(internal,retained)])
            check(tag+'_standard_global_G9',T,G)
        for nsteps in [0,1,4,5]:
            for j,z in enumerate(zs):
                Zf=characteristic(F,z,nsteps);Zr=characteristic(R,z,nsteps)
                check(tag+f'_n{nsteps}_z{j}_Z_projection',Zr,T.T@Zf@T)
                check(tag+f'_n{nsteps}_z{j}_Y_projection',physical_output(R,z,nsteps),physical_output(F,z,nsteps)@T)
                if R.n==15:
                    check(tag+f'_n{nsteps}_z{j}_full_recovery',T@la.solve(Zr,R.f),la.solve(Zf,F.f))
            if R.n==15:
                Af,bf=augmented(F,nsteps);Ar,br=augmented(R,nsteps)
                P=la.block_diag(T,T,np.eye(2*nsteps)) if nsteps else la.block_diag(T,T)
                check(tag+f'_n{nsteps}_state_similarity',Af@P,P@Ar)
        export[tag+'_T']=T
export['gain']=gain;export['h']=H
savemat(RES/'operators.mat',export,do_compression=True,oned_as='column')
result=dict(status='PASS',tests=len(tests),tolerance=TOL,
    max_normalized_residual=max(t['normalized_residual'] for t in tests),
    new_forced_time_histories=0,new_pole_or_boundary_scans=0,
    scope='global-basis and fully coordinated component-basis candidates; two divisions, zero/partial/all modes, equal delays 0/1/4/5 steps',
    checks=tests)
(RES/'validation_python.json').write_text(json.dumps(result,indent=2),'utf-8')
(RES/'model_summary.json').write_text(json.dumps(dict(models=models,interface_models=interface_models,negative_controls=negative,
    fixed_test_gain=gain.tolist(),gain_note='Copied from the prior verified Division II Full15; used as a fixed algebraic test parameter in both divisions, not a validated Division I control design.'),indent=2),'utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='checks'},ensure_ascii=False))
print('SHORTCUT_DIAGNOSTIC',negative)
