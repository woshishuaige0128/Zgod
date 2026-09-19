from pathlib import Path
import csv,json,shutil,re,hashlib
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

TMP=Path(__file__).resolve().parent;ROOT=TMP.parents[1]
NEW=ROOT.parent/'260817/elsevier_review_v2_figlayout_20260907'
if TMP.name=='code' and TMP.parent.name=='explanation_evidence':NEW=TMP.parents[1]
OUT=NEW/'submit_figure';DATA=NEW/'explanation_evidence/data'
plt.rcParams.update({'text.usetex':True,'font.family':'serif','font.serif':['Computer Modern Roman'],'font.size':9,'axes.labelsize':9,'xtick.labelsize':9,'ytick.labelsize':9,'legend.fontsize':9,'xtick.direction':'in','ytick.direction':'in','xtick.top':True,'ytick.right':True,'axes.linewidth':.8,'lines.linewidth':1.2,'lines.markersize':4,'legend.frameon':False,'axes.grid':False,'savefig.dpi':600,'savefig.pad_inches':.04})
COL={'Full':'#555555','Guyan':'#4477AA','CB':'#EE6677'}
LS={'Full':'--','Guyan':'-.','CB':'-'};MARK={'Full':'o','Guyan':'^','CB':'s'}
LAB={'Full':'Full order','Guyan':'Guyan','CB':'Craig--Bampton'}
def read(name):return list(csv.DictReader((DATA/name).open(encoding='utf-8-sig')))
shapes={(int(r['division']),r['method'],int(r['mode']),int(r['floor'])):float(r['normalised_displacement']) for r in read('new_horizontal_modes.csv')}
freq={(int(r['division']),r['method'],int(r['mode'])):float(r['frequency_hz']) for r in read('new_modes_frequencies.csv')}
manifest=[]
def save(fig,name,series):
    for ax in fig.axes:ax.tick_params(which='both',direction='in',top=True,right=True)
    fig.savefig(OUT/(name+'.pdf'),bbox_inches='tight',metadata={'CreationDate':None,'ModDate':None})
    fig.savefig(OUT/(name+'.png'),bbox_inches='tight',dpi=600)
    manifest.append({'file':name,'layout':[1,4],'data_series':series,'pdf_sha256':hashlib.sha256((OUT/(name+'.pdf')).read_bytes()).hexdigest(),'png_sha256':hashlib.sha256((OUT/(name+'.png')).read_bytes()).hexdigest()})
    plt.close(fig)

fig,axes=plt.subplots(1,4,figsize=(7.48,4.1),sharey=True)
fig.subplots_adjust(left=.065,right=.995,top=.91,bottom=.29,wspace=.12)
series=[]
for k,(div,mode) in enumerate([(1,1),(1,2),(2,1),(2,2)]):
    ax=axes[k]
    for method in ['Full','Guyan','CB']:
        xx=[0]+[shapes[div,method,mode,floor] for floor in [1,2,3]]
        ax.plot(xx,[0,1,2,3],color=COL[method],ls=LS[method],marker=MARK[method],mfc='white',label=LAB[method])
        series.append({'division':div,'mode':mode,'method':method,'x':xx,'y':[0,1,2,3],'frequency_hz':freq[div,method,mode]})
    ax.axvline(0,color='#BBBBBB',lw=.6,zorder=0)
    ax.set(xlim=(-1.18,1.18),ylim=(-.12,3.48));ax.set_xticks([-1,-.5,0,.5,1]);ax.set_yticks([0,1,2,3])
    ax.text(.04,.985,f'({chr(97+k)}) Division {"I"*div}\\\nMode {mode}'.replace('\\\n','\n'),transform=ax.transAxes,va='top',ha='left',linespacing=1.45)
    box=ax.get_position();x=box.x0+.055*box.width
    for row,method in enumerate(['Full','Guyan','CB']):fig.text(x,.14-.047*row,f'{method}: {freq[div,method,mode]:.4f}',ha='left',va='center',fontsize=9)
axes[0].set_ylabel('Storey level')
fig.supxlabel('Normalised horizontal displacement',y=.215,fontsize=9)
fig.text(.53,.179,'Natural frequencies (Hz)',ha='center',va='center',fontsize=9)
handles,labels=axes[0].get_legend_handles_labels();fig.legend(handles,labels,loc='upper center',bbox_to_anchor=(.53,1.005),ncol=3,handlelength=1.8,columnspacing=1.8)
save(fig,'fig12_horizontal_modes',series)

drift={(int(r['division']),r['excitation'],r['method'],int(r['storey'])):float(r['peak_drift_percent']) for r in read('new_peak_drift.csv')}
fig,axes=plt.subplots(1,4,figsize=(7.48,3.45),sharey=True,layout='constrained')
series=[]
for k,(div,exc) in enumerate([(1,'eq'),(2,'eq'),(1,'chirp'),(2,'chirp')]):
    ax=axes[k]
    for method in ['Full','Guyan','CB']:
        xx=[drift[div,exc,method,floor] for floor in [1,2,3]]
        ax.plot(xx,[1,2,3],color=COL[method],ls=LS[method],marker=MARK[method],mfc='white',label=LAB[method]);series.append({'division':div,'excitation':exc,'method':method,'x':xx,'y':[1,2,3]})
    upper=max(v for (di,ex,me,fl),v in drift.items() if ex==exc)*1.12
    ax.set(xlim=(0,upper),ylim=(.84,3.68));ax.set_yticks([1,2,3]);ax.xaxis.set_major_locator(MaxNLocator(4))
    ax.text(.04,.985,f'({chr(97+k)}) Division {"I"*div}\n'+('El Centro' if exc=='eq' else 'Chirp'),transform=ax.transAxes,va='top',ha='left',linespacing=1.45)
axes[0].set_ylabel('Storey')
fig.supxlabel(r'Peak interstorey drift (\%)',fontsize=9)
handles,labels=axes[0].get_legend_handles_labels();fig.legend(handles,labels,loc='outside upper center',ncol=3,handlelength=1.8,columnspacing=1.8)
save(fig,'fig15_peak_drift',series)
(DATA/'layout_figure_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')

before=(NEW/'explanation_evidence/baseline/main.tex').read_text('utf-8')
old1='the corresponding natural frequency is given in the legend.'
new1='the corresponding natural frequencies (Hz) are listed beneath each panel.'
old2=r'The left and right columns correspond to divisions I and II, respectively.'
new2=r'Panels (a,c) correspond to division I, and panels (b,d) to division II.'
assert before.count(old1)==1 and before.count(old2)==1
after=before.replace(old1,new1).replace(old2,new2)
assert re.findall(r'\\vspace\{-[^}]+\}',after)==re.findall(r'\\vspace\{-[^}]+\}',before)
(NEW/'main.tex').write_text(after,encoding='utf-8')
(NEW/'explanation_evidence/caption_changes.json').write_text(json.dumps([{'figure':6,'old':old1,'new':new1,'reason':'横向四子图使用共享方法图例，频率数值移至各子图下方，完整保留12项频率。'},{'figure':13,'old':old2,'new':new2,'reason':'四子图排成一行后，原左右两列描述不再适用；子图顺序和数据未变。'}],ensure_ascii=False,indent=2),encoding='utf-8')
if Path(__file__).resolve()!=(NEW/'explanation_evidence/code/plot_layout.py').resolve():shutil.copy2(__file__,NEW/'explanation_evidence/code/plot_layout.py')
print('Created two 1x4 figures and adjusted two caption phrases; scientific data unchanged.')
