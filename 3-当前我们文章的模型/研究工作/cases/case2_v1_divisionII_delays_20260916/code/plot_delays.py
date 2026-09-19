"""Render every selected physical-output response without resimulation."""
import os,json,csv,subprocess,hashlib,sys
from pathlib import Path
os.environ['MPLCONFIGDIR']=str(Path(__file__).resolve().parents[1]/'temp/mplconfig')
import numpy as np
import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator,ScalarFormatter
from matplotlib.colors import TwoSlopeNorm
from delay_model import CASE,DT

OUT=CASE/'figures';OUT.mkdir(exist_ok=True)
mpl.rcParams.update({'text.usetex':True,'font.family':'serif','font.serif':['Computer Modern Roman'],'font.size':9,
 'axes.labelsize':9,'xtick.labelsize':9,'ytick.labelsize':9,'legend.fontsize':9,'axes.linewidth':.8,
 'lines.linewidth':1.05,'lines.markersize':3.5,'xtick.direction':'in','ytick.direction':'in','xtick.top':True,
 'ytick.right':True,'legend.frameon':False,'axes.grid':False,'figure.constrained_layout.use':True,
 'savefig.dpi':600,'savefig.bbox':'tight','savefig.pad_inches':.03})
NAMES=['Full15','Uncondensed19','Guyan6','CB12']
COLORS={'Full15':'#228833','Uncondensed19':'#666666','Guyan6':'#4477AA','CB12':'#EE6677'}
STYLES={'Full15':':','Uncondensed19':'--','Guyan6':'-.','CB12':'-'}
LABELS={'Full15':'Ideal interface, 15 DOFs','Uncondensed19':'Same interface, unreduced','Guyan6':'Guyan','CB12':'Craig--Bampton'}
ROWS=json.loads((CASE/'results/selected_delays.json').read_text('utf-8'))
DATA={r['key']:np.load(CASE/'results'/f"{r['key']}_responses.npz") for r in ROWS}
METRICS=list(csv.DictReader((CASE/'results/response_metrics.csv').open(encoding='utf-8')))
RECORDS=[]

def decorate(ax,xlabel='Time (s)'):
    ax.xaxis.set_major_locator(MaxNLocator(5));ax.yaxis.set_major_locator(MaxNLocator(4));ax.set_xlabel(xlabel)
    ax.tick_params(which='both',direction='in',top=True,right=True)

