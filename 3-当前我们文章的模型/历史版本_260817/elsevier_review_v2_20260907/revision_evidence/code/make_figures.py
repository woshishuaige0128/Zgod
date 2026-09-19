from pathlib import Path
import json,csv,hashlib,shutil,os,tempfile
import numpy as np
from scipy.io import loadmat,savemat
from scipy.linalg import eig
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

ROOT=Path(__file__).resolve().parents[2]
TMP=Path(__file__).resolve().parent
NEW=ROOT.parent/'260817/elsevier_review_v2_20260907'
if Path(__file__).resolve().parent.name=='code' and Path(__file__).resolve().parent.parent.name=='revision_evidence':
    NEW=Path(__file__).resolve().parents[2]
    TMP=Path(tempfile.gettempdir())/'rths_review_v2_figure_build';TMP.mkdir(exist_ok=True)
OUT=NEW/'submit_figure'; DATA=NEW/'revision_evidence/data'
SOURCE=ROOT.parent/'260817/code/导师现场MATLAB全链演示_Fig06至Fig09'
plt.rcParams.update({'text.usetex':True,'font.family':'serif','font.serif':['Computer Modern Roman'],'font.size':9,'axes.labelsize':9,'xtick.labelsize':9,'ytick.labelsize':9,'legend.fontsize':9,'xtick.direction':'in','ytick.direction':'in','xtick.top':True,'ytick.right':True,'axes.linewidth':.8,'lines.linewidth':1.2,'lines.markersize':4,'legend.frameon':False,'axes.grid':False,'savefig.dpi':600,'savefig.bbox':'tight','savefig.pad_inches':.03})
COL={'Full':'#555555','Guyan':'#4477AA','CB':'#EE6677'}
LS={'Full':'--','Guyan':'-.','CB':'-'}
LAB={'Full':'Full order','Guyan':'Guyan','CB':'Craig--Bampton'}
MARK={'Full':'o','Guyan':'^','CB':'s'}
manifest=[];sources=[]; metrics={};matcheck={}

