from pathlib import Path
import csv,json,hashlib,shutil
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.transforms import Bbox

TMP=Path(__file__).resolve().parent;NEW=TMP.parents[1].parent/'260817/elsevier_review_v2_refined_20260907'
if TMP.name=='code' and TMP.parent.name=='refinement_evidence':NEW=TMP.parents[1]
DATA=NEW/'refinement_evidence/data';OUT=NEW/'submit_figure'
read=lambda name:list(csv.DictReader((DATA/name).open(encoding='utf-8-sig')))
shapes={(int(r['division']),r['method'],int(r['mode']),int(r['floor'])):float(r['normalised_displacement']) for r in read('new_horizontal_modes.csv')}
freq={(int(r['division']),r['method'],int(r['mode'])):float(r['frequency_hz']) for r in read('new_modes_frequencies.csv')}
plt.rcParams.update({'text.usetex':True,'font.family':'serif','font.serif':['Computer Modern Roman'],'font.size':9,'axes.labelsize':9,'xtick.labelsize':9,'ytick.labelsize':9,'legend.fontsize':9,'xtick.direction':'in','ytick.direction':'in','xtick.top':True,'ytick.right':True,'axes.linewidth':.8,'lines.linewidth':1.2,'lines.markersize':4,'legend.frameon':False,'savefig.dpi':600,'savefig.pad_inches':.04})
COL={'Full':'#555555','Guyan':'#4477AA','CB':'#EE6677'};LS={'Full':'--','Guyan':'-.','CB':'-'};MARK={'Full':'o','Guyan':'^','CB':'s'};LAB={'Full':'Full order','Guyan':'Guyan','CB':'Craig--Bampton'}
fig,axes=plt.subplots(1,4,figsize=(7.48,3.55),sharey=True)
fig.subplots_adjust(left=.065,right=.995,top=.91,bottom=.13,wspace=.12)
series=[];texts=[];headings=[]
for k,(div,mode) in enumerate([(1,1),(1,2),(2,1),(2,2)]):
 ax=axes[k]
 for method in ['Full','Guyan','CB']:
  xx=[0]+[shapes[div,method,mode,floor] for floor in [1,2,3]]
  ax.plot(xx,[0,1,2,3],color=COL[method],ls=LS[method],marker=MARK[method],mfc='white',label=LAB[method])
  series.append({'division':div,'mode':mode,'method':method,'x':xx,'y':[0,1,2,3],'frequency_hz':freq[div,method,mode]})
 ax.axvline(0,color='#BBBBBB',lw=.6,zorder=0)
 ax.set(xlim=(-1.18,1.18),ylim=(-.12,3.48));ax.set_xticks([-1,-.5,0,.5,1]);ax.set_yticks([0,1,2,3])
 headings.append(ax.text(.04,.985,f'({chr(97+k)}) Division {"I"*div}\nMode {mode}',transform=ax.transAxes,va='top',ha='left',linespacing=1.4,fontsize=8))
 frequency_text=r'$f$ (Hz)'+'\n'+'\n'.join(f'{method} {freq[div,method,mode]:.4f}' for method in ['Full','Guyan','CB'])
 # First modes have empty negative-displacement space. Second modes have empty lower-right space.
 x,y,va=(.04,.58,'top') if mode==1 else (.51,.095,'bottom')
 texts.append(ax.text(x,y,frequency_text,transform=ax.transAxes,ha='left',va=va,fontsize=8,linespacing=1.45))
axes[0].set_ylabel('Storey level');fig.supxlabel('Normalised horizontal displacement',y=.008,fontsize=9)
handles,labels=axes[0].get_legend_handles_labels();fig.legend(handles,labels,loc='upper center',bbox_to_anchor=(.53,1.005),ncol=3,handlelength=1.8,columnspacing=1.8)
fig.canvas.draw();renderer=fig.canvas.get_renderer();checks=[]
for k,(ax,t,h) in enumerate(zip(axes,texts,headings)):
 bb=t.get_window_extent(renderer);ab=ax.get_window_extent(renderer);pad=2.5*fig.dpi/72
 expanded=Bbox.from_extents(bb.x0-pad,bb.y0-pad,bb.x1+pad,bb.y1+pad)
 inside=ab.contains(bb.x0,bb.y0) and ab.contains(bb.x1,bb.y1)
 collision=[i for i,line in enumerate(ax.lines[:3]) if line.get_transform().transform_path(line.get_path()).intersects_bbox(expanded,filled=False)]
 heading_overlap=bb.overlaps(h.get_window_extent(renderer))
 checks.append({'panel':k+1,'frequency_font_pt':t.get_fontsize(),'inside_axes':bool(inside),'curve_collisions_at_2p5pt_padding':collision,'heading_overlap':bool(heading_overlap),'annotation_bbox_display':list(bb.extents),'annotation_bbox_axes':ax.transAxes.inverted().transform(bb.get_points()).tolist()})
 assert inside and not collision and not heading_overlap,checks[-1]
for ext in ['pdf','png']:fig.savefig(OUT/f'fig12_horizontal_modes.{ext}',bbox_inches='tight',dpi=600,**({'metadata':{'CreationDate':None,'ModDate':None}} if ext=='pdf' else {}))
plt.close(fig)
result={'status':'PASS','layout':[1,4],'frequency_entries':12,'curves':series,'placement_checks':checks,'pdf_sha256':hashlib.sha256((OUT/'fig12_horizontal_modes.pdf').read_bytes()).hexdigest(),'png_sha256':hashlib.sha256((OUT/'fig12_horizontal_modes.png').read_bytes()).hexdigest()}
(NEW/'refinement_evidence/validation/figure6_layout.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
if Path(__file__).resolve()!=(NEW/'refinement_evidence/code/plot_figure6.py').resolve():shutil.copy2(__file__,NEW/'refinement_evidence/code/plot_figure6.py')
print(json.dumps(result['placement_checks'],indent=2))
