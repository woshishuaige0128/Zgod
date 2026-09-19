"""Candidate full-frame equal-delay operators. No response integrator or scan.

The two delayed signals are defined in the original 15 physical coordinates.
All operators are then projected; reduced-coordinate columns are never selected
to redefine the physical feedback. Other interface coordinates remain ideal.
"""
from pathlib import Path
from dataclasses import dataclass
import numpy as np
from scipy import linalg as la
from scipy.io import loadmat

OUT=Path(__file__).resolve().parents[1]
H=1/1024
FLOORS=np.array([0,5,10])

@dataclass
class Operators:
    M:np.ndarray
    C:np.ndarray
    K:np.ndarray
    C0:np.ndarray
    K0:np.ndarray
    Uc:np.ndarray
    Uk:np.ndarray
    R:np.ndarray
    f:np.ndarray
    Yn:np.ndarray
    Y0:np.ndarray
    Yd:np.ndarray
    @property
    def n(self):return len(self.M)

def sources():
    frame=loadmat(OUT/'sources/calculation.mat',simplify_cells=True)['bundle']['frame']
    audit=loadmat(OUT/'sources/audit_matrices.mat',simplify_cells=True)
    saved=loadmat(OUT/'sources/model_and_cases.mat',simplify_cells=True)
    return frame,audit,saved

def full_model(division,frame,audit,gain):
    p=np.array([1,2,3,6,7,8] if division==1 else [1,2,3,6,7,8,11,12,13])-1
    act=np.array([1,6] if division==1 else [1,11])-1
    E=np.eye(15)[p]
    Cp=E.T@audit[f'div{division}_C_P']@E
    Kp=E.T@audit[f'div{division}_K_P']@E
    S=np.eye(15)[act];B=S.T;L=np.eye(15)[FLOORS]
    M,C,K=(frame[k] for k in ['M','C','K'])
    # One fixed gain from the already verified Division II source is used only
    # as an algebraic test coefficient for both divisions; no new design.
    Gd,Gv=gain[:,:2],gain[:,2:]
    C0=C-Cp@B@S;K0=K-Kp@B@S
    Uc=Cp@B+B@Gv;Uk=Kp@B+B@Gd
    gamma=np.zeros(15);gamma[FLOORS]=1
    return Operators(M,C,K,C0,K0,Uc,Uk,S,M@gamma,L,L@(np.eye(15)-B@S),L@B@S)

def cb_basis(frame,division,count):
    retained=np.array([1,6,11,4,9,14] if division==1 else [1,11,4,9,14])-1
    internal=np.array([i for i in range(15) if i not in retained])
    K,M=frame['K'],frame['M'];r=len(retained)
    T=np.zeros((15,r+count));T[retained,:r]=np.eye(r)
    T[internal,:r]=-la.solve(K[np.ix_(internal,internal)],K[np.ix_(internal,retained)])
    lam,phi=la.eigh(K[np.ix_(internal,internal)],M[np.ix_(internal,internal)])
    T[np.ix_(internal,np.arange(r,r+count))]=phi[:,:count]
    return T,retained,internal,lam

def project(F,T):
    mats={k:T.T@getattr(F,k)@T for k in ['M','C','K','C0','K0']}
    return Operators(**mats,Uc=T.T@F.Uc,Uk=T.T@F.Uk,R=F.R@T,
        f=T.T@F.f,Yn=F.Yn@T,Y0=F.Y0@T,Yd=F.Yd@T)

def algorithm_mass(F,h=H):return F.M+h/2*F.C+h*h/4*F.K

def continuous(F,s,tau):
    return s*s*F.M+s*F.C0+F.K0+np.exp(-s*tau)*(s*F.Uc+F.Uk)@F.R

def characteristic(F,z,steps,h=H):
    dv=(1-1/z)/h;da=(z-2+1/z)/h**2
    return da*algorithm_mass(F,h)+dv*F.C0+F.K0+z**(-steps)*(dv*F.Uc+F.Uk)@F.R

def physical_output(F,z,steps):return F.Y0+z**(-steps)*F.Yd