def hashfile(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def source(p):sources.append({'path':str(p),'sha256':hashfile(p)});return p
def writecsv(name,head,rows):
    with (DATA/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(head);w.writerows(rows)
def save(fig,name,purpose,origin):
    for ax in fig.axes:
        ax.tick_params(which='both',direction='in',top=True,right=True)
        if not getattr(ax,'_fixed_x',False):ax.xaxis.set_major_locator(MaxNLocator(5))
        if not getattr(ax,'_fixed_y',False):ax.yaxis.set_major_locator(MaxNLocator(5))
    fig.savefig(OUT/(name+'.pdf'),metadata={'CreationDate':None,'ModDate':None})
    fig.savefig(OUT/(name+'.png'),dpi=600)
    plt.close(fig)
    manifest.append({'file':name,'purpose':purpose,'source':origin,'pdf_sha256':hashfile(OUT/(name+'.pdf')),'png_sha256':hashfile(OUT/(name+'.png'))})
def panel(ax,label):ax.text(.025,.96,label,transform=ax.transAxes,va='top',ha='left')

# Read the verified, full-chain time histories without rerunning or editing sources.
hist={}
for num,div,exc in [(6,1,'eq'),(7,2,'eq'),(8,1,'chirp'),(9,2,'chirp')]:
    local=NEW/'supplementary_data'/f'response_division_{div}_{exc}.csv'
    if local.exists():p=source(local)
    else:
        folder=next(SOURCE.glob(f'Fig{num:02d}_*'))
        p=source(next((folder/'输出/本轮计算数据').glob('*本轮全链计算响应.csv')))
    a=np.loadtxt(p,delimiter=',',skiprows=1)
    assert a.shape==(40961,10) and np.isfinite(a).all()
    hist[div,exc]=a; matcheck[f'response_{div}_{exc}']=a
    if p.resolve()!=local.resolve():shutil.copy2(p,local)

modal={};share={};freqrows=[];shaperows=[];sharerows=[]
for div in [1,2]:
    d=loadmat(source(NEW/'supplementary_data'/f'division_{"I"*div}_matrices.mat'))
    M=d['M_full'];order=np.r_[d['master_dofs'].ravel(),d['slave_dofs'].ravel()].astype(int)-1
    influence=np.zeros(15);influence[[0,5,10]]=1
    for key,tag in [('Full','full'),('Guyan','guyan'),('CB','cb')]:
        values,V=eig(d['K_'+tag],d['M_'+tag]);idx=np.argsort(values.real)
        values=values[idx];V=V[:,idx].real; assert max(abs(values.imag))<1e-7
        freq=np.sqrt(values.real)/(2*np.pi)
        if key!='Full':
            W=np.empty((15,V.shape[1]));W[order,:]=d['T_'+tag]@V;V=W
        V=V/np.sqrt(np.sum(V*(M@V),axis=0))
        # Common physical mass normalisation after expansion. Sign only affects display.
        V*=np.where(V[10,:]>=0,1,-1)
        modal[div,key]=(freq,V)
        gamma=V[:,:5].T@M@influence;weights=gamma**2/sum(gamma**2)
        E=(np.diag(M)[:,None]*V[:,:5]**2)@weights
        assert abs(sum(E)-1)<1e-12
        share[div,key]=E
        for i in range(min(5,len(freq))):freqrows.append([div,key,i+1,freq[i]])
        for mode in [0,1]:
            shapes=V[[0,5,10],mode]/max(abs(V[[0,5,10],mode]))
            for floor,x in enumerate(shapes,1):shaperows.append([div,key,mode+1,floor,x])
        for j,e in enumerate(E,1):sharerows.append([div,key,j,e])
        matcheck[f'share_{div}_{tag}']=E
        matcheck[f'freq_{div}_{tag}']=freq
    if div==1:
        f,V=modal[div,'Full'];gam=V.T@M@influence
        metrics['full_first_five_hz']=f[:5].tolist()
        metrics['first_five_effective_mass_fraction']=float(sum(gam[:5]**2)/(influence@M@influence))
        metrics['mass_diagonal']=np.diag(M).tolist()
        metrics['rayleigh_coefficients']=np.linalg.lstsq(np.c_[M.flatten(),d['K_full'].flatten()],d['C_full'].flatten(),rcond=None)[0].tolist()
writecsv('new_modes_frequencies.csv',['division','method','mode','frequency_hz'],freqrows)
writecsv('new_horizontal_modes.csv',['division','method','mode','floor','normalised_displacement'],shaperows)
writecsv('new_modal_shares.csv',['division','method','physical_dof','share'],sharerows)

# Input histories. Units are those of the source state-space input (m/s^2).
t=hist[1,'eq'][:,0]
eqfile=NEW/'supplementary_data/EQ.mat'
if not eqfile.exists():shutil.copy2(next(SOURCE.glob('Fig06_*'))/'输入模型与参数/EQ.mat',eqfile)
source(eqfile)
eq=loadmat(eqfile);raw=eq['ElCentroAccel'];keep=raw[0]<=40
ag=np.interp(t,raw[0,keep],.4*raw[1,keep]);chirp=np.sin(2*np.pi*.1*t+np.pi*9.9/40*t*t)
writecsv('new_excitation.csv',['time_s','elcentro_scaled_m_s2','chirp_m_s2','chirp_hz'],zip(t,ag,chirp,.1+.2475*t))
metrics['peak_input_acceleration_m_s2']=float(max(abs(ag)))
fig,axes=plt.subplots(2,1,figsize=(7.48,3.9),layout='constrained')
for ax,y,letter in zip(axes,[ag,chirp],['(a) El Centro, scale 0.40','(b) Linear chirp, 0.1--10 Hz']):
    ax.plot(t,y,color=COL['Full'],lw=.8);ax.set(xlim=(0,40),ylabel=r'Acceleration (m/s$^2$)');panel(ax,letter)
    lo,hi=ax.get_ylim();ax.set_ylim(lo,hi+.22*(hi-lo))
axes[-1].set_xlabel('Time (s)')
save(fig,'fig11_excitation','说明实际输入、幅值和扫频覆盖范围','EQ.mat和全链入口第5段')

# Restored horizontal modes, showing actual mode-frequency values beside each curve.
fig,axes=plt.subplots(2,2,figsize=(7.48,5.15),layout='constrained')
for row,div in enumerate([1,2]):
    for mode in [0,1]:
        ax=axes[row,mode]
        for key in ['Full','Guyan','CB']:
            f,V=modal[div,key];x=V[[0,5,10],mode];x=x/max(abs(x))
            ax.plot(np.r_[0,x],np.arange(4),color=COL[key],ls=LS[key],marker=MARK[key],mfc='white',label=f'{LAB[key]}: {f[mode]:.4f} Hz')
        ax.axvline(0,color='#BBBBBB',lw=.6,zorder=0)
        ax.set(xlim=(-1.25,1.25),ylim=(-.15,3.2),xlabel='Normalised horizontal displacement',ylabel='Storey level')
        panel(ax,f'({chr(97+row*2+mode)}) Division {"I"*div}, mode {mode+1}')
        ax.set_yticks([0,1,2,3]);ax._fixed_y=True
        ax.legend(loc='center left' if mode==0 else 'center right',fontsize=9,handlelength=1.4)
save(fig,'fig12_horizontal_modes','同时展示实际频率和恢复后三层水平振型','随包M/K/T矩阵的广义特征值求解')

# Middle-storey response and its error at the omitted horizontal coordinate.
for exc,num in [('eq',13),('chirp',14)]:
    a=hist[2,exc];x=a[:,4:7];ref=x[:,0];err=x[:,1:]-ref[:,None]
    vals=np.sqrt(np.trapezoid(err**2,t,axis=0)/40)/np.ptp(ref)*100
    metrics['middle_'+exc+'_nrmse_percent']=vals.tolist()
    writecsv(f'new_middle_{exc}.csv',['time_s','full_mm','guyan_mm','cb_mm','guyan_error_mm','cb_error_mm'],np.c_[t,x,err])
    fig,axes=plt.subplots(3,1,figsize=(7.48,5.65),layout='constrained',sharex=True)
    for i,key in enumerate(['Full','Guyan','CB']):axes[0].plot(t,x[:,i],color=COL[key],ls=LS[key],label=LAB[key],lw=1)
    axes[0].legend(ncol=3,loc='upper right');axes[0].set_ylabel('Displacement (mm)');panel(axes[0],r'(a) Middle storey, $\psi_6$')
    for i,key in enumerate(['Guyan','CB']):
        axes[i+1].plot(t,err[:,i],color=COL[key],ls=LS[key],lw=.9)
        axes[i+1].axhline(0,color='#BBBBBB',lw=.5,zorder=0)
        axes[i+1].set_ylabel('Error (mm)')
        panel(axes[i+1],f'({chr(98+i)}) {LAB[key]}, NRMSE = {vals[i]:.3f}\\%')
    axes[-1].set(xlim=(0,40),xlabel='Time (s)')
    for ax in axes:
        lo,hi=ax.get_ylim();ax.set_ylim(lo,hi+.22*(hi-lo))
    save(fig,f'fig{num}_middle_{exc}','直接检验第二种划分中被消去的中间楼层水平坐标','第二类划分全链CSV第5至7列；误差=缩聚响应-完整响应')

# Peak interstorey drift measures shape fidelity, not just each floor's response amplitude.
driftrows=[]
fig,axes=plt.subplots(2,2,figsize=(7.48,5.05),layout='constrained')
for row,exc in enumerate(['eq','chirp']):
    for col,div in enumerate([1,2]):
        a=hist[div,exc];ax=axes[row,col]
        for method,key in enumerate(['Full','Guyan','CB']):
            x=a[:,[1+method,4+method,7+method]]
            drift=np.diff(np.c_[np.zeros(len(t)),x],axis=1)/635*100
            peaks=np.max(abs(drift),axis=0)
            for floor,value in enumerate(peaks,1):driftrows.append([div,exc,key,floor,value])
            ax.plot(peaks,[1,2,3],color=COL[key],ls=LS[key],marker=MARK[key],mfc='white',label=LAB[key])
        ax.set(xlabel=r'Peak interstorey drift (\%)',ylabel='Storey',ylim=(.8,3.2));ax.set_xlim(left=0)
        panel(ax,f'({chr(97+row*2+col)}) Division {"I"*div}, '+('El Centro' if exc=='eq' else 'chirp'))
        ax.set_yticks([1,2,3]);ax._fixed_y=True;ax.set_ylim(.8,3.55)
axes[0,0].legend(loc='center left',fontsize=9)
save(fig,'fig15_peak_drift','从层间相对变形检验响应形状的保真程度','三层水平响应差分除以635 mm层高，再取全时程绝对峰值')
writecsv('new_peak_drift.csv',['division','excitation','method','storey','peak_drift_percent'],driftrows)
metrics['drift_rows']=driftrows
matcheck['drift_values']=np.array([r[-1] for r in driftrows])

# Modal shares and the signed, separately normalised actuator contributions in Delta E.
contributions=[]
fig,axes=plt.subplots(2,2,figsize=(7.48,5.05),layout='constrained',gridspec_kw={'width_ratios':[1.45,1]})
for row,div in enumerate([1,2]):
    acts=[0,5] if div==1 else [0,10];E0=share[div,'Full']
    for key in ['Full','Guyan','CB']:
        axes[row,0].plot(np.arange(1,16),share[div,key],color=COL[key],ls=LS[key],marker=MARK[key],mfc='white',label=LAB[key])
    axes[row,0].set(xlabel=r'Physical coordinate index $j$',ylabel=r'Modal share $E_j$',xlim=(.5,15.5))
    axes[row,0].set_ylim(-.02,.80);axes[row,0].set_xticks([1,3,6,9,12,15]);axes[row,0]._fixed_x=True
    panel(axes[row,0],f'({chr(97+row*2)}) Division {"I"*div}')
    for i,key in enumerate(['Guyan','CB']):
        rel=(share[div,key][acts]-E0[acts])/E0[acts]
        axes[row,1].bar(np.array([0,1])+(i-.5)*.3,rel,width=.28,color=COL[key],edgecolor='white',hatch='//' if key=='Guyan' else None,label=LAB[key])
        for a,v in zip(acts,rel):contributions.append([div,key,a+1,v,float(sum(rel))])
    axes[row,1].axhline(0,color=COL['Full'],lw=.6)
    axes[row,1].set_xticks([0,1],[rf'$\psi_{{{j+1}}}$' for j in acts])
    axes[row,1]._fixed_x=True
    axes[row,1].set(xlabel='Actuated coordinate',ylabel='Relative share change')
    lo,hi=axes[row,1].get_ylim();axes[row,1].set_ylim(lo,hi+.22*(hi-lo))
    panel(axes[row,1],f'({chr(98+row*2)}) Division {"I"*div}')
axes[0,0].legend(loc='upper right',fontsize=9)
# Preserve categorical ticks in this panel after common style application.
save(fig,'fig16_modal_shares','解释模态份额分布和表5两项带符号贡献，而不等同为能量转移','前5阶恢复振型质量归一化；式(4.3)-(4.4)')
writecsv('new_actuator_share_contributions.csv',['division','method','physical_dof','relative_share_change','delta_E'],contributions)
metrics['actuator_share_contributions']=contributions
metrics['section_properties']={'Ac_m2':1.670*.0254**2,'Ab_m2':.947*.0254**2,'Ic_m4':2.520*.0254**4,'Ib_m4':.6132*.0254**4}
metrics['new_numbered_figures']=len(manifest)
assert len(manifest)==6
(DATA/'new_figure_metrics.json').write_text(json.dumps(metrics,ensure_ascii=False,indent=2),encoding='utf-8')
(DATA/'new_figure_manifest.json').write_text(json.dumps({'figures':manifest,'sources':sources},ensure_ascii=False,indent=2),encoding='utf-8')
savemat(TMP/'new_figure_check.mat',matcheck)
if Path(__file__).resolve()!=(NEW/'revision_evidence/code/make_figures.py').resolve():shutil.copy2(__file__,NEW/'revision_evidence/code/make_figures.py')
print(json.dumps(metrics,ensure_ascii=False,indent=2))
print('FIGURES_CREATED=6')
