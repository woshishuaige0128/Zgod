"""Algebraic audit and reuse of frozen histories; no time integration."""
from pathlib import Path
import csv,json,hashlib
import numpy as np
from scipy import linalg as la
from scipy.io import loadmat,savemat

OUT=Path(__file__).resolve().parents[1];ROOT=OUT.parents[1]
C1=ROOT/'cases/case1_v1_standard_guyan_20260916'
C2=ROOT/'cases/case2_v1_divisionII_delays_20260916'
SRC=OUT/'sources';RES=OUT/'results';TOL=1e-10
checks=[];findings={};matrices={}
def rel(a,b):return float(la.norm(a-b)/max(la.norm(b),1e-30))
def test(name,value,tol=TOL):
    value=float(value);checks.append(dict(name=name,value=value,tolerance=tol,passed=value<=tol))
    assert value<=tol,(name,value,tol)
def dump(name,value): (RES/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n','utf-8')
def basis(K,M,r,count):
    r=list(r);c=[i for i in range(len(K)) if i not in r]
    psi=-la.solve(K[np.ix_(c,c)],K[np.ix_(c,r)])
    t=np.zeros((len(K),len(r)+count));t[r,:len(r)]=np.eye(len(r));t[c,:len(r)]=psi
    if count:
        w,v=la.eigh(K[np.ix_(c,c)],M[np.ix_(c,c)])
        t[np.ix_(c,range(len(r),len(r)+count))]=v[:,:count]
    return t
def complete_coordinates(K,r):
    r=list(r);c=[i for i in range(len(K)) if i not in r]
    t=np.zeros_like(K);t[r,:len(r)]=np.eye(len(r));t[c,:len(r)]=-la.solve(K[np.ix_(c,c)],K[np.ix_(c,r)])
    t[np.ix_(c,range(len(r),len(K)))]=np.eye(len(c))
    return t

bundle=loadmat(SRC/'full_frame/calculation.mat',simplify_cells=True)['bundle']
old=loadmat(SRC/'legacy/calculation.mat',simplify_cells=True)['bundle']
frame=bundle['frame'];gamma=np.zeros(15);gamma[[0,5,10]]=1
delay=loadmat(SRC/'delayed/model_and_cases.mat',simplify_cells=True)
full=[]
for d,(m,o) in enumerate(zip(bundle['models'],old['models']),1):
    order=np.asarray(m['order'],int)-1;r=np.asarray(m['master'],int)-1
    t=basis(frame['K'],frame['M'],r,0);a=basis(frame['K'],frame['M'],r,15-len(r));ai=la.inv(a)
    test(f'full_div{d}_G_basis',rel(t[order],m['T']))
    z=basis(frame['K'],frame['M'],r,0)
    for k in ['M','C','K']:
        test(f'full_div{d}_{k}_standard_projection',rel(t.T@frame[k]@t,m[k+'g']))
        test(f'full_div{d}_{k}_CB0_is_G',rel(z.T@frame[k]@z,t.T@frame[k]@t))
        test(f'full_div{d}_{k}_CB_all_recovers_full15',rel(ai.T@(a.T@frame[k]@a)@ai,frame[k]))
        test(f'full_div{d}_{k}_CB_unchanged',rel(m[k+'cb'],o[k+'cb']))
    for freq in [0.,3.,9.,20.]:
        s=2j*np.pi*freq;Z=s*s*frame['M']+s*frame['C']+frame['K'];force=frame['M']@gamma
        test(f'full_div{d}_all_basis_resolvent_{freq:g}Hz',rel(a@la.solve(a.T@Z@a,a.T@force),la.solve(Z,force)))
    test(f'full_div{d}_load_projection',rel(m['T'].T@np.asarray(m['Mf']).reshape(-1),t.T@frame['M']@gamma))
    full.append(dict(division=d,retained=(r+1).tolist(),guyan_order=len(r),cb3_order=len(r)+3,full_order=15,
                     legacy_to_standard={k:rel(m[k+'g'],o[k+'g']) for k in ['M','C','K']},all_internal_basis_rank=int(np.linalg.matrix_rank(a))))
findings['full_frame']=full

def local_parts(d):
    # Match the manuscript geometry and frozen lumped-mass convention.
    E=frame['E'];L=frame['height_mm']/1000;lb=frame['span_m']
    kc=E*frame['inertia_column']/L**3*np.array([[12,-6*L,-12,-6*L],[-6*L,4*L*L,6*L,2*L*L],[-12,6*L,12,6*L],[-6*L,2*L*L,6*L,4*L*L]])
    kb=E*frame['inertia_beam']/lb*np.array([[4,2],[2,4]])
    kp=np.zeros((15,15));kn=kp.copy()
    def add(k,ids,e):
        sel=[i for i,x in enumerate(ids) if x>=0];dst=[ids[i] for i in sel];k[np.ix_(dst,dst)]+=e[np.ix_(sel,sel)]
    nfloor=2 if d==1 else 3
    for f in range(3):
        for col in range(4):
            ids=([-1,-1] if f==0 else [5*(f-1),5*(f-1)+1+col])+[5*f,5*f+1+col]
            add(kp if f<nfloor and col<2 else kn,ids,kc)
        for bay in range(3):add(kp if f<nfloor and bay==0 else kn,[5*f+1+bay,5*f+2+bay],kb)
    p=np.array([1,2,3,6,7,8] if d==1 else [1,2,3,6,7,8,11,12,13])-1
    n=np.array([1,3,4,5,6,7,8,9,10,11,12,13,14,15] if d==1 else [1,3,4,5,6,8,9,10,11,13,14,15])-1
    act=np.array([1,6] if d==1 else [1,11])-1
    nm=np.array([1,6,11,4,9,14] if d==1 else [1,11,6,4,9,14])-1
    mb=frame['rho_model']*frame['area_beam']*lb;mc=frame['rho_model']*frame['area_column']*L
    mp=np.zeros((15,15));mp[p,p]=np.tile([mb+2*mc,mb/2*lb**2/12+mc*L**2/12,mb/2*lb**2/12+mc*L**2/12],nfloor)
    mn=frame['M']-mp;alpha,beta=frame['rayleigh']
    P=dict(M=mp[np.ix_(p,p)],K=kp[np.ix_(p,p)],C=(alpha*mp+beta*kp)[np.ix_(p,p)])
    N=dict(M=mn[np.ix_(n,n)],K=kn[np.ix_(n,n)],C=(alpha*mn+beta*kn)[np.ix_(n,n)])
    return p,n,act,nm,P,N

local=[]
for d in [1,2]:
    p,n,act,nm,P,N=local_parts(d);nn=len(n);np_=len(p);extras=[x for x in p if x not in act];nd=nn+len(extras)
    rn=np.c_[np.eye(nn),np.zeros((nn,len(extras)))];rp=np.zeros((np_,nd))
    for i,x in enumerate(p):rp[i,list(n).index(x) if x in act else nn+extras.index(x)]=1
    ids=np.r_[n,extras];J=np.eye(15)[ids]
    overlap=sorted(set(p)&set(n));missing=[x for x in overlap if x not in act]
    G=np.array([rp[list(p).index(x)]-rn[list(n).index(x)] for x in missing])
    test(f'local_div{d}_constraint_rank',abs(np.linalg.matrix_rank(G)-len(missing)),0)
    test(f'local_div{d}_all_join_rank',abs(np.linalg.matrix_rank(J)-15),0)
    test(f'local_div{d}_joined_compatibility',la.norm(G@J))
    U={k:rn.T@N[k]@rn+rp.T@P[k]@rp for k in ['M','C','K']}
    for k in ['M','C','K']:test(f'local_div{d}_{k}_full_join_recovers_full15',rel(J.T@U[k]@J,frame[k]))
    force=rn.T@N['M']@gamma[n]+rp.T@P['M']@gamma[p]
    test(f'local_div{d}_force_join_recovers_full15',rel(J.T@force,frame['M']@gamma))
    irn=[list(n).index(x) for x in nm];irp=[list(p).index(x) for x in act]
    tn=basis(N['K'],N['M'],irn,0);tp=basis(P['K'],P['M'],irp,0)
    en=np.eye(6);ep=np.c_[np.eye(2),np.zeros((2,4))]
    RGn=tn@en;RGp=tp@ep
    for k in ['M','C','K']:
        g=RGn.T@N[k]@RGn+RGp.T@P[k]@RGp
        cb0=tn.T@N[k]@tn+ep.T@(tp.T@P[k]@tp)@ep
        test(f'local_div{d}_{k}_CB0_is_G',rel(cb0,g))
        if d==2:test(f'local_div2_{k}_matches_saved_Guyan',rel(g,delay['Guyan6'][k]))
    # Complete interior coordinate basis proves full-space recovery even where
    # a positive-definite mass-normalized eigenbasis is unavailable.
    an=complete_coordinates(N['K'],irn);ap=complete_coordinates(P['K'],irp)
    en=np.c_[np.eye(nn),np.zeros((nn,np_-2))];ep=np.zeros((np_,nd));ep[:2,:2]=np.eye(2);ep[2:,nn:]=np.eye(np_-2)
    Rn=an@en;Rp=ap@ep;W=np.zeros((nd,nd));W[:nn]=Rn
    for x in extras:W[nn+extras.index(x)]=Rp[list(p).index(x)]
    Wi=la.inv(W)
    for k in ['M','C','K']:
        reduced=Rn.T@N[k]@Rn+Rp.T@P[k]@Rp
        test(f'local_div{d}_{k}_complete_internal_recovers_U{nd}',rel(Wi.T@reduced@Wi,U[k]))
    ic=[i for i in range(nn) if i not in irn]
    ew=la.eigvals(N['K'][np.ix_(ic,ic)],N['M'][np.ix_(ic,ic)])
    masszero=[int(n[i]+1) for i in range(nn) if abs(N['M'][i,i])<1e-12]
    local.append(dict(division=d,physical=(p+1).tolist(),numerical=(n+1).tolist(),actuated=(act+1).tolist(),common=(np.array(overlap)+1).tolist(),uncoordinated=(np.array(missing)+1).tolist(),uncondensed_order=nd,required_extra_constraints=len(missing),guyan_order=6,nominal_cb3_order=12,mass_rank=int(np.linalg.matrix_rank(U['M'])),zero_mass_numerical_coordinates=masszero,finite_fixed_interface_modes=int(np.isfinite(ew).sum()),infinite_fixed_interface_modes=int((~np.isfinite(ew)).sum()),G_recovery_gap_rank=int(np.linalg.matrix_rank(np.array([RGp[list(p).index(x)]-RGn[list(n).index(x)] for x in missing])))))
    matrices.update({f'div{d}_{k}':v for k,v in dict(J=J,G=G,M_U=U['M'],C_U=U['C'],K_U=U['K'],complete_basis=W,M_N=N['M'],K_N=N['K'],M_P=P['M'],K_P=P['K'],C_P=P['C']).items()})
    if d==2:
        # Recreate the archived, mass-normalized all-mode basis independently.
        an=basis(N['K'],N['M'],irn,6);ap=basis(P['K'],P['M'],irp,7)
        Rn=an@en;Rp=ap@ep;W[:nn]=Rn
        for x in extras:W[nn+extras.index(x)]=Rp[list(p).index(x)]
        for k in ['M','C','K']:
            test(f'local_div2_{k}_CB_all_matches_saved19',rel(Rn.T@N[k]@Rn+Rp.T@P[k]@Rp,delay['Uncondensed19'][k]))
        sn=np.eye(nd)[[list(n).index(x) for x in act]];sq=np.eye(nd)[:2];En=sn.T@sn;Eq=sq.T@sq
        matrices.update(delay_W=W.copy(),delay_En=En,delay_Eq=Eq,delay_Cp_natural=rp.T@P['C']@rp,delay_Kp_natural=rp.T@P['K']@rp)
        delaypaths=[]
        for steps in [0,4]:
            z=np.exp(2j*np.pi*9/1024);dn=np.eye(nd)+(z**(-steps)-1)*En;dq=np.eye(nd)+(z**(-steps)-1)*Eq
            item={'delay_steps':steps,'frequency_hz':9.,'recovery_commutator':rel(W@dq,dn@W)}
            for k in ['C','K']:
                cp=rp.T@P[k]@rp
                left=W.T@cp@W@dq;right=W.T@cp@dn@W
                item[k+'_delay_projection_difference']=rel(left,right)
                if steps==0:test(f'zero_delay_projection_commutes_{k}',rel(left,right))
            delaypaths.append(item)
        findings['delay_operator_audit']=delaypaths
findings['local_assembly']=local

metrics=[];decomp_max=0.;energy_max=0.;metric_max=0.
base=np.load(C2/'results/n00_00_responses.npz')
saved=list(csv.DictReader((C2/'results/response_metrics.csv').open(encoding='utf-8')))
for steps in range(6):
    tag=f'n{steps:02d}_{steps:02d}';data=np.load(C2/'results'/f'{tag}_responses.npz');t=data['time_s'];duration=t[-1]-t[0]
    def mean(a):return np.trapezoid(a,t,axis=0)/duration
    for ex in ['eq','chirp']:
        passive=np.genfromtxt(C1/'results/standard'/f'division2_{ex}/response.csv',delimiter=',',names=True)
        test(f'{tag}_{ex}_time_alignment',rel(passive['time_s'],t))
        yoriginal=np.column_stack([passive[f'floor{i}_full_mm'] for i in [1,2,3]])
        f=data[f'{ex}_Full15_physical_mm'];u=data[f'{ex}_Uncondensed19_physical_mm'];f0=base[f'{ex}_Full15_physical_mm']
        scale=np.ptp(yoriginal,axis=0)
        for model in ['Guyan6','CB12']:
            y=data[f'{ex}_{model}_physical_mm'];terms=[y-u,u-f,f-f0,f0-yoriginal];total=y-yoriginal
            closure=rel(sum(terms),total);decomp_max=max(decomp_max,closure);test(f'{tag}_{ex}_{model}_signed_decomposition',closure)
            squares=sum(mean(e*e) for e in terms);cross=sum(2*mean(terms[i]*terms[j]) for i in range(4) for j in range(i+1,4));energy=rel(squares+cross,mean(total*total));energy_max=max(energy_max,energy);test(f'{tag}_{ex}_{model}_energy_with_cross_terms',energy)
            nrmse=100*np.sqrt(mean((y-u)**2))/np.ptp(u,axis=0)
            for floor in range(3):
                oldrow=next(a for a in saved if a['key']==tag and a['input']==ex and a['model']==model and int(a['floor'])==floor+1)
                delta=abs(nrmse[floor]-float(oldrow['nrmse_same_interface_percent']));metric_max=max(metric_max,delta)
                row=dict(delay_ms=steps/1024*1000,input=ex,model=model,floor=floor+1,stability=oldrow['stability'],total_to_original_passive_nrmse_percent=float(100*np.sqrt(mean(total*total))[floor]/scale[floor]),cross_term_mm2=float(cross[floor]))
                for label,e in zip(['reduction','reference_model','delay','control_and_integrator'],terms):row[label+'_fixed_scale_percent']=float(100*np.sqrt(mean(e*e))[floor]/scale[floor])
                row['same_interface_nrmse_percent']=float(nrmse[floor]);row['same_delay_full15_nrmse_percent']=float(oldrow['nrmse_full15_same_delay_percent']);metrics.append(row)
test('existing_metrics_recomputed_max_percentage_point_error',metric_max)
with (RES/'error_decomposition.csv').open('w',newline='',encoding='utf-8-sig') as f:
    w=csv.DictWriter(f,fieldnames=list(metrics[0]));w.writeheader();w.writerows(metrics)
findings['decomposition']=dict(rows=len(metrics),max_response_identity_residual=decomp_max,max_squared_energy_identity_residual=energy_max,max_existing_metric_percentage_point_error=metric_max,terms=['reduction to archived all-mode19','reference-model difference: interface and delayed recovery convention','common delay within Full15 CR controlled loop','combined control/integrator change from original passive RK4 Full15'],new_time_integrations=0)
for k in ['M','C','K']:test('Full15_saved_'+k,rel(delay['Full15'][k],frame[k]))
dump('findings.json',findings);dump('algebra_checks.json',dict(status='PASS',checks=len(checks),max_normalized_residual=max(x['value'] for x in checks),tolerance=TOL,tests=checks,new_time_integrations=0))
savemat(RES/'audit_matrices.mat',matrices,do_compression=True)
print(json.dumps(dict(status='PASS',checks=len(checks),local=local,delay_operator_audit=findings['delay_operator_audit'],decomposition=findings['decomposition']),ensure_ascii=False))
