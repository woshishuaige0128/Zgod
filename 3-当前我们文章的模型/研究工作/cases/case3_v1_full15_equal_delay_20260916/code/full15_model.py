"""Full-frame virtual RTHS with two equal-delay signals and consistent projection.

SI units; base record sign retained from the frozen source. The mass is advanced
numerically. Undriven physical coordinates are supplied by the current numerical
state. This is an explicit virtual-feedback model, not a two-actuator hardware
realizability claim. No calculation is run by importing this module.
"""
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import numpy as np
from scipy import linalg as la
from scipy.io import loadmat
from numba import njit

ROOT=Path(__file__).resolve().parents[1]
H=1/1024
FLOORS=np.array([0,5,10])
STORY_HEIGHT=0.635
RETAINED={1:np.array([0,5,10,3,8,13]),2:np.array([0,10,3,8,13])}
PORTS={1:np.array([0,5]),2:np.array([0,10])}

@dataclass(frozen=True)
class Model:
    M:np.ndarray
    C:np.ndarray
    K:np.ndarray
    C0:np.ndarray
    K0:np.ndarray
    Uc:np.ndarray
    Uk:np.ndarray
    S:np.ndarray
    f:np.ndarray
    Yn:np.ndarray
    Y0:np.ndarray
    Jd:np.ndarray
    T:np.ndarray
    division:int
    label:str
    @property
    def order(self):return self.M.shape[0]

@lru_cache(maxsize=1)
def load_sources():
    bundle=loadmat(ROOT/'data/calculation.mat',simplify_cells=True)['bundle']
    local=loadmat(ROOT/'data/audit_matrices.mat',simplify_cells=True)
    saved=loadmat(ROOT/'data/model_and_cases.mat',simplify_cells=True)
    return bundle['frame'],bundle['inputs'],local,np.asarray(saved['Full15']['gain'],float)

def timing(n,h):
    if isinstance(n,(bool,np.bool_)) or not isinstance(n,(int,np.integer)) or n<0:
        raise ValueError('Delay must be a nonnegative integer number of steps')
    if not np.isfinite(h) or h<=0:raise ValueError('Step size must be finite and positive')

def full_model(division,gain=None):
    if division not in RETAINED:raise ValueError('Division must be 1 or 2')
    frame,_,audit,_=load_sources()
    gain=np.zeros((2,4)) if gain is None else np.asarray(gain,float)
    if gain.shape!=(2,4) or not np.isfinite(gain).all():raise ValueError('Gain must be finite 2 by 4')
    p=np.array([0,1,2,5,6,7] if division==1 else [0,1,2,5,6,7,10,11,12])
    embed=np.eye(15)[p]
    Cp=embed.T@audit[f'div{division}_C_P']@embed
    Kp=embed.T@audit[f'div{division}_K_P']@embed
    M,C,K=[np.asarray(frame[k],float) for k in ['M','C','K']]
    S=np.eye(15)[PORTS[division]];B=S.T;D=B@S;L=np.eye(15)[FLOORS]
    F=Model(M,C,K,C-Cp@D,K-Kp@D,Cp@B+B@gain[:,2:],
            Kp@B+B@gain[:,:2],S,M@L.sum(axis=0),L,L@(np.eye(15)-D),L@B,
            np.eye(15),division,'Full15')
    validate_model(F)
    return F

def validate_model(F):
    r=F.order
    for k in ['M','C','K','C0','K0']:
        a=getattr(F,k)
        if a.shape!=(r,r) or not np.isfinite(a).all():raise ValueError(k+' shape or values')
    for k,shape in [('Uc',(r,2)),('Uk',(r,2)),('S',(2,r)),('f',(r,)),
                    ('Yn',(3,r)),('Y0',(3,r)),('Jd',(3,2)),('T',(15,r))]:
        a=getattr(F,k)
        if a.shape!=shape or not np.isfinite(a).all():raise ValueError(k+' shape or values')
    la.cholesky(F.M);la.cholesky(F.K)
    if np.linalg.matrix_rank(F.S)!=2:raise ValueError('Two independent ports required')

def guyan_basis(M,K,retained):
    """Static constraint map, using the explicit ordered retained coordinates."""
    r=np.asarray(retained,int);c=np.array([i for i in range(len(M)) if i not in r])
    if len(set(r))!=len(r) or len(r)==0 or min(r)<0 or max(r)>=len(M):
        raise ValueError('Invalid retained coordinate set')
    T=np.zeros((len(M),len(r)));T[r]=np.eye(len(r))
    T[c]=-la.solve(K[np.ix_(c,c)],K[np.ix_(c,r)],assume_a='pos')
    return T

