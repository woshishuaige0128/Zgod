"""Independent numerical audit of the current manuscript against current plot data.

The acceptance criterion is manuscript display precision, never fitted values.
Primary chirp bands are the literal Table 4 labels; alternative prose conventions
are evaluated separately and cannot replace the primary result to chase a match.
"""
from pathlib import Path
import csv, hashlib, json, re
import numpy as np
from scipy.io import loadmat
from scipy.linalg import eig

OUT=Path(__file__).resolve().parents[1]
ROOT=OUT.parents[1]
PAPER=ROOT.parent/'260817'

def write_csv(name, rows):
    p=OUT/'results'/name
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def modes(M,K):
    w,V=eig(K,M)
    assert np.max(np.abs(w.imag))<1e-7
    ix=np.argsort(w.real);w=w[ix].real;V=V[:,ix].real
    assert np.all(w>0)
    residual=np.linalg.norm(K@V-(M@V)*w,axis=0)/((np.linalg.norm(K)+np.abs(w)*np.linalg.norm(M))*np.linalg.norm(V,axis=0))
    assert np.max(residual)<1e-12
    return np.sqrt(w)/2/np.pi,V,float(max(residual))

def shares(V,M):
    V=V[:,:5].copy()
    V/=np.sqrt(np.sum(V*(M@V),axis=0))
    influence=np.zeros(15);influence[[0,5,10]]=1
    gamma=(V.T@M@influence)/np.sum(V*(M@V),axis=0)
    weights=gamma**2/np.sum(gamma**2)
    coordinate=np.diag(M)[:,None]*V**2
    coordinate/=coordinate.sum(axis=0)
    E=coordinate@weights
    assert abs(E.sum()-1)<1e-12
    return E,weights

def nrmse(a, start,end, method):
    t=a[:,0];ref=a[:,1];error=ref-a[:,method+1]
    # Include the exact non-grid band endpoints by linear interpolation.
    tt=np.r_[start,t[(t>start)&(t<end)],end]
    err=np.interp(tt,t,error)
    return float(np.sqrt(np.trapezoid(err**2,tt)/(end-start))/np.ptp(ref)*100)

