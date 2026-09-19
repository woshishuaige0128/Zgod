"""Division II: element-consistent substructures and the manuscript CR loop.

All forces are generalized forces. SI units internally. The physical inertia
is numerical; only physical C/K columns and channel controller forces lag.
"""
from pathlib import Path
from dataclasses import dataclass
import numpy as np
from scipy import linalg as la
from scipy.io import loadmat

CASE = Path(__file__).resolve().parents[1]
DT = 1 / 1024
P_IDS = np.array([1,2,3,6,7,8,11,12,13])-1
N_IDS = np.array([1,3,4,5,6,8,9,10,11,13,14,15])-1
N_MASTER = np.array([1,11,6,4,9,14])-1
P_MASTER = np.array([1,11])-1
FLOORS = np.array([1,6,11])-1

def relative(a,b):
    return float(la.norm(a-b)/max(la.norm(b),1e-30))

def element_matrices(frame):
    """Assemble columns 0,1 plus bay 0 physically, other elements numerically."""
    E=frame['E']; L=frame['height_mm']/1000; lb=frame['span_m']
    kc=E*frame['inertia_column']/L**3*np.array([
        [12,-6*L,-12,-6*L],[-6*L,4*L**2,6*L,2*L**2],
        [-12,6*L,12,6*L],[-6*L,2*L**2,6*L,4*L**2]])
    kb=E*frame['inertia_beam']/lb*np.array([[4,2],[2,4]])
    kp=np.zeros((15,15));kn=kp.copy()
    def add(target,ids,k):
        keep=[i for i,x in enumerate(ids) if x>=0]
        dest=[ids[i] for i in keep]
        target[np.ix_(dest,dest)]+=k[np.ix_(keep,keep)]
    for floor in range(3):
        for col in range(4):
            ids=([-1,-1] if floor==0 else [5*(floor-1),5*(floor-1)+1+col])+[5*floor,5*floor+1+col]
            add(kp if col<2 else kn,ids,kc)
        for bay in range(3):
            add(kp if bay==0 else kn,[5*floor+1+bay,5*floor+2+bay],kb)
    mb=frame['rho_model']*frame['area_beam']*lb
    mc=frame['rho_model']*frame['area_column']*L
    mp=np.zeros((15,15)); mp[P_IDS,P_IDS]=np.tile([mb+2*mc,mb/2*lb**2/12+mc*L**2/12,mb/2*lb**2/12+mc*L**2/12],3)
    mn=frame['M']-mp
    alpha,beta=frame['rayleigh']
    cp=alpha*mp+beta*kp;cn=alpha*mn+beta*kn
    return {'P':dict(M=mp[np.ix_(P_IDS,P_IDS)],C=cp[np.ix_(P_IDS,P_IDS)],K=kp[np.ix_(P_IDS,P_IDS)]),
            'N':dict(M=mn[np.ix_(N_IDS,N_IDS)],C=cn[np.ix_(N_IDS,N_IDS)],K=kn[np.ix_(N_IDS,N_IDS)]),
            'global_P':dict(M=mp,C=cp,K=kp),'global_N':dict(M=mn,C=cn,K=kn)}

def basis(local,ids,master,nmodes):
    retained=[int(np.where(ids==x)[0][0]) for x in master]
    internal=[i for i in range(len(ids)) if i not in retained]
    psi=-la.solve(local['K'][np.ix_(internal,internal)],local['K'][np.ix_(internal,retained)],assume_a='pos')
    eigen,phi=la.eigh(local['K'][np.ix_(internal,internal)],local['M'][np.ix_(internal,internal)])
    T=np.zeros((len(ids),len(retained)+nmodes))
    T[retained,:len(retained)]=np.eye(len(retained));T[internal,:len(retained)]=psi
    T[internal,len(retained):]=phi[:,:nmodes]
    return T, np.sqrt(eigen)/(2*np.pi)

@dataclass
class Model:
    name: str
    M: np.ndarray
    C: np.ndarray
    K: np.ndarray
    Cp: np.ndarray
    Kp: np.ndarray
    force: np.ndarray
    S: np.ndarray
    Yp: np.ndarray
    Yn: np.ndarray
    gain: np.ndarray = None

    @property
    def n(self):return self.M.shape[0]