def cb_basis(F,modes):
    if F.order!=15:raise ValueError('CB basis is defined in the original full frame')
    r=RETAINED[F.division];c=np.array([i for i in range(15) if i not in r])
    if isinstance(modes,(bool,np.bool_)) or not isinstance(modes,(int,np.integer)) or not 0<=modes<=len(c):
        raise ValueError('Invalid internal mode count')
    lam,phi=la.eigh(F.K[np.ix_(c,c)],F.M[np.ix_(c,c)])
    for j in range(phi.shape[1]):
        if phi[np.argmax(abs(phi[:,j])),j]<0:phi[:,j]*=-1
    T=np.zeros((15,len(r)+modes));T[:,:len(r)]=guyan_basis(F.M,F.K,r)
    T[np.ix_(c,np.arange(len(r),len(r)+modes))]=phi[:,:modes]
    return T,lam

def project(F,T,label):
    T=np.asarray(T,float)
    if T.ndim!=2 or T.shape[0]!=F.order or not np.isfinite(T).all() or np.linalg.matrix_rank(T)!=T.shape[1]:
        raise ValueError('Projection basis must be finite, compatible and full rank')
    mats={k:T.T@getattr(F,k)@T for k in ['M','C','K','C0','K0']}
    R=Model(**mats,Uc=T.T@F.Uc,Uk=T.T@F.Uk,S=F.S@T,f=T.T@F.f,
            Yn=F.Yn@T,Y0=F.Y0@T,Jd=F.Jd.copy(),T=F.T@T,division=F.division,label=label)
    validate_model(R)
    return R

def family(division,modes=(0,3),gain=None):
    F=full_model(division,gain);models={'Full15':F}
    for m in modes:
        T,_=cb_basis(F,m);label='Guyan' if m==0 else f'CB{m}'
        models[label]=project(F,T,label)
    return models

def algorithm_mass(F,h=H):
    timing(0,h)
    return F.M+h/2*F.C+h*h/4*F.K

def continuous(F,s,tau):
    if not np.isfinite(tau) or tau<0:raise ValueError('Delay must be finite and nonnegative')
    return s*s*F.M+s*F.C0+F.K0+np.exp(-s*tau)*(s*F.Uc+F.Uk)@F.S

def characteristic(F,z,n,h=H):
    timing(n,h)
    if z==0:raise ValueError('Use the augmented state matrix at z=0')
    dv=(1-1/z)/h;da=(z-2+1/z)/h**2
    return da*algorithm_mass(F,h)+dv*F.C0+F.K0+z**(-n)*(dv*F.Uc+F.Uk)@F.S

def state_space(F,n,h=H):
    """Port-history realization: [q_k, q_(k-1), S q_(k-2),...,S q_(k-n-1)]."""
    timing(n,h);r=F.order;size=2*r+2*n;Mh=algorithm_mass(F,h)
    A=np.zeros((size,size));A[:r,:r]=2*np.eye(r)-la.solve(Mh,h*F.C0+h*h*F.K0)
    A[:r,r:2*r]=-np.eye(r)+la.solve(Mh,h*F.C0);A[r:2*r,:r]=np.eye(r)
    if n:
        A[2*r:2*r+2,r:2*r]=F.S
        if n>1:A[2*r+2:,2*r:-2]=np.eye(2*(n-1))
    def add(U,lag):
        if lag<2:A[:r,lag*r:(lag+1)*r]+=U@F.S
        else:A[:r,2*r+2*(lag-2):2*r+2*(lag-1)]+=U
    add(-la.solve(Mh,h*F.Uc+h*h*F.Uk),n)
    add(la.solve(Mh,h*F.Uc),n+1)
    b=np.zeros(size);b[:r]=h*h*la.solve(Mh,F.f)
    return A,b

def state_output(F,n,kind='physical'):
    timing(n,H);r=F.order;O=np.zeros((3,2*r+2*n))
    if kind=='numerical':O[:,:r]=F.Yn
    elif kind=='physical':
        O[:,:r]=F.Y0
        if n<2:O[:,n*r:(n+1)*r]+=F.Jd@F.S
        else:O[:,2*r+2*(n-2):2*r+2*(n-1)]+=F.Jd
    else:raise ValueError('Output is physical or numerical')
    return O

def full_history(F,n,h=H):
    """Independent coordinate-history assembly, used as a cross-check."""
    timing(n,h);r=F.order;N=r*(n+2);A=np.zeros((N,N));Mh=algorithm_mass(F,h)
    coefficients=[np.zeros((r,r)) for _ in range(n+2)]
    coefficients[0]+=2*Mh-h*F.C0-h*h*F.K0
    coefficients[1]+=-Mh+h*F.C0
    coefficients[n]+=-h*F.Uc@F.S-h*h*F.Uk@F.S
    coefficients[n+1]+=h*F.Uc@F.S
    A[:r]=la.solve(Mh,np.concatenate(coefficients,axis=1))
    A[r:,:-r]=np.eye(N-r);b=np.zeros(N);b[:r]=h*h*la.solve(Mh,F.f)
    J=la.block_diag(np.eye(2*r),*([F.S]*n)) if n else np.eye(2*r)
    return A,b,J

