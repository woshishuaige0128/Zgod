from pathlib import Path
import os,json,csv,subprocess,sys
TMP=Path(__file__).resolve().parent
os.environ['MPLCONFIGDIR']=str(TMP.parent/'temp/plot_cache')
import numpy as np
from scipy.io import loadmat
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator,StrMethodFormatter
from matplotlib.lines import Line2D
CASE=TMP.parent;RUN=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else CASE/'results'
def unpack(x):
    if hasattr(x,'_fieldnames'):return {k:unpack(getattr(x,k)) for k in x._fieldnames}
    if isinstance(x,dict):return {k:unpack(v) for k,v in x.items()}
    if isinstance(x,np.ndarray) and x.dtype==object:
        a=np.empty(x.shape,object)
        for i in np.ndindex(x.shape):a[i]=unpack(x[i])
        return a
    return x
B={v:unpack(loadmat(RUN/v/'calculation.mat',simplify_cells=True)['bundle']) for v in ['legacy','standard']}
plt.rcParams.update({'text.usetex':True,'font.family':'serif','font.serif':['Computer Modern Roman'],'font.size':9,'axes.labelsize':9,'xtick.labelsize':9,'ytick.labelsize':9,'legend.fontsize':9,'xtick.direction':'in','ytick.direction':'in','xtick.top':True,'ytick.right':True,'axes.linewidth':.8,'lines.linewidth':1.2,'lines.markersize':4,'legend.frameon':False,'axes.grid':False,'savefig.dpi':600,'pdf.fonttype':42})
colors=['#555555','#4477AA','#EE6677'];styles=['--','-.','-'];marks=['o','^','s'];names=['Full order','Guyan','Craig--Bampton']
handles=[Line2D([],[],color=colors[j],ls=styles[j],marker=marks[j],mfc='white',label=names[j]) for j in range(3)]
curve_manifest=[]
def pad(a,top=.15):
    a=np.asarray(a);lo=float(a.min());hi=float(a.max());span=max(hi-lo,1e-8);return lo-.06*span,hi+top*span
def axis(ax):
    ax.tick_params(direction='in',top=True,right=True);ax.xaxis.set_major_locator(MaxNLocator(5));ax.yaxis.set_major_locator(MaxNLocator(5))
