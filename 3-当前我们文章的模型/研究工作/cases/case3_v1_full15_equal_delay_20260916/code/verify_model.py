"""Independent algebra and finite-record verification; artifacts go to --out."""
import argparse,json,hashlib
from pathlib import Path
import numpy as np
from scipy import linalg as la
from scipy.io import savemat
from full15_model import *

def main(out):
    out.mkdir(parents=True,exist_ok=True);checks=[];exports={};rng=np.random.default_rng(260916)
    def check(name,a,b,scale=None,tol=1e-10):
        a=np.asarray(a);b=np.asarray(b)
        den=max(float(la.norm(b.ravel())),1e-300) if scale is None else max(float(scale),1e-300)
        value=float(la.norm((a-b).ravel())/den)
        checks.append(dict(name=name,residual=value,tolerance=tol,passed=bool(value<=tol)))
    def predicate(name,ok):checks.append(dict(name=name,residual=0 if ok else 1,tolerance=0,passed=bool(ok)))
    frame,inputs,_,gain=load_sources();alpha,beta=np.asarray(frame['rayleigh']).ravel()
    for d in [1,2]:
        F=full_model(d);ridx=RETAINED[d];cidx=np.array([i for i in range(15) if i not in ridx]);nr=len(ridx)
        # Independently solve a permuted block problem and expand its mass, load,
        # and stiffness formulas. This path never calls cb_basis or guyan_basis.
        p=np.r_[ridx,cidx];M=F.M[np.ix_(p,p)];K=F.K[np.ix_(p,p)]
        Krr,Krc,Kcr,Kcc=K[:nr,:nr],K[:nr,nr:],K[nr:,:nr],K[nr:,nr:]
        L=-np.linalg.solve(Kcc,Kcr);Vind=np.vstack([np.eye(nr),L]);Tind=np.zeros((15,nr));Tind[p]=Vind
        Mg=M[:nr,:nr]+M[:nr,nr:]@L+L.T@M[nr:,:nr]+L.T@M[nr:,nr:]@L
        Kg=Krr+Krc@L;fg=F.f[ridx]+L.T@F.f[cidx]
        G=family(d)['Guyan'];check(f'd{d}_independent_G_basis',G.T,Tind)
        for key,ref in [('M',Mg),('K',Kg),('C',alpha*Mg+beta*Kg),('f',fg)]:check(f'd{d}_independent_G_{key}',getattr(G,key),ref)
        W,_=cb_basis(F,len(cidx));allR=project(F,W,'CBall');lamF=la.eigvalsh(F.K,F.M);last=None
        for m in range(len(cidx)+1):
            T,lam=cb_basis(F,m);R=project(F,T,f'CB{m}');vals=la.eigvalsh(R.K,R.M)
            predicate(f'd{d}_m{m}_Ritz_above_full',bool(np.all(vals>=lamF[:len(vals)]-1e-10*np.maximum(abs(vals),abs(lamF[:len(vals)])))))
            if last is not None:predicate(f'd{d}_m{m}_nested_Ritz',bool(np.all(vals[:len(last)]<=last+1e-10*np.maximum(abs(vals[:len(last)]),abs(last)))))
            last=vals
            if m==len(cidx):check(f'd{d}_full_modal_spectrum',vals,lamF)
        xs=la.solve(F.K,F.f);qg=la.solve(G.K,G.f);estat=G.Yn@qg-F.Yn@xs
        expected=np.zeros(15);expected[cidx]=-la.solve(Kcc,F.f[cidx])
        check(f'd{d}_static_internal_load_output',estat,F.Yn@expected,scale=la.norm(F.Yn@xs))
        predicate(f'd{d}_internal_load_present',bool((la.norm(F.f[cidx])>0)==(d==2)))
        for control in [False,True]:
            F=full_model(d,gain if control else None);mods=family(d,gain=gain if control else None)
            allR=project(F,W,'CBall')
            for n in [0,1,4,5]:
                prefix=f'd{d}_g{int(control)}_n{n}'
                AF,bF=state_space(F,n);AR,bR=state_space(allR,n)
                P=la.block_diag(W,W,np.eye(2*n)) if n else la.block_diag(W,W)
                check(prefix+'_full_state_similarity',AF@P,P@AR)
                check(prefix+'_full_input_similarity',bF,P@bR)
                for kind in ['numerical','physical']:check(prefix+'_full_output_'+kind,state_output(F,n,kind)@P,state_output(allR,n,kind))
                for name,R in mods.items():
                    tag=prefix+'_'+name;A,b=state_space(R,n);Ah,bh,J=full_history(R,n)
                    check(tag+'_history_intertwining',A@J,J@Ah)
                    check(tag+'_history_input',b,J@bh)
                    predicate(tag+'_history_map_full_row_rank',np.linalg.matrix_rank(J)==len(A))
                    history=rng.normal(size=(n+2,R.order))*1e-5
                    initial=J@history.ravel();u=rng.normal(size=64)
                    y,end=simulate(R,n,u,x0=initial)
                    independent=independent_recurrence(R,n,u,history=history)
                    check(tag+'_independent_force_recurrence',y,independent,tol=1e-9)
                    O=np.vstack([state_output(R,n,'numerical'),state_output(R,n,'physical')])
                    Oh=np.zeros((6,len(Ah)));Oh[:3,:R.order]=R.Yn;Oh[3:,:R.order]=R.Y0
                    Oh[3:,n*R.order:(n+1)*R.order]+=R.Jd@R.S
                    check(tag+'_history_output',O@J,Oh)
                    # Explicit matrix powers and finite convolution; includes
                    # nonzero history and the last finite sample.
                    yp=np.array([O@np.linalg.matrix_power(A,k)@initial+sum((O@np.linalg.matrix_power(A,k-1-j)@b*u[j] for j in range(k)),np.zeros(6)) for k in range(65)])
                    check(tag+'_finite_convolution_with_history',y,yp,tol=1e-9)
                    y1,x1=simulate(R,n,u[:32],x0=initial);y2,_=simulate(R,n,u[32:],x0=x1)
                    check(tag+'_unbroken_history',np.vstack([y1,y2[1:]]),y)
                    for z in [0.9+0.25j,np.exp(2j*np.pi*3*H),np.exp(2j*np.pi*9*H)]:
                        Z=characteristic(R,z,n);Zf=characteristic(F,z,n)
                        check(tag+f'_project_Z_{z}',Z,R.T.T@Zf@R.T)
                        # Transfer of a sampled exponential from state equation.
                        qs=la.solve(z*np.eye(len(A))-A,b)
                        for kind in ['physical','numerical']:
                            Y=R.Yn if kind=='numerical' else R.Y0+z**(-n)*R.Jd@R.S
                            check(tag+f'_state_transfer_{kind}_{z}',state_output(R,n,kind)@qs,Y@la.solve(Z,R.f))
                        # Scale-free determinant identities using complex logs.
                        def logdet(X):
                            sg,logabs=np.linalg.slogdet(X);return logabs+1j*np.angle(sg)
                        delta=logdet(z*np.eye(len(A))-A)-(2*R.order*np.log(H)-logdet(algorithm_mass(R))+(R.order+2*n)*np.log(z)+logdet(Z))
                        check(tag+f'_determinant_{z}',np.exp(delta),1.)
                        delta2=logdet(z*np.eye(len(Ah))-Ah)-((R.order-2)*n*np.log(z)+logdet(z*np.eye(len(A))-A))
                        check(tag+f'_redundant_zero_roots_{z}',np.exp(delta2),1.)
                    if not control:
                        z=.9+.3j;s=2/H*(z-1)/(z+1)
                        if n==0:check(tag+'_passive_bilinear_identity',characteristic(R,z,0),(z+1)**2/(4*z)*continuous(R,s,0))
                    key=tag.replace('Full15','Full')
                    exports[key+'_A']=A;exports[key+'_b']=b;exports[key+'_O']=O
                    exports[key+'_M']=R.M;exports[key+'_C']=R.C;exports[key+'_K']=R.K
                    for k in ['C0','K0','Uc','Uk','S','f','Yn','Y0','Jd']:exports[key+'_'+k]=getattr(R,k)
                    exports[key+'_u']=u;exports[key+'_history']=history;exports[key+'_y']=y;exports[key+'_n']=n
            # Continuous omitted-block identities include dynamic load and output.
            for m in [0,3]:
                T,_=cb_basis(F,m);R=project(F,T,f'CB{m}');r=R.order;Q=W[:,r:]
                for s in [0,2+19j,-.5+37j]:
                    tau=4*H;Z=continuous(F,s,tau);Zr=continuous(R,s,tau)
                    Zro=T.T@Z@Q;Zor=Q.T@Z@T;Zoo=Q.T@Z@Q
                    omega2=np.diag(Q.T@F.K@Q);fo=Q.T@F.f;fr=T.T@F.f
                    check(f'd{d}_g{control}_m{m}_Zoo_{s}',Zoo,s*s*np.eye(len(fo))+s*(alpha*np.eye(len(fo))+beta*np.diag(omega2))+np.diag(omega2))
                    # At s=0 the exact target is zero. Normalize its cancellation
                    # by the multiplying physical operators, not by 1 SI unit.
                    zro_scale=la.norm(T)*la.norm(F.K)*la.norm(Q) if s==0 else la.norm(Zro)
                    check(f'd{d}_g{control}_m{m}_Zro_{s}',Zro,(s*s+alpha*s)*(T.T@F.M@Q),scale=zro_scale)
                    # Whole modal-coordinate solve is a separate path from Schur.
                    coordinates=la.solve(W.T@Z@W,W.T@F.f);pf=coordinates[r:]
                    Y=F.Y0+np.exp(-s*tau)*F.Jd@F.S;Yr=Y@T;Yo=Y@Q
                    qt=la.solve(Zr,fr);error=Yr@qt-Y@la.solve(Z,F.f)
                    check(f'd{d}_g{control}_m{m}_Schur_output_{s}',error,(Yr@la.solve(Zr,Zro)-Yo)@pf,scale=la.norm(Y@la.solve(Z,F.f)))
                    residual=F.f-Z@T@qt
                    check(f'd{d}_g{control}_m{m}_residual_output_{s}',error,-Y@la.solve(Z,residual),scale=la.norm(Y@la.solve(Z,F.f)))
        # Isolated passive discrete roots equal the Cayley image, not exp(sh).
        F=full_model(d);Ac=np.block([[np.zeros((15,15)),np.eye(15)],[-la.solve(F.M,F.K),-la.solve(F.M,F.C)]])
        expected=(1+H*la.eigvals(Ac)/2)/(1-H*la.eigvals(Ac)/2);actual=la.eigvals(state_space(F,0)[0])
        from scipy.optimize import linear_sum_assignment
        rows,cols=linear_sum_assignment(abs(actual[:,None]-expected[None,:]))
        check(f'd{d}_passive_root_bilinear',actual[rows],expected[cols])
    for bad in [-1,1.5,True]:
        try:state_space(full_model(1),bad);ok=False
        except ValueError:ok=True
        predicate(f'invalid_delay_{bad}',ok)
    zero_metrics=error_metrics(np.ones((4,3)),np.zeros((4,3)))
    predicate('zero_reference_relative_metrics_undefined',zero_metrics['relative_l2_pct']==[None]*3 and zero_metrics['nrmse_range_pct']==[None]*3)
    predicate('zero_reference_absolute_error_retained',zero_metrics['max_abs_error']==[1.]*3)
    savemat(out/'crosscheck_inputs.mat',exports,oned_as='column',do_compression=True)
    summary=dict(status='PASS' if all(x['passed'] for x in checks) else 'FAIL',count=len(checks),
        maximum_residual=max(x['residual'] for x in checks),checks=checks,
        scope='Algebra and 64-step verification, no selected research cases or stability scan',
        code_sha256=hashlib.sha256(Path(__file__).with_name('full15_model.py').read_bytes()).hexdigest())
    (out/'model_validation.json').write_text(json.dumps(summary,indent=2),'utf-8')
    failed=[x for x in checks if not x['passed']]
    print(json.dumps(dict(status=summary['status'],count=len(checks),maximum=summary['maximum_residual'],failures=failed[:20]),ensure_ascii=False))
    if failed:raise SystemExit(1)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True,type=Path);main(parser.parse_args().out)