def write(fig,name,meta):
    pdf=OUT/f'{name}.pdf';fig.savefig(pdf)
    subprocess.run(['pdftoppm','-singlefile','-png','-r','600',str(pdf),str(OUT/name)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    digest=lambda x:hashlib.sha256(np.asarray(x,dtype=np.float64).tobytes()).hexdigest()
    meta.update(name=name,pdf=pdf.name,png=f'{name}.png',axes=[dict(xlim=list(a.get_xlim()),ylim=list(a.get_ylim()),xlabel=a.get_xlabel(),ylabel=a.get_ylabel(),lines=[dict(label=l.get_label(),points=len(l.get_xdata()),x_sha256=digest(l.get_xdata()),y_sha256=digest(l.get_ydata())) for l in a.lines]) for a in fig.axes])
    RECORDS.append(meta);plt.close(fig);print('FIGURE',name,flush=True)

def metric(key,exc,model,floor,field):
    r=next(r for r in METRICS if r['key']==key and r['input']==exc and r['model']==model and int(r['floor'])==floor)
    return float(r[field])

def main():
    global RECORDS
    extra_only='--extra-only' in sys.argv
    if extra_only:RECORDS=json.loads((CASE/'results/figure_records.json').read_text('utf-8'))
    # Shared physical scales across all stable cases; errors are also shared.
    stable=[r for r in ROWS if all(s=='stable' for s in r['status'].values())]
    limits={}
    for exc in ['eq','chirp']:
        for floor in range(3):
            ymax=max(float(np.max(abs(DATA[r['key']][f'{exc}_{n}_physical_mm'][:,floor]))) for r in stable for n in NAMES)
            emax=max(float(np.max(abs(DATA[r['key']][f'{exc}_{n}_physical_mm'][:,floor]-DATA[r['key']][f'{exc}_Uncondensed19_physical_mm'][:,floor]))) for r in stable for n in ['Guyan6','CB12'])
            limits[(exc,floor)]=(1.12*ymax,1.14*emax)
    for row in ROWS:
        if extra_only and any(x.get('key')==row['key'] for x in RECORDS):continue
        key=row['key'];d=DATA[key];t=d['time_s'];unstable=any(s!='stable' for s in row['status'].values())
        for exc in ['eq','chirp']:
            fig,axs=plt.subplots(3,2,figsize=(7.48,4.8),sharex=True,gridspec_kw={'width_ratios':[1.12,1]})
            plotted=[]
            for floor in range(3):
                left,right=axs[floor];ref=d[f'{exc}_Uncondensed19_physical_mm'][:,floor]
                for name in NAMES:
                    vals=d[f'{exc}_{name}_physical_mm'][:,floor]
                    if unstable:
                        left.semilogy(t,np.where(abs(vals)>1e-12,abs(vals),np.nan),color=COLORS[name],ls=STYLES[name],label=LABELS[name],lw=.85)
                    else:left.plot(t,vals,color=COLORS[name],ls=STYLES[name],label=LABELS[name],lw=.85)
                    plotted.append(dict(model=name,output='physical_mm',floor=floor+1,quantity='abs_displacement' if unstable else 'displacement',max_abs=float(np.max(abs(vals)))))
                for name in ['Guyan6','CB12']:
                    err=d[f'{exc}_{name}_physical_mm'][:,floor]-ref
                    if unstable:right.semilogy(t,np.where(abs(err)>1e-12,abs(err),np.nan),color=COLORS[name],ls=STYLES[name],lw=.85)
                    else:right.plot(t,err,color=COLORS[name],ls=STYLES[name],lw=.85)
                    plotted.append(dict(model=name,reference='Uncondensed19',floor=floor+1,quantity='abs_error' if unstable else 'signed_error',max_abs=float(np.max(abs(err)))))
                if not unstable:
                    ymax,emax=limits[(exc,floor)];left.set_ylim(-ymax,ymax);right.set_ylim(-emax,emax);right.axhline(0,color='.75',lw=.5,zorder=0)
                else:
                    left.set_ylim(bottom=1e-3);right.set_ylim(bottom=1e-5)
                left.set_ylabel(('Absolute ' if unstable else '')+r'$u_{%d}$ (mm)'%(floor+1))
                right.set_ylabel(('Absolute error' if unstable else 'Error')+' (mm)')
                for col,ax in enumerate([left,right]):
                    decorate(ax);ax.set_xlim(0,40)
                    ax.text(.012,.98,f'({chr(97+floor*2+col)})',transform=ax.transAxes,va='top')
                    if floor<2:ax.set_xlabel('')
                if unstable:
                    for ax in [left,right]:ax.yaxis.set_major_locator(mpl.ticker.LogLocator(base=10,numticks=4))
            handles,labels=axs[0,0].get_legend_handles_labels();fig.legend(handles,labels,loc='outside upper center',ncol=2,handlelength=2.8,columnspacing=1.3)
            write(fig,f'{key}_{exc}',dict(kind='case',key=key,input=exc,delays_ms=[row['tau1_ms'],row['tau2_ms']],unstable=unstable,reference='Uncondensed19 at same delay',plotted=plotted))
    if extra_only:RECORDS=[r for r in RECORDS if r['kind']=='case']
    # Four models, exactly the evaluated integer grid (no interpolated roots).
    grid=list(csv.DictReader((CASE/'results/delay_survey.csv').open()))
    fig,axs=plt.subplots(2,2,figsize=(7.48,5.2),sharex=True,sharey=True)
    norm=TwoSlopeNorm(vmin=-.001,vcenter=0,vmax=.005)
    ticks=np.arange(9)*DT*1000
    for ax,name,letter in zip(axs.flat,NAMES,'abcd'):
        Z=np.array([float(r['rho_'+name])-1 for r in grid]).reshape(9,9).T
        image=ax.pcolormesh(ticks,ticks,Z,cmap='coolwarm',norm=norm,shading='nearest')
        for r in ROWS:ax.plot(r['tau1_ms'],r['tau2_ms'],'o',mfc='none',mec='k',ms=4,lw=.6)
        ax.text(.025,.965,f'({letter}) '+LABELS[name],transform=ax.transAxes,va='top',bbox=dict(facecolor='white',alpha=.8,edgecolor='none',pad=1.8))
        decorate(ax,r'$\tau_1$ (ms)');ax.set_ylabel(r'$\tau_2$ (ms)');ax.set_xlim(-.45,8.3);ax.set_ylim(-.45,8.3)
    cb=fig.colorbar(image,ax=axs.ravel().tolist(),shrink=.85,pad=.03);cb.set_label(r'$\rho-1$');cb.solids.set_rasterized(False)
    write(fig,'delay_grid',dict(kind='delay_grid',grid_points=len(grid),selected_cases=len(ROWS)))
    # Equal-delay progression, stable response metrics plus the actual pole at 5 steps.
    fig,axs=plt.subplots(1,2,figsize=(7.48,2.85))
    for name in ['Guyan6','CB12']:
        xs=[k*DT*1000 for k in range(5)]
        for exc,marker in [('eq','o'),('chirp','s')]:
            ys=[metric(f'n{k:02d}_{k:02d}',exc,name,2,'error_same_interface_fixed_scale_percent') for k in range(5)]
            axs[0].plot(xs,ys,color=COLORS[name],ls='-' if exc=='eq' else '--',marker=marker,label=LABELS[name]+(' / EQ' if exc=='eq' else ' / Chirp'))
    for name in NAMES:
        xs=[k*DT*1000 for k in range(6)];ys=[float(next(r['rho_'+name] for r in grid if int(r['n1'])==k and int(r['n2'])==k)) for k in range(6)]
        axs[1].plot(xs,ys,color=COLORS[name],ls=STYLES[name],marker='o',label=LABELS[name])
    axs[1].axhline(1,color='k',lw=.7);axs[0].set_ylabel(r'Middle-storey error (\%)');axs[1].set_ylabel(r'Spectral radius $\rho$')
    for ax,letter in zip(axs,'ab'):
        decorate(ax,r'Equal delay $\tau_1=\tau_2$ (ms)');ax.text(.015,.98,f'({letter})',transform=ax.transAxes,va='top');ax.legend(fontsize=9,loc='best',handlelength=2)
    axs[1].yaxis.set_major_formatter(mpl.ticker.FormatStrFormatter('%.4f'))
    write(fig,'equal_delay_progression',dict(kind='equal_delay_progression',error_normalization='fixed Full15 zero-delay range'))
    # Two concrete stable candidates, physical middle-storey responses in both inputs.
    fig,axs=plt.subplots(2,2,figsize=(7.48,4.4))
    for col,key in enumerate(['n04_04','n05_01']):
        for row,exc in enumerate(['eq','chirp']):
            ax=axs[row,col];d=DATA[key];t=d['time_s'];mask=(t>=6)&(t<=16) if exc=='eq' else (t>=30)&(t<=40)
            for name in NAMES:ax.plot(t[mask],d[f'{exc}_{name}_physical_mm'][mask,1],color=COLORS[name],ls=STYLES[name],lw=.85,label=LABELS[name])
            decorate(ax);ax.set_ylabel(r'$u_2$ (mm)');ax.text(.015,.98,f'({chr(97+row*2+col)})',transform=ax.transAxes,va='top')
    for row in range(2):
        lo=min(axs[row,j].get_ylim()[0] for j in range(2));hi=max(axs[row,j].get_ylim()[1] for j in range(2))
        for j in range(2):axs[row,j].set_ylim(lo,hi)
    handles,labels=axs[0,0].get_legend_handles_labels();fig.legend(handles,labels,loc='outside upper center',ncol=2,handlelength=2.8)
    write(fig,'two_candidate_windows',dict(kind='candidate_windows',left='3.90625/3.90625 ms',right='4.8828125/0.9765625 ms',top='earthquake 6-16 s',bottom='chirp 30-40 s'))
    (CASE/'results/figure_records.json').write_text(json.dumps(RECORDS,indent=2),'utf-8')
    print('ALL_FIGURES_COMPLETE',len(RECORDS),flush=True)

if __name__=='__main__':main()