def augmented(F,steps,h=H):
    """Minimal port history for algebraic checks, not a time-history solver."""
    n=F.n;size=2*n+2*steps;Mh=algorithm_mass(F,h)
    A=np.zeros((size,size));A[:n,:n]=2*np.eye(n)-la.solve(Mh,h*F.C0+h*h*F.K0)
    A[:n,n:2*n]=-np.eye(n)+la.solve(Mh,h*F.C0)
    A[n:2*n,:n]=np.eye(n)
    if steps:
        A[2*n:2*n+2,n:2*n]=F.R
        if steps>1:A[2*n+2:,2*n:-2]=np.eye(2*(steps-1))
    def add(U,lag):
        if lag<2:A[:n,lag*n:(lag+1)*n]+=U@F.R
        else:A[:n,2*n+2*(lag-2):2*n+2*(lag-1)]+=U
    add(-la.solve(Mh,h*F.Uc+h*h*F.Uk),steps)
    add(la.solve(Mh,h*F.Uc),steps+1)
    b=np.zeros(size);b[:n]=h*h*la.solve(Mh,F.f)
    return A,b

def interface_basis(frame,audit,division,nmN,nmP):
    """Retain ALL shared interface coordinates before local CB reduction."""
    p=np.array([1,2,3,6,7,8] if division==1 else [1,2,3,6,7,8,11,12,13])-1
    n=np.array([1,3,4,5,6,7,8,9,10,11,12,13,14,15] if division==1 else [1,3,4,5,6,8,9,10,11,13,14,15])-1
    act=[0,5] if division==1 else [0,10]
    common=sorted(set(p)&set(n))
    nr=([0,5,10,3,8,13] if division==1 else [0,10,5,3,8,13])
    nr=nr+[int(x) for x in common if x not in nr]
    pr=act+[int(x) for x in common if x not in act]
    def local(ids,retained,side,nm):
        r=[list(ids).index(x) for x in retained];c=[i for i in range(len(ids)) if i not in r]
        K=audit[f'div{division}_K_{side}'];M=audit[f'div{division}_M_{side}']
        T=np.zeros((len(ids),len(r)+nm));T[r,:len(r)]=np.eye(len(r))
        T[c,:len(r)]=-la.solve(K[np.ix_(c,c)],K[np.ix_(c,r)])
        lam,phi=la.eigh(K[np.ix_(c,c)],M[np.ix_(c,c)])
        T[np.ix_(c,np.arange(len(r),len(r)+nm))]=phi[:,:nm]
        return T,c,float(la.eigvalsh(M[np.ix_(c,c)])[0]),lam
    tn,cn,minN,lamN=local(n,nr,'N',nmN);tp,cp,minP,lamP=local(p,pr,'P',nmP)
    size=len(nr)+nmN+nmP
    en=np.c_[np.eye(len(nr)+nmN),np.zeros((len(nr)+nmN,nmP))]
    ep=np.zeros((len(pr)+nmP,size))
    for i,x in enumerate(pr):ep[i,nr.index(x)]=1
    ep[len(pr):,len(nr)+nmN:]=np.eye(nmP)
    RN=tn@en;RP=tp@ep;T=np.zeros((15,size));T[n]=RN
    for i,x in enumerate(p):
        if x not in n:T[x]=RP[i]
    alpha,beta=frame['rayleigh'];assembled={}
    for k in ['M','K','C']:
        if k=='C':
            N=alpha*audit[f'div{division}_M_N']+beta*audit[f'div{division}_K_N']
            P=alpha*audit[f'div{division}_M_P']+beta*audit[f'div{division}_K_P']
        else:N=audit[f'div{division}_{k}_N'];P=audit[f'div{division}_{k}_P']
        assembled[k]=RN.T@N@RN+RP.T@P@RP
    gaps=np.array([RN[list(n).index(x)]-RP[list(p).index(x)] for x in common])
    info=dict(division=division,retained_global=[int(x+1) for x in nr],
        all_common=[int(x+1) for x in common],physical_retained=[int(x+1) for x in pr],
        numerical_internal=[int(n[x]+1) for x in cn],physical_internal=[int(p[x]+1) for x in cp],
        numerical_modes=nmN,physical_modes=nmP,order=size,
        numerical_internal_mass_min_eigenvalue=minN,physical_internal_mass_min_eigenvalue=minP,
        numerical_available_modes=len(cn),physical_available_modes=len(cp))
    return T,assembled,gaps,info