def parse_manuscript():
    tex=(OUT/'evidence/main_source_readonly.tex').read_text(encoding='utf-8-sig')
    blocks=re.findall(r'\\begin\{table\}.*?\\end\{table\}',tex,re.S)
    assert len(blocks)==5
    result=[]
    # Extract only explicitly numeric body rows from the exact source tables.
    for line in blocks[2].splitlines():
        if re.match(r'\s*(I|II)\s*&\s*[12]\s*&',line):
            x=[v.strip().rstrip('\\').strip() for v in line.split('&')]
            d=1 if x[0]=='I' else 2;m=int(x[1])
            for j,(metric,method,decimals) in enumerate([('频率误差(%)','Guyan',3),('频率误差(%)','Craig–Bampton',3),('MAC','Guyan',4),('MAC','Craig–Bampton',4)]):
                result.append(dict(table=3,division=d,item=f'第{m}阶',metric=metric,method=method,reported=x[j+2],decimals=decimals,mode=m))
    for rowno,line in enumerate([s for s in blocks[3].splitlines() if re.match(r'\s*(El Centro|Chirp,)',s)]):
        x=[v.strip().rstrip('\\').strip().replace('$','') for v in line.split('&')]
        for j in range(4):
            result.append(dict(table=4,division=1+j//2,item=x[0].replace('--','–'),metric='首层NRMSE(%)',method=['Guyan','Craig–Bampton'][j%2],reported=x[j+1],decimals=3,row=rowno))
    for line in blocks[4].splitlines():
        if re.match(r'\s*(I|II)\s*&',line):
            x=[v.strip().rstrip('\\').strip() for v in line.split('&')]
            for j in range(2):
                result.append(dict(table=5,division=1 if x[0]=='I' else 2,item='前5阶/两作动坐标',metric='模态重分配比',method=['Guyan','Craig–Bampton'][j],reported=x[j+1],decimals=4))
    assert len(result)==44
    return result

def main():
    config=json.loads((OUT/'evidence/runtime_derivation.json').read_text(encoding='utf-8'))
    data={}
    source_comparisons=[]
    for c in config:
        p=Path(c['runtime'])/'输出/本轮计算数据/audit_snapshot.mat'
        assert p.exists(),p
        d=loadmat(p);data[c['figure']]=d
        a=d['computed_matrix'];assert a.shape==(40961,10)
        assert np.max(np.abs(np.diff(a[:,0])-1/1024))<1e-14
        assert a[0,0]==0 and a[-1,0]==40 and np.all(np.isfinite(a))
        original=Path(c['source'])
        ref=next((original/'参考结果_仅用于末端验收').glob('*.csv'))
        plotted=PAPER/'figure/results_v2/输入数据'/ref.name
        b=np.loadtxt(plotted,delimiter=',',skiprows=1)
        error=float(np.max(np.abs(a-b)))
        assert error<=1e-12
        source_comparisons.append(dict(figure=c['figure'],fresh_snapshot=str(p),plotted_csv=str(plotted),shape=str(a.shape),maximum_absolute_difference_mm=error,comparison='PASS',csv_sha256=hashlib.sha256(plotted.read_bytes()).hexdigest()))
    numeric={};modal_rows=[];energy_rows=[];dim_rows=[]
    for division,fig in [(1,'Fig06'),(2,'Fig07')]:
        d=data[fig];M=d['M_full'];K=d['K_full'];master=d['master_dofs'].ravel().astype(int)-1
        order=np.r_[master,d['slave_dofs'].ravel().astype(int)-1]
        f,V,residual=modes(M,K);E0,p0=shares(V,M)
        acts=[0,5] if division==1 else [0,10]
        dim_rows.append(dict(division=division,full=15,guyan=len(master),craig_bampton=d['M_cb'].shape[0],master_dofs=','.join(str(x+1) for x in master),actuated_dofs=','.join(str(x+1) for x in acts),full_frequencies_hz=','.join(f'{x:.12f}' for x in f[:5])))
        for method,key in [('Guyan','guyan'),('Craig–Bampton','cb')]:
            fr,Vr,rr=modes(d['M_'+key],d['K_'+key])
            full=np.empty((15,len(fr)));full[order,:]=d['T_'+key]@Vr
            Er,pr=shares(full,M)
            de=float(np.sum((Er[acts]-E0[acts])/E0[acts]));numeric[(5,division,method)]=de
            for i in range(15):
                energy_rows.append(dict(division=division,method=method,physical_dof=i+1,actuated=i in acts,full_share=E0[i],reduced_share=Er[i],relative_change=(Er[i]-E0[i])/E0[i],delta_E=de))
            for mode in range(2):
                a=V[master,mode];b=Vr[:len(master),mode]
                mac=float((a@b)**2/((a@a)*(b@b)))
                ferr=float(abs(fr[mode]-f[mode])/f[mode]*100)
                numeric[(3,division,mode+1,method,'频率误差(%)')]=ferr
                numeric[(3,division,mode+1,method,'MAC')]=mac
                modal_rows.append(dict(division=division,method=method,mode=mode+1,full_hz=f[mode],reduced_hz=fr[mode],frequency_error_percent=ferr,MAC=mac,full_eigen_residual=residual,reduced_eigen_residual=rr))
    edge_policies={'表4标签':np.array([.1,1.9,3.5,5.4,8.1,10]),
                   '正文倍频_2.7Hz':np.r_[.1,np.array([.7,1.3,2,3])*2.7,10],
                   '正文倍频_当前实算基频':np.r_[.1,np.array([.7,1.3,2,3])*f[0],10]}
    sensitivity=[]
    for division in [1,2]:
        for row in range(6):
            a=data[('Fig06' if division==1 else 'Fig07') if row==0 else ('Fig08' if division==1 else 'Fig09')]['computed_matrix']
            for method_index,method in enumerate(['Guyan','Craig–Bampton'],1):
                for policy,edges in edge_policies.items():
                    lo,hi=(0.,40.) if row==0 else ((edges[row-1]-.1)/.2475,(edges[row]-.1)/.2475)
                    val=nrmse(a,lo,hi,method_index)
                    mask=(a[:,0]>=lo)&(a[:,0]<=hi)
                    mean_val=float(np.sqrt(np.mean((a[mask,1]-a[mask,method_index+1])**2))/np.ptp(a[:,1])*100)
                    sensitivity.append(dict(division=division,row=row,method=method,band_policy=policy,start_s=lo,end_s=hi,integral_nrmse_percent=val,sample_mean_nrmse_percent=mean_val,full_record_range_mm=np.ptp(a[:,1])))
                    if policy=='表4标签':numeric[(4,division,row,method)]=val
    rows=parse_manuscript()
    result=[]
    for i,r in enumerate(rows,1):
        if r['table']==3:key=(3,r['division'],r['mode'],r['method'],r['metric'])
        elif r['table']==4:key=(4,r['division'],r['row'],r['method'])
        else:key=(5,r['division'],r['method'])
        value=numeric[key];display=f"{value:.{r['decimals']}f}"
        reported=r['reported'];bound=reported.startswith('<')
        passed=value<float(reported[1:]) if bound else display==f"{float(reported):.{r['decimals']}f}"
        result.append(dict(id=i,table=r['table'],division=r['division'],item=r['item'],metric=r['metric'],method=r['method'],manuscript_value=reported,recomputed=value,rounded_value=('<0.001' if bound and passed else display),difference=None if bound else value-float(reported),status='相符' if passed else '不符'))
    write_csv('逐单元格核查_44项.csv',result)
    write_csv('表3_完整模态指标.csv',modal_rows)
    write_csv('表4_频段边界与积分方式敏感性.csv',sensitivity)
    write_csv('表5_15个物理坐标模态份额.csv',energy_rows)
    write_csv('当前出图模型与参数.csv',dim_rows)
    write_csv('本轮仿真与当前绘图数据比较.csv',source_comparisons)
    summary={str(k):{'total':sum(r['table']==k for r in result),'matched':sum(r['table']==k and r['status']=='相符' for r in result)} for k in [3,4,5]}
    (OUT/'results/python_results.json').write_text(json.dumps(dict(summary=summary,rows=result,models=dim_rows,source_comparisons=source_comparisons),ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False))
    print(json.dumps(modal_rows,ensure_ascii=False))
    print('NUMERICAL_AUDIT_COMPUTATION=PASS (table agreement is reported separately)')

if __name__=='__main__':main()
