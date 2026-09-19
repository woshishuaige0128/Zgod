from pathlib import Path
import json,hashlib,shutil
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
TMP=Path(__file__).resolve().parent;NEW=TMP.parents[1].parent/'260817/elsevier_review_v2_refined_20260907'
if TMP.name=='code' and TMP.parent.name=='refinement_evidence':NEW=TMP.parents[1]
DATA=NEW/'refinement_evidence/data';OUT=NEW/'submit_figure'
source=json.loads((DATA/'explanation_calculations.json').read_text('utf-8'));metric=json.loads((DATA/'modal_share_deviation.json').read_text('utf-8'))
shares={(m['division'],m['method']):m['shares'] for m in source['models']}
plt.rcParams.update({'text.usetex':True,'font.family':'serif','font.serif':['Computer Modern Roman'],'font.size':9,'axes.labelsize':9,'xtick.labelsize':9,'ytick.labelsize':9,'legend.fontsize':9,'xtick.direction':'in','ytick.direction':'in','xtick.top':True,'ytick.right':True,'axes.linewidth':.8,'lines.linewidth':1.2,'lines.markersize':4,'legend.frameon':False,'savefig.dpi':600,'savefig.pad_inches':.04})
COL={'Full':'#555555','Guyan':'#4477AA','CB':'#EE6677'};LS={'Full':'--','Guyan':'-.','CB':'-'};MARK={'Full':'o','Guyan':'^','CB':'s'};LAB={'Full':'Full order','Guyan':'Guyan','CB':'Craig--Bampton'}
fig,axes=plt.subplots(2,2,figsize=(7.48,5.05),layout='constrained',gridspec_kw={'width_ratios':[1.45,1]})
curves=[];bars=[]
for row,div in enumerate([1,2]):
 acts=[1,6] if div==1 else [1,11]
 for method in ['Full','Guyan','CB']:
  E=shares[div,method];axes[row,0].plot(np.arange(1,16),E,color=COL[method],ls=LS[method],marker=MARK[method],mfc='white',label=LAB[method]);curves.append({'division':div,'method':method,'shares':E})
 axes[row,0].set(xlabel=r'Physical coordinate index $j$',ylabel=r'Modal share $E_j$',xlim=(.5,15.5),ylim=(-.02,.8));axes[row,0].set_xticks([1,3,6,9,12,15]);axes[row,0].yaxis.set_major_locator(MaxNLocator(5))
 axes[row,0].text(.025,.96,f'({chr(97+row*2)}) Division {"I"*div}',transform=axes[row,0].transAxes,va='top')
 for i,method in enumerate(['Guyan','CB']):
  values=[next(v['absolute_relative_deviation'] for v in metric['per_coordinate'] if (v['division'],v['method'],v['physical_dof'])==(div,method,j)) for j in acts]
  axes[row,1].bar(np.array([0,1])+(i-.5)*.3,values,width=.28,color=COL[method],edgecolor='white',hatch='//' if method=='Guyan' else None,label=LAB[method])
  bars.append({'division':div,'method':method,'coordinates':acts,'heights':values,'sum':sum(values)})
 axes[row,1].set_xticks([0,1],[rf'$\psi_{{{j}}}$' for j in acts]);axes[row,1].set(xlabel='Actuated coordinate',ylabel='Relative share deviation',ylim=(0,.055 if div==1 else 1.4));axes[row,1].yaxis.set_major_locator(MaxNLocator(5))
 axes[row,1].text(.035,.96,f'({chr(98+row*2)}) Division {"I"*div}',transform=axes[row,1].transAxes,va='top')
axes[0,0].legend(loc='upper right',fontsize=9)
for ext in ['pdf','png']:fig.savefig(OUT/f'fig16_modal_shares.{ext}',bbox_inches='tight',dpi=600,**({'metadata':{'CreationDate':None,'ModDate':None}} if ext=='pdf' else {}))
plt.close(fig)
assert all(v>=0 for b in bars for v in b['heights'])
result={'status':'PASS','left_curves':curves,'right_bars':bars,'pdf_sha256':hashlib.sha256((OUT/'fig16_modal_shares.pdf').read_bytes()).hexdigest(),'png_sha256':hashlib.sha256((OUT/'fig16_modal_shares.png').read_bytes()).hexdigest()}
(NEW/'refinement_evidence/validation/figure15_values.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
if Path(__file__).resolve()!=(NEW/'refinement_evidence/code/plot_figure15.py').resolve():shutil.copy2(__file__,NEW/'refinement_evidence/code/plot_figure15.py')
print(json.dumps(bars,indent=2))