def frequency_response(F,freq_hz,n,h=H,kind='physical'):
    if kind not in ('numerical','physical'):raise ValueError('Output is physical or numerical')
    z=np.exp(2j*np.pi*freq_hz*h);Z=characteristic(F,z,n,h)
    Y=F.Yn if kind=='numerical' else F.Y0+z**(-n)*F.Jd@F.S
    return Y@la.solve(Z,F.f)

@njit(cache=False)
def _advance(A,b,O,u,x0):
    size=A.shape[0];p=O.shape[0];steps=len(u);y=np.zeros((steps+1,p))
    x=x0.copy()
    for j in range(p):
        for k in range(size):y[0,j]+=O[j,k]*x[k]
    for t in range(steps):
        nx=np.zeros(size)
        for j in range(size):
            nx[j]=b[j]*u[t]
            for k in range(size):nx[j]+=A[j,k]*x[k]
        x=nx
        for j in range(p):
            for k in range(size):y[t+1,j]+=O[j,k]*x[k]
    return y,x

def simulate(F,n,u,h=H,x0=None):
    """Input has N samples u_0...u_(N-1); returns N+1 states' six outputs.

    Columns 0:3 are numerical floor commands, 3:6 are physical recovered floors.
    Historical state is retained during zero input, including after unloading.
    """
    A,b=state_space(F,n,h);O=np.vstack([state_output(F,n,'numerical'),state_output(F,n,'physical')])
    u=np.asarray(u,float)
    if u.ndim!=1 or not np.isfinite(u).all():raise ValueError('Input must be a finite vector')
    x0=np.zeros(len(A)) if x0 is None else np.asarray(x0,float)
    if x0.shape!=(len(A),) or not np.isfinite(x0).all():raise ValueError('Invalid initial history state')
    return _advance(np.ascontiguousarray(A),np.ascontiguousarray(b),np.ascontiguousarray(O),u,x0)

def independent_recurrence(F,n,u,h=H,history=None):
    """Explicit second-order force balance; intentionally does not use A or b."""
    timing(n,h);r=F.order;u=np.asarray(u,float)
    old=np.zeros((n+2,r)) if history is None else np.asarray(history,float).copy()
    if old.shape!=(n+2,r):raise ValueError('History rows are q_0,q_-1,...,q_-n-1')
    out=np.empty((len(u)+1,6));Mh=algorithm_mass(F,h)
    def output():return np.r_[F.Yn@old[0],F.Y0@old[0]+F.Jd@F.S@old[n]]
    out[0]=output()
    for k,forcing in enumerate(u):
        v=(old[0]-old[1])/h;vd=(old[n]-old[n+1])/h
        req=F.f*forcing-F.C0@v-F.K0@old[0]-F.Uc@F.S@vd-F.Uk@F.S@old[n]
        algorithm_acceleration=la.solve(Mh,req,assume_a='pos')
        qnew=old[0]+h*v+h*h*algorithm_acceleration
        old[1:]=old[:-1].copy();old[0]=qnew;out[k+1]=output()
    return out

def residual_error(F,R,z,n,h=H,kind='physical'):
    Zf=characteristic(F,z,n,h);Zr=characteristic(R,z,n,h)
    q=la.solve(Zr,R.f);residual=F.f-Zf@R.T@q
    Y=F.Yn if kind=='numerical' else F.Y0+z**(-n)*F.Jd@F.S
    return -Y@la.solve(Zf,residual),residual

def drift(floor_displacements):
    return np.asarray(floor_displacements)@np.array([[1,-1,0],[0,1,-1],[0,0,1]])/STORY_HEIGHT

def error_metrics(pred,ref):
    pred=np.asarray(pred);ref=np.asarray(ref);err=pred-ref
    if pred.shape!=ref.shape or pred.ndim!=2 or not np.isfinite(pred).all() or not np.isfinite(ref).all():
        raise ValueError('Metrics require two finite arrays with the same time/output shape')
    rms=np.sqrt(np.mean(err*err,axis=0));span=np.ptp(ref,axis=0)
    energy=np.sqrt(np.mean(ref*ref,axis=0));peak=np.max(abs(ref),axis=0)
    def ratio(num,den):return [float(100*a/b) if b>0 else None for a,b in zip(num,den)]
    return dict(nrmse_range_pct=ratio(rms,span),relative_l2_pct=ratio(rms,energy),
                peak_bias_pct=ratio(np.max(abs(pred),axis=0)-peak,peak),
                max_abs_error=np.max(abs(err),axis=0).tolist(),rms_abs_error=rms.tolist(),
                undefined_relative_metrics='null when the reference denominator is zero')
