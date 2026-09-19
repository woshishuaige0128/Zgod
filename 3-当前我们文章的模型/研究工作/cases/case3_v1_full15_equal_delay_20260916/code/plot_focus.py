"""Readable steady/free windows of the same saved reference-selected tone."""
import argparse,json,hashlib
from pathlib import Path
import numpy as np
from scipy import linalg as la
from PIL import Image
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import fitz
from plot_cases import COLORS,STYLES,LABELS

def main(results,out):
    resp=json.loads((results/'responses.json').read_text('utf8'));e=resp['divisions']['2']['tones'][1]
    a=np.load(results/e['file']);t=a['t']-e['loading_duration_s'];f=e['frequency_hz'];decay=e['models']['Full15']['free_identification']['expected_decay']
    masks=[(t>=-3/f)&(t<0),(t>=0)&(t<=3/decay)];fig,axs=plt.subplots(2,2,figsize=(7.48,5.3));curves=[]
    for col,mask in enumerate(masks):
        for name in COLORS:
            y=a[name][mask,4]*1000
            for row in [0,1]:
                if row==1 and name=='Full15':continue
                yy=y if row==0 else y-a['Full15'][mask,4]*1000
                axs[row,col].plot(t[mask],yy,color=COLORS[name],ls=STYLES[name],label=LABELS[name])
                curves.append(dict(figure='17_steady_free_detail',source=e['file'],method=name,row=row,col=col,
                    x_sha256=hashlib.sha256(t[mask].tobytes()).hexdigest(),y_sha256=hashlib.sha256(yy.tobytes()).hexdigest()))
        for ax in axs[:,col]:ax.set_xlabel('Time from unloading (s)');ax.xaxis.set_major_locator(MaxNLocator(5));ax.yaxis.set_major_locator(MaxNLocator(5));ax.minorticks_off()
        axs[0,col].set_ylabel('Displacement (mm)');axs[1,col].set_ylabel('Error (mm)')
    for row in axs:
        v=max(max(abs(ax.get_ylim()[0]),abs(ax.get_ylim()[1])) for ax in row)
        for ax in row:ax.set_ylim(-v,v)
    handles,labels=axs[0,0].get_legend_handles_labels();fig.legend(handles,labels,loc='outside upper center',ncol=3)
    name='17_steady_free_detail';fig.savefig(out/(name+'.pdf'));doc=fitz.open(out/(name+'.pdf'));doc[0].get_pixmap(dpi=600).save(out/(name+'.png'));doc[0].get_pixmap(dpi=140).save(out/'previews'/(name+'.png'))
    entry=dict(name=name,caption='划分二、中间层，等时滞2.9296875ms，激励9.32959965Hz。左为撤载前最后3周期，右为撤载后的3个完整模型相关模态衰减时间常数；完整记录另存。上为位移，下为同τ误差，两列各行同纵轴。新增定频局部图。',old_figure=None,pdf=name+'.pdf',png=name+'.png',pdf_vector=True,dpi=600,
        axes=[dict(xlim=ax.get_xlim(),ylim=ax.get_ylim(),xlabel=ax.get_xlabel(),ylabel=ax.get_ylabel()) for ax in axs.flat],fonts=[x[3] for x in doc[0].get_fonts()])
    mf=json.loads((out/'figure_manifest.json').read_text('utf8'));mf=[x for x in mf if x['name']!=name]+[entry];(out/'figure_manifest.json').write_text(json.dumps(mf,ensure_ascii=False,indent=2),'utf8')
    p=json.loads((out/'curve_provenance.json').read_text('utf8'));p=[x for x in p if x['figure']!=name]+curves;(out/'curve_provenance.json').write_text(json.dumps(p,ensure_ascii=False,indent=2),'utf8')
    print(name)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--results',required=True,type=Path);p.add_argument('--out',required=True,type=Path);a=p.parse_args();main(a.results,a.out)
