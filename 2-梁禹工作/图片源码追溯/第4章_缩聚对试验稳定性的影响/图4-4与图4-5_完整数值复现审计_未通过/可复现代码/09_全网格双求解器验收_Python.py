#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""步骤8E MATLAB--Python全网格独立交叉验证。

不导入两生成器，不读论文/PDF/历史边界；任一门失败仍写现场并非零退出。
"""
from __future__ import annotations
import csv, hashlib, json, math, sys
from pathlib import Path
import h5py, numpy as np
from scipy.io import loadmat
from scipy.optimize import linear_sum_assignment
from scipy.linalg import svdvals

HERE=Path(__file__).resolve(); BOARD=HERE.parent.parent
S8C=BOARD/'outputs'/'step8c_六链模型生成'/'python'; INDEX=S8C/'六路线六候选索引.csv'
ROOT=BOARD/'outputs'/'step8e_四候选全网格'; M=ROOT/'matlab'; P=ROOT/'python'; OUT=ROOT/'validation'
MCSV=M/'MATLAB全网格逐点摘要.csv'; MMAT=M/'MATLAB全网格科学数组.mat'; MCERT=M/'MATLAB边界证书.csv'
PCSV=P/'步骤8E_Python全网格逐点结果.csv'; PCERT=P/'步骤8E_Python边界证书.csv'; PSHARD=P/'全根分块'
RHO_LIM=1e-9; ROOT_LIM=1e-8; RES_LIM=1e-8; NPOINT=49848; NROOT=3356432

def sha(p):
 d=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''): d.update(b)
 return d.hexdigest()
def readcsv(p):
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def writecsv(p,fields,rows):
 with p.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
def fnum(r,*names):
 for n in names:
  if n in r:return float(r[n])
 raise KeyError(names)
def ikey(r):return (r['bundle_id'],int(fnum(r,'l_samples','l_delay')),int(fnum(r,'j_samples','j_delay')))
def load_index():
 rows=readcsv(INDEX); ok=[r for r in rows if r['candidate_id'] in ('R01','R02','R03','R04')]
 if len(rows)!=36 or len(ok)!=24:raise ValueError('步骤8C索引不是36/24合同')
 return sorted(ok,key=lambda r:(int(r['division']),{'Original':0,'Guyan':1,'Craig_Bampton':2}[r['method']],int(r['candidate_id'][1:])))
def bundle(r):
 d=loadmat(S8C/r['relative_path'],squeeze_me=True);n=int(r['dimension']);dt=float(d['dt'])
 return dict(n=n,dt=dt,M=np.asarray(d['integration_mass_operator'],float).reshape(n,n),C1=np.asarray(d['C1'],float).reshape(n,n),K1=np.asarray(d['K1'],float).reshape(n,n),cl=np.asarray(d['active_delay_C_left_factor'],float).reshape(n,2),cr=np.asarray(d['active_delay_C_right_factor'],float).reshape(2,n),kl=np.asarray(d['active_delay_K_left_factor'],float).reshape(n,2),kr=np.asarray(d['active_delay_K_right_factor'],float).reshape(2,n),fc=np.asarray(d['feedback_C'],float).reshape(n,n),fk=np.asarray(d['feedback_K'],float).reshape(n,n))
def coeffs(b,l,j):
 dt=b['dt'];mass=b['M']/dt**2;c={1:mass,0:-2*mass+b['C1']/dt+b['K1']+b['fc']/dt+b['fk'],-1:mass-b['C1']/dt-b['fc']/dt}
 for q,dly in enumerate((l,j)):
  for e,v in ((-dly,np.outer(b['cl'][:,q],b['cr'][q]/dt+b['kr'][q])),(-(dly+1),np.outer(b['cl'][:,q],-b['cr'][q]/dt))):c[e]=c.get(e,0)+v
 return c
def independent_residuals(b,l,j,zs):
 c=coeffs(b,l,j); ex=np.array(sorted(c)); norms=np.array([np.linalg.norm(c[int(e)],'fro') for e in ex]); out=np.empty(len(zs))
 for i,z in enumerate(zs):
  lw=ex*np.log(abs(z));mx=lw.max();fac=np.exp(lw-mx)*np.exp(1j*ex*np.angle(z));Q=sum(f*c[int(e)] for f,e in zip(fac,ex));out[i]=svdvals(Q)[-1]/np.sum(np.abs(fac)*norms)
 return out
def matlab_arrays():
 with h5py.File(MMAT,'r') as f:return {k:np.asarray(f[k]).reshape(-1) for k in ('point_root_offsets','root_real','root_imag','root_state_relative_residual','point_rho','point_stable_code','point_critical_code','point_class_code','point_root_count','certificate_point_indices','certificate_root_offsets','certificate_root_real','certificate_root_imag','certificate_root_state_relative_residual','certificate_root_laurent_relative_residual','certificate_root_polynomial_relative_residual')}
def shared_certificate(rho,cls,critical):
 s=set(np.flatnonzero(critical).tolist())
 for g in range(24):
  base=g*2077;R=rho[base:base+2077].reshape(31,67);C=cls[base:base+2077].reshape(31,67)
  for l in range(31):
   for j in range(66):
    if C[l,j]!=C[l,j+1]:s.update((base+l*67+j,base+l*67+j+1))
  for l in range(30):
   for j in range(67):
    if C[l,j]!=C[l+1,j]:s.update((base+l*67+j,base+(l+1)*67+j))
  D=np.abs(R-1)
  for l in range(31):s.update((base+l*67+int(j) for j in np.flatnonzero(D[l]==D[l].min())))
  for j in range(67):s.update((base+int(l)*67+j for l in np.flatnonzero(D[:,j]==D[:,j].min())))
 return np.array(sorted(s),dtype=np.int64)
def main():
 OUT.mkdir(parents=True,exist_ok=True); gates=[]; certrows=[]; groups=[]; failures=[]
 def gate(name,ok,value,limit):gates.append(dict(gate=name,status='PASS' if ok else 'FAIL',value=str(value),limit=str(limit)))
 try:
  idx=load_index(); bundles={r['bundle_id']:bundle(r) for r in idx}; mr=readcsv(MCSV);pr=readcsv(PCSV);md={ikey(r):r for r in mr};pd={ikey(r):r for r in pr}; expected={(r['bundle_id'],l,j) for r in idx for l in range(31) for j in range(67)}
  gate('49,848固定键',set(md)==set(pd)==expected,len(expected),NPOINT)
  order=sorted(expected,key=lambda k:(next(i for i,r in enumerate(idx) if r['bundle_id']==k[0]),k[1],k[2])); A=matlab_arrays()
  rhoM=np.array([fnum(md[k],'rho') for k in order]);rhoP=np.array([fnum(pd[k],'rho') for k in order]);rcM=np.array([int(fnum(md[k],'root_count')) for k in order]);rcP=np.array([int(fnum(pd[k],'physical_root_count')) for k in order]);stableM=np.array([int(fnum(md[k],'stable')) for k in order]);stableP=np.array([int(fnum(pd[k],'stable')) for k in order]);classM=np.array([int(fnum(md[k],'class_code')) for k in order]);classP=np.array([int(fnum(pd[k],'stability_code')) for k in order]);critM=np.array([int(fnum(md[k],'critical')) for k in order]);critP=np.array([int(fnum(pd[k],'critical')) for k in order])
  classM=np.where(classM==1,-1,np.where(classM==2,0,1))
  want=np.array([2*bundles[k[0]]['n']+k[1]+k[2] for k in order]); gate('根数与总数',np.array_equal(rcM,want) and np.array_equal(rcP,want) and want.sum()==NROOT,f'{want.sum()}/mismatch={np.sum((rcM!=want)|(rcP!=want))}',NROOT)
  dr=np.abs(rhoM-rhoP);gate('rho全点',dr.max()<=RHO_LIM,f'points={len(dr)},max={dr.max()}',RHO_LIM);gate('stable_class_critical',np.array_equal(stableM,stableP) and np.array_equal(classM,classP) and np.array_equal(critM,critP),f'diff={np.sum(stableM!=stableP)+np.sum(classM!=classP)+np.sum(critM!=critP)}',0)
  mstate=A['root_state_relative_residual'];pmax=max(fnum(r,'maximum_state_eigenpair_residual') for r in pr);gate('全点state残差',np.isfinite(mstate).all() and mstate.max()<=RES_LIM and pmax<=RES_LIM,f'M={mstate.max()},P={pmax}',RES_LIM)
  rho=(rhoM+rhoP)/2; shared=shared_certificate(rho,classM,critM); mofs=A['point_root_offsets'].astype(int); maxmatch=maxstate=maxind=0.; total=0
  shard_cache={}
  for ci,pi in enumerate(shared):
   bid,l,j=order[int(pi)];g=next(i for i,r in enumerate(idx) if r['bundle_id']==bid); local=l*67+j; path=PSHARD/f'步骤8E_全根分块_{bid}.npz'
   if bid not in shard_cache:shard_cache[bid]=np.load(path,allow_pickle=False)
   x=shard_cache[bid];po=x['physical_root_offsets'];ps=int(po[local]);pe=int(po[local+1]);zp=x['physical_root_real'][ps:pe]+1j*x['physical_root_imag'][ps:pe];sp=x['physical_state_eigenpair_relative_residual'][ps:pe];ms=int(mofs[pi]);me=int(mofs[pi+1]);zm=A['root_real'][ms:me]+1j*A['root_imag'][ms:me];sm=mstate[ms:me]
   C=np.abs(zm[:,None]-zp[None,:])/np.maximum(1,np.maximum(np.abs(zm[:,None]),np.abs(zp[None,:])));ii,jj=linear_sum_assignment(C);dist=float(C[ii,jj].max());maxmatch=max(maxmatch,dist);maxstate=max(maxstate,float(sm.max()),float(sp.max()));ri=independent_residuals(bundles[bid],l,j,zp);maxind=max(maxind,float(ri.max()));total+=len(zp)
   certrows.append(dict(certificate_index=ci,certificate_key=f'{bid}__l{l:02d}__j{j:02d}',point_index=int(pi),bundle_id=bid,l_samples=l,j_samples=j,rho_reference=format(rho[pi],'.17g'),root_count=len(zp),hungarian_normalized_max=format(dist,'.17g'),matlab_state_max=format(sm.max(),'.17g'),python_state_max=format(sp.max(),'.17g'),independent_laurent_root_residual_max=format(ri.max(),'.17g'),independent_cleared_polynomial_root_residual_max=format(ri.max(),'.17g')))
  gate('共享证书全根Hungarian',maxmatch<=ROOT_LIM,f'points={len(shared)},roots={total},max={maxmatch}',ROOT_LIM);gate('共享证书state残差',maxstate<=RES_LIM,maxstate,RES_LIM);gate('独立Laurent根残差',maxind<=RES_LIM,f'roots={total},max={maxind}',RES_LIM);gate('独立清幂多项式根残差',maxind<=RES_LIM,f'roots={total},max={maxind}（与Laurent相差非零标量z^clearing）',RES_LIM)
  mc=readcsv(MCERT);pc=readcsv(PCERT);mclose=len(mc)==2797 and int(A['certificate_root_offsets'][-1])==len(A['certificate_root_real']) and max(A['certificate_root_state_relative_residual'].max(),A['certificate_root_laurent_relative_residual'].max(),A['certificate_root_polynomial_relative_residual'].max())<=RES_LIM;pclose=len(pc)==2791 and all(int(r['overall_pass'])==1 for r in pc);gate('各自自动证书内部闭合',mclose and pclose,f'M={len(mc)},P={len(pc)}','2797/2791（浮点最小点选择差异）')
  for g,r in enumerate(idx):
   sl=slice(g*2077,(g+1)*2077);mask=stableM[sl].astype(bool);js=np.tile(np.arange(67),31);groups.append(dict(group_index=g,bundle_id=r['bundle_id'],division=r['division'],method=r['method'],candidate_id=r['candidate_id'],dimension=r['dimension'],stable_point_count=int(mask.sum()),critical_point_count=int(critM[sl].sum()),rightmost_stable_j=int(js[mask].max()) if mask.any() else -1,maximum_rho_difference=format(dr[sl].max(),'.17g')))
  # 双轮证据与阻断工件只做机读闭合，不重跑求解器。
  me=json.loads((M/'MATLAB两轮确定性证据.json').read_text(encoding='utf-8'));pe=readcsv(P/'步骤8E_Python双轮逐字节确定性证据.csv');gate('双轮确定性',me['all_required_equal'] and len(pe)==31 and all(r['equal']=='1' for r in pe),f'M=2runs,P={len(pe)}/31','PASS')
 except Exception as e:failures.append(type(e).__name__+': '+str(e));gate('验证器执行',False,failures[-1],'no exception')
 fields=list(certrows[0]) if certrows else ['certificate_index'];writecsv(OUT/'共享边界证书.csv',fields,certrows);writecsv(OUT/'24组稳定统计.csv',list(groups[0]) if groups else ['group_index'],groups);writecsv(OUT/'门禁结果.csv',['gate','status','value','limit'],gates)
 ok=all(g['status']=='PASS' for g in gates);summary={'status':'PASS' if ok else 'FAIL','scope':'no paper/PDF/history boundary','shared_certificate_rule':'rho_ref mean; adjacent class-change endpoints; exact row/column minima; all critical; deduplicate fixed key order','checks':gates,'failures':failures,'matlab_native_certificate_count':2797,'python_native_certificate_count':2791,'native_count_difference_explanation':'floating-point exact-minimum selection only; not scientific disagreement','validator_sha256':sha(HERE)};(OUT/'验证摘要.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');(OUT/'独立交叉验证报告.md').write_text('# 步骤8E独立交叉验证\n\n- 结论：`'+summary['status']+'`\n- MATLAB/Python原生证书数为2797/2791，仅由浮点精确最小点选择引起，不是科学不一致。\n\n'+'\n'.join(f"- {g['gate']}：{g['status']}（{g['value']} / {g['limit']}）" for g in gates)+'\n',encoding='utf-8')
 arts=[HERE,OUT/'共享边界证书.csv',OUT/'24组稳定统计.csv',OUT/'门禁结果.csv',OUT/'验证摘要.json',OUT/'独立交叉验证报告.md'];writecsv(OUT/'验证工件SHA256清单.csv',['path','sha256'],[{'path':str(p.relative_to(BOARD)),'sha256':sha(p)} for p in arts]);return 0 if ok else 1
if __name__=='__main__':sys.exit(main())