def label(ax,c):ax.text(-.085,1.025,f'({c})',transform=ax.transAxes,va='bottom')
def curves(ax,t,x,markers=False):
    for j in [0,1,2]:
        ax.plot(t,x[:,j],color=colors[j],ls=styles[j],lw=1.05,marker=marks[j] if markers else None,markevery=max(1,len(t)//9),mfc='white',ms=3.7)
def data(v,d,ex):return np.loadtxt(RUN/v/f'division{d}_{ex}/response.csv',delimiter=',',skiprows=1)
D={(v,d,ex):data(v,d,ex) for v in B for d in [1,2] for ex in ['eq','chirp']}
def errors(v,d,ex,storey):
    a=D[v,d,ex];idx=1+3*(storey-1);return a[:,idx+1:idx+3]-a[:,idx,None]
def metric(v,name):return list(csv.DictReader((RUN/v/f'metric_{name}.csv').open(encoding='utf-8-sig')))
def shares(v,d):return np.column_stack([B[v]['modes'][d-1,j]['shares'] for j in range(3)])
def deviations(v,d):
    a=shares(v,d);ids=[0,5] if d==1 else [0,10];return abs((a[ids,1:]-a[ids,0,None])/a[ids,0,None])
def create(n,v):
    b=B[v]
    if n==5:
        fig,axs=plt.subplots(2,1,figsize=(7.48,3.8));fig.subplots_adjust(left=.10,right=.99,bottom=.13,top=.94,hspace=.26)
        t=b['inputs']['time'];vals=[b['inputs']['eq_on_grid'],b['inputs']['chirp'][:,1]]
        for k,ax in enumerate(axs):
            ax.plot(t,vals[k],color=colors[1],lw=.8);axis(ax);ax.set(xlim=(0,40),ylim=pad(vals[k],.1),ylabel=r'Acceleration (m/s$^2$)');ax.set_xticks(np.arange(0,41,8));label(ax,chr(97+k))
        axs[-1].set_xlabel('Time (s)')
    elif n==6:
        fig,axs=plt.subplots(1,4,figsize=(7.48,3.55));fig.subplots_adjust(left=.06,right=.99,bottom=.15,top=.88,wspace=.13)
        for k,ax in enumerate(axs):
            d=k//2;mode=k%2;axis(ax)
            for j in range(3):ax.plot(np.r_[0,b['modes'][d,j]['horizontal'][:,mode]],np.arange(4),color=colors[j],ls=styles[j],marker=marks[j],mfc='white')
            ax.axvline(0,color='.75',lw=.6,zorder=0);ax.set(xlim=(-1.18,1.18),ylim=(-.12,3.48));ax.set_xticks([-1,-.5,0,.5,1]);ax.set_yticks([0,1,2,3]);label(ax,chr(97+k))
            if k==0:ax.set_ylabel('Storey level')
            else:ax.set_yticklabels([])
            freq=[b['modes'][d,j]['frequency_hz'][mode] for j in range(3)]
            text=r'$f$ (Hz)'+'\n'+f'Full {freq[0]:.4f}\nGuyan {freq[1]:.4f}\nCB {freq[2]:.4f}'
            ax.text(.04 if mode==0 else .45,.57 if mode==0 else .095,text,transform=ax.transAxes,va='top' if mode==0 else 'bottom',fontsize=9)
        fig.legend(handles=handles,loc='upper center',ncol=3,bbox_to_anchor=(.5,1.02));fig.supxlabel('Normalised horizontal displacement',y=.015,fontsize=9)
    elif n in [7,8,10,11]:
        d=1 if n in [7,10] else 2;ex='eq' if n<10 else 'chirp';a=D[v,d,ex];t=a[:,0]
        windows=[(10,11),(21.5,22.5)] if ex=='eq' else [(13,14),(38,38.3)]
        fig,axs=plt.subplots(2,3,figsize=(7.48,4.6),gridspec_kw={'width_ratios':[2.4,1,1]});fig.subplots_adjust(left=.085,right=.99,bottom=.11,top=.90,wspace=.40,hspace=.28)
        for row,floor in enumerate([1,3]):
            x=a[:,1+3*(floor-1):4+3*(floor-1)]
            for col in range(3):
                ax=axs[row,col];window=(0,40) if col==0 else windows[col-1];mask=(t>=window[0])&(t<=window[1]);ids=np.where(mask)[0]
                if col==0:ids=np.unique(np.r_[ids[::6],ids[-1]])
                curves(ax,t[ids],x[ids],col>0);axis(ax);ax.set_xlim(window)
                values=np.concatenate([D[w,d,ex][mask,1+3*(floor-1):4+3*(floor-1)] for w in B]);ax.set_ylim(pad(values,.12))
                if col==0:ax.set_ylabel('Displacement (mm)');ax.set_xticks(np.arange(0,41,8));label(ax,chr(97+row))
                else:ax.set_xticks([window[0],sum(window)/2,window[1]]);ax.xaxis.set_major_formatter(StrMethodFormatter('{x:g}'))
                if row==1:ax.set_xlabel('Time (s)')
        fig.legend(handles=handles,loc='upper center',ncol=3,bbox_to_anchor=(.5,1.005))
    elif n in [9,12]:
        ex='eq' if n==9 else 'chirp';a=D[v,2,ex];t=a[:,0];x=a[:,4:7];e=x[:,1:]-x[:,0,None]
        fig,axs=plt.subplots(3,1,figsize=(7.48,5.45));fig.subplots_adjust(left=.105,right=.99,bottom=.10,top=.955,hspace=.19)
        vals=[x,e[:,0],e[:,1]]
        for k,ax in enumerate(axs):
            axis(ax);ax.set_xlim(0,40);ax.set_xticks(np.arange(0,41,8));label(ax,chr(97+k))
            if k==0:
                curves(ax,t[::3],x[::3]);ax.set_ylabel('Displacement (mm)');ax.legend(handles=handles,loc='upper right',ncol=3)
                combined=np.concatenate([D[w,2,ex][:,4:7].ravel() for w in B])
            else:
                ax.plot(t,vals[k],color=colors[k],ls=styles[k],lw=.85);ax.axhline(0,color='.7',lw=.5);ax.set_ylabel('Error (mm)')
                combined=np.concatenate([errors(w,2,ex,2)[:,k-1] for w in B])
            ax.set_ylim(pad(combined,.18))
            if k<2:ax.set_xticklabels([])
        axs[-1].set_xlabel('Time (s)')
    elif n==13:
        fig,axs=plt.subplots(1,4,figsize=(7.48,3.55));fig.subplots_adjust(left=.065,right=.99,bottom=.16,top=.88,wspace=.15)
        for k,ax in enumerate(axs):
            d=k%2+1;ex=k//2+1;axis(ax)
            for j in [1,2,3]:
                rows=[r for r in metric(v,'drifts') if int(r['division'])==d and int(r['excitation'])==ex and int(r['method'])==j]
                ax.plot([float(r['peak_drift_percent']) for r in rows],[1,2,3],color=colors[j-1],ls=styles[j-1],marker=marks[j-1],mfc='white')
            ax.set(ylim=(.8,3.45),xlim=(0,.92 if ex==1 else 2.65));ax.set_yticks([1,2,3]);label(ax,chr(97+k))
            if k==0:ax.set_ylabel('Storey')
            else:ax.set_yticklabels([])
        fig.legend(handles=handles,loc='upper center',ncol=3,bbox_to_anchor=(.5,1.02));fig.supxlabel(r'Peak interstorey drift (\%)',y=.012,fontsize=9)
    elif n==15:
        fig,axs=plt.subplots(2,2,figsize=(7.48,5.15),gridspec_kw={'width_ratios':[1.5,1]});fig.subplots_adjust(left=.085,right=.985,bottom=.105,top=.96,wspace=.29,hspace=.32)
        for d in [1,2]:
            ax=axs[d-1,0];s=shares(v,d)
            for j in range(3):ax.plot(np.arange(1,16),s[:,j],color=colors[j],ls=styles[j],marker=marks[j],mfc='white')
            axis(ax);ax.set(xlim=(.5,15.5),ylim=(-.02,.8),xlabel=r'Physical coordinate index $j$',ylabel=r'Weighted fraction $E_j$');ax.set_xticks([1,3,6,9,12,15]);label(ax,chr(97+2*(d-1)))
            if d==1:ax.legend(handles=handles,loc='upper left')
            ax=axs[d-1,1];dev=deviations(v,d)
            for j in range(2):ax.bar(np.arange(2)+(j-.5)*.32,dev[:,j],.32,color=colors[j+1],hatch='//' if j==0 else '',edgecolor='white',lw=.7)
            axis(ax);ax.set(xlim=(-.6,1.6),ylim=(0,max(deviations(w,d).max() for w in B)*1.25),ylabel='Absolute relative deviation',xlabel='Actuated coordinate')
            ax.set_xticks([0,1],[r'$\psi_1$',r'$\psi_6$' if d==1 else r'$\psi_{11}$']);label(ax,chr(98+2*(d-1)))
    else:raise ValueError(n)
    return fig
selected=[int(x) for x in os.environ.get('PLOT_FIGURES','5,6,7,8,9,10,11,12,13,15').split(',')]
if (CASE/'results/plot_data.json').exists():
    curve_manifest=[p for p in json.loads((CASE/'results/plot_data.json').read_text('utf-8')) if p['figure'] not in selected]
for v in ['legacy','standard']:
    folder=CASE/'figures'/('legacy_same_scale' if v=='legacy' else 'standard');folder.mkdir(exist_ok=True,parents=True)
    for n in selected:
        fig=create(n,v);base=folder/f'fig{n:02d}'
        axes_data=[]
        for ai,ax in enumerate(fig.axes):
            curves_data=[{'x':np.asarray(l.get_xdata(),float).tolist(),'y':np.asarray(l.get_ydata(),float).tolist()} for l in ax.lines]
            bars_data=[{'x':r.get_x(),'height':r.get_height(),'width':r.get_width()} for r in ax.patches]
            axes_data.append({'xlim':list(ax.get_xlim()),'ylim':list(ax.get_ylim()),'lines':curves_data,'bars':bars_data})
        fig.savefig(str(base)+'.pdf',bbox_inches='tight',pad_inches=.035)
        subprocess.run(['pdftoppm','-png','-r','600','-singlefile',str(base)+'.pdf',str(base)],check=True,capture_output=True)
        plt.close(fig);curve_manifest.append({'variant':v,'figure':n,'axes':axes_data})
        print(f'PLOTTED {v} figure {n}',flush=True)
(CASE/'results/plot_data.json').write_text(json.dumps(curve_manifest,separators=(',',':')),'utf-8')
print('ALL_FIGURES_SAVED',flush=True)