def reduced_model(name,parts,nmN,nmP):
    tn,_=basis(parts['N'],N_IDS,N_MASTER,nmN)
    tp,_=basis(parts['P'],P_IDS,P_MASTER,nmP)
    n=6+nmN+nmP
    en=np.zeros((6+nmN,n));en[:,:6+nmN]=np.eye(6+nmN)
    ep=np.zeros((2+nmP,n));ep[:2,:2]=np.eye(2)
    if nmP:ep[2:,6+nmN:]=np.eye(nmP)
    rn=tn@en;rp=tp@ep
    mats={k:rn.T@parts['N'][k]@rn+rp.T@parts['P'][k]@rp for k in ['M','C','K']}
    gm=np.zeros(15);gm[FLOORS]=1
    # Same positive input sign as the frozen response chain.
    f=rn.T@parts['N']['M']@gm[N_IDS]+rp.T@parts['P']['M']@gm[P_IDS]
    yp=rp[[int(np.where(P_IDS==i)[0][0]) for i in FLOORS]]
    yn=rn[[int(np.where(N_IDS==i)[0][0]) for i in FLOORS]]
    S=np.zeros((2,n));S[:,:2]=np.eye(2)
    return Model(name,**mats,Cp=rp.T@parts['P']['C']@rp,Kp=rp.T@parts['P']['K']@rp,force=f,S=S,Yp=yp,Yn=yn)

def build_models():
    f=loadmat(CASE/'sources/calculation.mat',simplify_cells=True)['bundle']['frame']
    parts=element_matrices(f)
    models={}
    S=np.zeros((2,15));S[0,0]=1;S[1,10]=1
    gamma=np.zeros(15);gamma[FLOORS]=1
    y=np.eye(15)[FLOORS]
    models['Full15']=Model('Full15',f['M'],f['C'],f['K'],parts['global_P']['C'],parts['global_P']['K'],f['M']@gamma,S,y,y)
    models['Uncondensed19']=reduced_model('Uncondensed19',parts,6,7)
    models['Guyan6']=reduced_model('Guyan6',parts,0,0)
    models['CB12']=reduced_model('CB12',parts,3,3)
    g=models['Guyan6'];ids=np.arange(g.n);master=[0,1];slave=list(range(2,g.n))
    T=np.vstack((np.eye(2),-la.solve(g.K[np.ix_(slave,slave)],g.K[np.ix_(slave,master)])))
    M=T.T@g.M@T;C=T.T@g.C@T;K=T.T@g.K@T
    A=np.block([[np.zeros((2,2)),np.eye(2)],[-la.solve(M,K),-la.solve(M,C)]])
    B=np.vstack((np.zeros((2,2)),la.inv(M)))
    Q=np.diag([1e6,1e6,1e4,1e4]);R=np.diag([1e-2,1e-2])
    X=la.solve_continuous_are(A,B,Q,R);gain=la.solve(R,B.T@X)
    for m in models.values():m.gain=gain.copy()
    care=relative(A.T@X+X@A-X@B@la.solve(R,B.T@X),-Q)
    checks={'assembled_K':relative(parts['global_P']['K']+parts['global_N']['K'],f['K']),
            'assembled_M':relative(parts['global_P']['M']+parts['global_N']['M'],f['M']),
            'assembled_C':relative(parts['global_P']['C']+parts['global_N']['C'],f['C']),
            'care_residual':care,'gain':gain.tolist(),'model_orders':{k:m.n for k,m in models.items()},
            'local_modes_hz':{k:basis(parts[k],N_IDS if k=='N' else P_IDS,N_MASTER if k=='N' else P_MASTER,0)[1].tolist() for k in ['N','P']}}
    for side in ['P','N']:
        for k in ['M','C','K']:
            mat=parts[side][k];checks[f'{side}_{k}_symmetry']=relative(mat,mat.T)
            checks[f'{side}_{k}_min_eigenvalue']=float(la.eigvalsh(mat)[0]);la.cholesky(mat)
    assert max(checks[k] for k in ['assembled_K','assembled_M','assembled_C','care_residual'])<1e-10,checks
    return models,parts,checks

