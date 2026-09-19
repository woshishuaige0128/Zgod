"""Validate construction, survey a bounded delay grid and select plot cases."""
import json,csv,hashlib
import numpy as np
from scipy import linalg as la
from scipy.io import savemat,loadmat
from delay_model import *

def main():
    out=CASE/'results';out.mkdir(exist_ok=True)
    models,parts,checks=build_models();tests=[]
    def test(name,value,tolerance):
        tests.append(dict(name=name,value=float(value),tolerance=tolerance,passed=bool(value<=tolerance)))
        assert value<=tolerance,(name,value,tolerance)
    for key in ['assembled_M','assembled_C','assembled_K','care_residual']:test(key,checks[key],1e-10)
    for m in models.values():
        for k in ['M','C','K']:
            a=getattr(m,k);test(m.name+'_'+k+'_symmetry',relative(a,a.T),1e-10);la.cholesky(a)
    # Full CB bases are invertible on each local model. Compare assembled
    # matrices with an independently assembled 19-coordinate natural basis.
    idsN=list(N_MASTER)+[x for x in N_IDS if x not in N_MASTER]
    idsP=list(P_MASTER)+[x for x in P_IDS if x not in P_MASTER]
    rn=np.zeros((12,19));rp=np.zeros((9,19))
    for i,x in enumerate(N_IDS):rn[i,idsN.index(x)]=1
    for i,x in enumerate(P_IDS):rp[i,idsP.index(x) if x in P_MASTER else 12+idsP.index(x)-2]=1
    direct={k:rn.T@parts['N'][k]@rn+rp.T@parts['P'][k]@rp for k in ['M','C','K']}
    tn,_=basis(parts['N'],N_IDS,N_MASTER,6);tp,_=basis(parts['P'],P_IDS,P_MASTER,7)
    en=np.zeros((12,19));en[:,:12]=np.eye(12)
    ep=np.zeros((9,19));ep[:2,:2]=np.eye(2);ep[2:,12:]=np.eye(7)
    transform=np.zeros((19,19))
    for i,x in enumerate(N_IDS):transform[idsN.index(x)]=tn[i]@en
    for i,x in enumerate(P_IDS):
        if x not in P_MASTER:transform[12+idsP.index(x)-2]=tp[i]@ep
    for k in ['M','C','K']:test('CB_all_modes_'+k,relative(getattr(models['Uncondensed19'],k),transform.T@direct[k]@transform),1e-10)
    g0=reduced_model('CB0',parts,0,0)
    for k in ['M','C','K']:test('CB_zero_modes_'+k,relative(getattr(g0,k),getattr(models['Guyan6'],k)),1e-12)
    grid=[]
    for n1 in range(9):
        for n2 in range(9):
            r={'n1':n1,'n2':n2,'tau1_ms':n1*DT*1000,'tau2_ms':n2*DT*1000}
            for name,m in models.items():r['rho_'+name]=float(max(abs(poles(m,(n1,n2)))))
            grid.append(r)
    with (out/'delay_survey.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(grid[0]));w.writeheader();w.writerows(grid)
    selected=[(0,0),(1,1),(2,2),(3,3),(4,4),(0,4),(4,0),(1,3),(3,1),(1,4),(4,1),(2,4),(4,2),(3,4),(4,3),(5,5)]
    # Also display the closest jointly stable point in this bounded grid.
    stable=[r for r in grid if max(r['rho_'+x] for x in models)<1-1e-8]
    near=max(stable,key=lambda r:max(r['rho_'+x] for x in models))
    if (near['n1'],near['n2']) not in selected:selected.append((near['n1'],near['n2']))
    discord=[r for r in grid if r['rho_Guyan6']>1+1e-8 and max(r['rho_'+x] for x in ['Full15','Uncondensed19','CB12'])<1-1e-8]
    if discord:
        extra=min(discord,key=lambda r:r['n1']+r['n2'])
        if (extra['n1'],extra['n2']) not in selected:selected.append((extra['n1'],extra['n2']))
    rows=[];payload={};t,inputs=load_inputs()
    for name,m in models.items():
        payload[name]={k:getattr(m,k) for k in ['M','C','K','Cp','Kp','force','S','Yp','Yn','gain']}
    payload.update(time=t,eq=inputs['eq'],chirp=inputs['chirp'],dt=DT,delays=np.array(selected))
    for n1,n2 in selected:
        r=next(r.copy() for r in grid if (r['n1'],r['n2'])==(n1,n2))
        r['key']=f'n{n1:02d}_{n2:02d}'
        r['status']={name:('stable' if r['rho_'+name]<1-1e-8 else 'unstable' if r['rho_'+name]>1+1e-8 else 'critical') for name in models}
        rows.append(r)
        for name,m in models.items():
            w,V,A=poles(m,(n1,n2),vectors=True);ix=np.argmax(abs(w));z=w[ix];v=V[:m.n,ix]
            mass,c0,k0,cs,ks=operators(m)
            scale=(abs((z-1)**2/(z*DT**2))*la.norm(mass)+abs((z-1)/(z*DT))*la.norm(c0)+la.norm(k0)+sum(abs(z)**(-d)*(abs((z-1)/(z*DT))*la.norm(c)+la.norm(k)) for d,c,k in zip((n1,n2),cs,ks)))
            test(f'{name}_{n1}_{n2}_dominant_characteristic',la.norm(characteristic(m,z,(n1,n2))@v)/(scale*la.norm(v)),1e-9)
            test(f'{name}_{n1}_{n2}_eigen_residual',la.norm(A@V[:,ix]-z*V[:,ix])/(la.norm(A)*la.norm(V[:,ix])),1e-10)
            payload[f'{name}_{n1}_{n2}_A']=A
            payload[f'{name}_{n1}_{n2}_b']=transition(m,(n1,n2))[1]
    # Zero-delay matrix equals the CR update with total stiffness/damping
    # including the controller, but CR mass coefficient uses open matrices.
    for name,m in models.items():
        mass=m.M+DT/2*m.C+DT**2/4*m.K
        c=m.C+m.S.T@m.gain[:,2:]@m.S;k=m.K+m.S.T@m.gain[:,:2]@m.S
        expected=np.block([[2*np.eye(m.n)-la.solve(mass,DT*c+DT**2*k),-np.eye(m.n)+la.solve(mass,DT*c)],[np.eye(m.n),np.zeros((m.n,m.n))]])
        test(name+'_zero_delay_transition',relative(transition(m,(0,0))[0],expected),1e-12)
    savemat(out/'model_and_cases.mat',payload,do_compression=True)
    (out/'model_checks.json').write_text(json.dumps({'status':'PASS','model':checks,'tests':tests},indent=2),'utf-8')
    (out/'selected_delays.json').write_text(json.dumps(rows,indent=2),'utf-8')
    print('MODEL_CHECKS',len(tests),'PASS; grid',len(grid),'selected',len(rows),flush=True)
    for r in rows:print(r['key'],tuple(round(r['rho_'+x],8) for x in models),r['status'],flush=True)

if __name__=='__main__':main()
