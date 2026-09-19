#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""板块20步骤8D独立双求解器验证器。

不导入任一求解器；从步骤8C数值包独立重建最小增广合同。失败时仍写出
现场 CSV/JSON/报告/清单，然后非零退出。
"""
from __future__ import annotations

import csv, hashlib, json, math, sys
from pathlib import Path
import h5py
import numpy as np
from scipy.io import loadmat
from scipy.optimize import linear_sum_assignment

HERE = Path(__file__).resolve(); BOARD = HERE.parent.parent
INROOT = BOARD/'outputs'/'step8c_六链模型生成'/'python'
INDEX = INROOT/'六路线六候选索引.csv'
ROOT = BOARD/'outputs'/'step8d_单点双求解器门禁'
MROOT, PROOT, OUT = ROOT/'matlab', ROOT/'python', ROOT/'validation'
MCSV=MROOT/'MATLAB试点逐点结果.csv'; MMAT=MROOT/'MATLAB试点原始科学数组.mat'
PCSV=PROOT/'步骤8D_Python试点逐点结果.csv'; PNPZ=PROOT/'步骤8D_Python试点全部根.npz'
POINTS=(('P00',0,0),('P01',1,0),('P02',0,1),('P03',3,7),('P04',10,20),('P05',15,33),('P06',30,66),('P07',1,48),('P08',1,51),('P09',1,57),('P10',1,58),('P11',1,59),('P12',1,64))
# 固定在单位圆上，避免高时滞的 z**m0 自身造成下溢/上溢假差异。
PROBES=np.exp(1j*np.array([.173,.419,.731,1.087,1.533,2.071,2.617,2.941]))
RHO_TOL=1e-9; ROOT_TOL=1e-8; RES_TOL=1e-8; PROBE_TOL=1e-8

def sha(p):
 d=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''): d.update(b)
 return d.hexdigest()
def rows(p):
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def key(r): return (r['bundle_id'],r['point_id'])
def num(r,*names):
 for n in names:
  if n in r and r[n]!='': return float(r[n])
 raise KeyError(names)
def h5_value(f,ref):
 a=np.asarray(f[ref])
 if a.dtype.fields and {'real','imag'}<=set(a.dtype.fields): return (a['real']+1j*a['imag']).reshape(-1,order='F')
 return a.reshape(-1,order='F')
def matlab_roots(path):
 out={}
 with h5py.File(path,'r') as f:
  g=f['scientific_records']; N=g['bundle_id'].size
  def txt(ref): return ''.join(chr(int(x)) for x in h5_value(f,ref) if x).strip()
  br=g['bundle_id'][...].reshape(-1,order='F'); pr=g['point_id'][...].reshape(-1,order='F'); rr=g['physical_roots'][...].reshape(-1,order='F')
  for i in range(N): out[(txt(br[i]),txt(pr[i]))]=np.asarray(h5_value(f,rr[i]),complex)
 return out
def python_roots(path):
 x=np.load(path,allow_pickle=False); off=x['physical_root_offsets']; z=x['physical_root_real']+1j*x['physical_root_imag']; out={}
 for i,(b,p) in enumerate(zip(x['point_bundle_id'],x['point_point_id'])): out[(str(b),str(p))]=z[off[i]:off[i+1]]
 return out,x
def bundle(index_row):
 d=loadmat(INROOT/index_row['relative_path'],squeeze_me=True); n=int(index_row['dimension'])
 return dict(n=n,dt=float(d['dt']),M=np.asarray(d['integration_mass_operator'],float).reshape(n,n),C1=np.asarray(d['C1'],float).reshape(n,n),K1=np.asarray(d['K1'],float).reshape(n,n),cl=np.asarray(d['delay_C_left_factor'],float).reshape(n,2),cr=np.asarray(d['delay_C_right_factor'],float).reshape(2,n),kl=np.asarray(d['delay_K_left_factor'],float).reshape(n,2),kr=np.asarray(d['delay_K_right_factor'],float).reshape(2,n),fc=np.asarray(d['feedback_C'],float).reshape(n,n),fk=np.asarray(d['feedback_K'],float).reshape(n,n))
def independent_contract(b,l,j):
 n,dt=b['n'],b['dt']; mass=b['M']/dt**2; N=2*n+l+j; A=np.zeros((N,N)); B=np.zeros((N,N))
 z0=-2*mass+b['C1']/dt+b['K1']+b['fc']/dt+b['fk']; zm=mass-b['C1']/dt-b['fc']/dt
 B[:n,:n]=mass; A[:n,:n]=-z0; A[:n,n:2*n]=-zm; A[n:2*n,:n]=np.eye(n); B[n:2*n,n:2*n]=np.eye(n)
 off=2*n; gam=[]
 for c,dly in enumerate((l,j)):
  den=max(np.linalg.norm(b['cl'][:,c]),np.linalg.norm(b['kl'][:,c]),np.finfo(float).eps)
  if np.linalg.norm(b['cl'][:,c]-b['kl'][:,c])/den>1e-12: raise ValueError('C/K时滞左因子不共享')
  u=b['cl'][:,c]; a=b['cr'][c]/dt+b['kr'][c]; q=-b['cr'][c]/dt; gamma=max(np.linalg.norm(a),np.linalg.norm(q),np.finfo(float).eps); gam.append(gamma)
  if dly==0: A[:n,:n]-=np.outer(u,a); A[:n,n:2*n]-=np.outer(u,q); continue
  A[:n,off+dly-1]-=u*gamma; A[off,:n]=a/gamma; A[off,n:2*n]=q/gamma; B[off,off]=1
  for k in range(1,dly): A[off+k,off+k-1]=1; B[off+k,off+k]=1
  off+=dly
 return A,B,np.array(gam)
def poly_value(b,l,j,z):
 dt=b['dt']; mass=b['M']/dt**2
 Q=mass*z+(-2*mass+b['C1']/dt+b['K1']+b['fc']/dt+b['fk'])+(mass-b['C1']/dt-b['fc']/dt)/z
 for c,d in enumerate((l,j)):
  Q+=np.outer(b['cl'][:,c],b['cr'][c]/dt+b['kr'][c])*z**(-d)+np.outer(b['cl'][:,c],-b['cr'][c]/dt)*z**(-(d+1))
 return Q*z**(max(l,j)+1)
def probe_error(b,l,j,A,B):
 m0=b['n']*max(l,j)-l-j; vals=[]
 for z in PROBES:
  s1,a1=np.linalg.slogdet(poly_value(b,l,j,z)); s2,a2=np.linalg.slogdet(z*B-A)
  vals.append((a1-m0*math.log(abs(z))-a2)+1j*np.angle(s1/(z**m0*s2)))
 vals=np.array(vals); return float(max(np.ptp(vals.real),np.max(np.abs(np.angle(np.exp(1j*(vals.imag-vals.imag[0])))))))
def main():
 OUT.mkdir(parents=True,exist_ok=True); checks=[]; detail=[]
 def gate(name,ok,value='',limit=''):
  checks.append(dict(gate=name,status='PASS' if ok else 'FAIL',value=str(value),limit=str(limit)))
 try:
  idx=rows(INDEX); mr=rows(MCSV); pr=rows(PCSV); M=matlab_roots(MMAT); P,px=python_roots(PNPZ)
  eligible=[r for r in idx if r['candidate_id'] in ('R01','R02','R03','R04')]; rejected=[r for r in idx if r['candidate_id'] in ('R05','R06')]
  expected={(r['bundle_id'],p[0]) for r in eligible for p in POINTS}; gate('312键',len(expected)==312 and set(map(key,mr))==expected and set(map(key,pr))==expected,len(expected),312)
  madm=rows(MROOT/'36候选准入门禁.csv'); preject=rows(PROOT/'步骤8D_Python诊断候选拒绝.csv')
  mblocked=[r for r in madm if r.get('candidate_id') in ('R05','R06')]
  gate('R05_R06读取前阻断',len(rejected)==len(mblocked)==len(preject)==12 and all(r['paper_grid_eligible']!='ELIGIBLE_SOURCE_COMPLETION' for r in rejected),'12+12',12)
  gate('冻结试点',set((r['point_id'],int(num(r,'l_samples','l_delay')),int(num(r,'j_samples','j_delay'))) for r in mr)==set(POINTS),'exact','exact')
  md={key(r):r for r in mr}; pd={key(r):r for r in pr}; imax=rmax=pmax=gmax=0.; badcount=badclass=totalroots=0
  bundles={r['bundle_id']:bundle(r) for r in eligible}; pointmap={p[0]:(p[1],p[2]) for p in POINTS}
  for k in sorted(expected):
   a,c=md[k],pd[k]; b=bundles[k[0]]; l,j=pointmap[k[1]]; want=2*b['n']+l+j
   if int(num(a,'physical_root_count','retained_root_count'))!=want or int(num(c,'physical_root_count','retained_root_count'))!=want: badcount+=1
   totalroots+=want
   za,zc=M[k],P[k]; C=np.abs(za[:,None]-zc[None,:])/np.maximum(1,np.maximum(np.abs(za[:,None]),np.abs(zc[None,:]))); ii,jj=linear_sum_assignment(C); dist=float(C[ii,jj].max()); imax=max(imax,dist)
   rd=abs(num(a,'rho')-num(c,'rho')); rmax=max(rmax,rd)
   ra,rc=num(a,'rho'),num(c,'rho'); sa=int(ra<1); sc=int(rc<1); ca=int(abs(ra-1)<=1e-8); cc=int(abs(rc-1)<=1e-8); badclass+=int((sa,ca)!=(sc,cc))
   pmax=max(pmax,num(a,'max_state_matrix_relative_residual','maximum_state_eigenpair_residual'),num(a,'max_polynomial_relative_residual','maximum_polynomial_relative_residual'),num(c,'max_state_matrix_relative_residual','maximum_state_eigenpair_residual'),num(c,'max_polynomial_relative_residual','maximum_polynomial_relative_residual'))
   AA,BB,g=independent_contract(b,l,j); gmax=max(gmax,probe_error(b,l,j,AA,BB))
   ga=np.array([num(a,'delay_line_gamma_1','delay_channel_1_register_scale'),num(a,'delay_line_gamma_2','delay_channel_2_register_scale')]); gc=np.array([num(c,'delay_line_gamma_1','delay_channel_1_register_scale'),num(c,'delay_line_gamma_2','delay_channel_2_register_scale')]);
   gd=max(np.max(np.abs(ga-g)/np.maximum(np.abs(g),np.finfo(float).eps)),np.max(np.abs(gc-g)/np.maximum(np.abs(g),np.finfo(float).eps)))
   detail.append(dict(bundle_id=k[0],point_id=k[1],expected_root_count=want,hungarian_normalized_max=dist,rho_abs_difference=rd,gamma_max_relative_difference=gd))
  gate('物理根数',badcount==0,f'{totalroots}根/{badcount}异常','18728根/0异常'); gate('Hungarian全物理根',imax<=ROOT_TOL,f'{totalroots}根,max={imax}',ROOT_TOL); gate('rho差',rmax<=RHO_TOL,f'312点,max={rmax}',RHO_TOL); gate('稳定_临界分类',badclass==0,f'312点/{badclass}异常',0); gate('状态_多项式残差',pmax<=RES_TOL,f'312点,max={pmax}',RES_TOL); gate('复数探针行列式等价',gmax<=PROBE_TOL,f'{312*len(PROBES)}探针,max={gmax}',PROBE_TOL); gate('gamma独立重算',max(float(x['gamma_max_relative_difference']) for x in detail)<=1e-12,f'624通道,max={max(float(x["gamma_max_relative_difference"]) for x in detail)}',1e-12)
  me=rows(MROOT/'MATLAB两轮确定性证据.csv'); pe=rows(PROOT/'步骤8D_Python双轮逐字节确定性证据.csv')
  mfields=('main_script_sha256','point_csv_sha256','normalized_scientific_array_sha256','actual_result_count','point_csv_pass_count','point_csv_fail_count','stable_point_count','critical_point_count','unstable_point_count','maximum_state_matrix_relative_residual','maximum_polynomial_relative_residual','minimum_physical_root_magnitude','minimum_minimal_augmented_order','maximum_minimal_augmented_order','minimum_delay_line_gamma','maximum_delay_line_gamma')
  mok=len(me)==2 and all(me[0][f].lower()==me[1][f].lower() for f in mfields) and all(r['mat_contract_matches_summary']=='1' and r['point_csv_matches_summary_count']=='1' and r['all_points_pass']=='1' for r in me)
  pok=len(pe)==7 and all(r.get('equal','')=='1' and r['round1_sha256']==r['round2_sha256'] and r['round1_bytes']==r['round2_bytes'] for r in pe)
  gate('两轮确定性证据',mok and pok,f'MATLAB={len(me)}轮,Python={len(pe)}工件','MATLAB=2轮且Python=7/7 equal')
 except Exception as e:
  gate('验证器执行',False,type(e).__name__+': '+str(e),'no exception')
 with (OUT/'逐点跨实现诊断.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(detail[0]) if detail else ['bundle_id']); w.writeheader(); w.writerows(detail)
 with (OUT/'门禁结果.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=['gate','status','value','limit']); w.writeheader(); w.writerows(checks)
 ok=all(x['status']=='PASS' for x in checks); summary={'status':'PASS' if ok else 'FAIL','checks':checks,'probe_angles_radian':[.173,.419,.731,1.087,1.533,2.071,2.617,2.941],'probe_revision_note':'首轮非单位模探针在高时滞点因 |z|**m0 下溢造成假FAIL；改用预声明单位圆非实探针，等价式和1e-8门限未变。','validator_sha256':sha(HERE)}
 (OUT/'验证摘要.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 (OUT/'独立验证报告.md').write_text('# 步骤8D独立验证\n\n- 结论：`'+summary['status']+'`\n- 探针修订：'+summary['probe_revision_note']+'\n\n'+'\n'.join(f"- {x['gate']}：{x['status']}（{x['value']} / {x['limit']}）" for x in checks)+'\n',encoding='utf-8')
 arts=[HERE,OUT/'逐点跨实现诊断.csv',OUT/'门禁结果.csv',OUT/'验证摘要.json',OUT/'独立验证报告.md']
 with (OUT/'验证工件SHA256清单.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.writer(f); w.writerow(['path','sha256']); [w.writerow([str(p.relative_to(BOARD)),sha(p)]) for p in arts]
 return 0 if ok else 1
if __name__=='__main__': sys.exit(main())