def operators(m,h=DT):
    mass=m.M+h/2*m.C+h*h/4*m.K
    c0=m.C.copy();k0=m.K.copy();cs=[];ks=[]
    for ell in range(2):
        c=m.Cp@m.S[ell][:,None]@m.S[ell][None,:]
        k=m.Kp@m.S[ell][:,None]@m.S[ell][None,:]
        c0-=c;k0-=k
        cs.append(c+np.outer(m.S[ell],m.gain[ell,2:]@m.S))
        ks.append(k+np.outer(m.S[ell],m.gain[ell,:2]@m.S))
    return mass,c0,k0,cs,ks

def transition(m,delays,h=DT):
    """2*n+2*max(delay) exact history state, storing only actuated q history."""
    delays=tuple(map(int,delays));N=max(delays);n=m.n;size=2*n+2*N
    mass,c0,k0,cs,ks=operators(m,h)
    A=np.zeros((size,size));A[:n,:n]=2*np.eye(n)-la.solve(mass,h*c0+h*h*k0)
    A[:n,n:2*n]=-np.eye(n)+la.solve(mass,h*c0)
    A[n:2*n,:n]=np.eye(n)
    if N:
        A[2*n:2*n+2,n:2*n]=m.S
        if N>1:A[2*n+2:,2*n:-2]=np.eye(2*(N-1))
    def add_lag(mat,lag):
        if lag==0:A[:n,:n]+=mat
        elif lag==1:A[:n,n:2*n]+=mat
        else:
            block=2*n+2*(lag-2)
            A[:n,block:block+2]+=mat@m.S.T
    for ell,delay in enumerate(delays):
        add_lag(-la.solve(mass,h*cs[ell]+h*h*ks[ell]),delay)
        add_lag(la.solve(mass,h*cs[ell]),delay+1)
    b=np.zeros(size);b[:n]=h*h*la.solve(mass,m.force)
    return A,b

def characteristic(m,z,delays,h=DT):
    mass,c0,k0,cs,ks=operators(m,h)
    dv=(z-1)/(z*h)
    Z=(z-1)**2/(z*h*h)*mass+dv*c0+k0
    for delay,c,k in zip(delays,cs,ks):Z=Z+z**(-delay)*(dv*c+k)
    return Z

def poles(m,delays,h=DT,vectors=False):
    A,b=transition(m,delays,h)
    if vectors:
        w,V=la.eig(A);return w,V,A
    return la.eigvals(A)

def simulate(m,delays,ag,h=DT):
    """Direct CR equilibrium recursion; zero displacement/velocity/history."""
    mass,c0,k0,cs,ks=operators(m,h);inv=la.inv(mass)
    ns=len(ag);q=np.zeros((ns+1,m.n));v=np.zeros_like(q)
    delayed=np.zeros((2,m.n));vd=np.zeros_like(delayed)
    for k in range(ns-1):
        for ell,delay in enumerate(delays):
            j=k-delay
            delayed[ell]=q[j] if j>=0 else 0
            vd[ell]=v[j] if j>=0 else 0
        a=inv@(m.force*ag[k]-c0@v[k]-k0@q[k]-sum(cs[i]@vd[i]+ks[i]@delayed[i] for i in range(2)))
        v[k+1]=v[k]+h*a;q[k+1]=q[k]+h*v[k+1]
        if not np.all(np.isfinite(q[k+1])):raise FloatingPointError((m.name,delays,k))
    q=q[:ns];v=v[:ns]
    yn=q@m.Yn.T;yp=q@m.Yp.T
    for ell,delay in enumerate(delays):
        active=q@m.S[ell]
        lagged=np.r_[np.zeros(delay),active[:ns-delay]] if delay else active
        yp+=np.outer(lagged-active,m.Yp@m.S[ell])
    return dict(q=q,v=v,physical_mm=1000*yp,numerical_mm=1000*yn)

def load_inputs():
    raw=loadmat(CASE/'data/EQ.mat',simplify_cells=True)
    t=np.arange(40961)*DT
    eq=np.interp(t,raw['ElCentroAccel'][0],raw['ElCentroAccel'][1])*float(raw['EQ_intensity'])
    chirp=np.sin(2*np.pi*.1*t+np.pi*9.9/40*t*t)
    return t,{'eq':eq,'chirp':chirp}

if __name__=='__main__':
    import json
    models,parts,checks=build_models()
    print(json.dumps(checks,indent=2))
    for delays in [(0,0),(1,1),(2,2),(4,4),(8,8),(1,4),(4,1)]:
        print(delays,{k:float(max(abs(poles(m,delays)))) for k,m in models.items()},flush=True)
