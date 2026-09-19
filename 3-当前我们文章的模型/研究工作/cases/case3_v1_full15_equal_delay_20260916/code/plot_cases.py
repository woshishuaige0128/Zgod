"""Scientific-plotting figures from saved results, with curve provenance."""
import argparse,json,hashlib
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator,NullLocator
import fitz
from full15_model import H,FLOORS

COLORS={'Full15':'#228833','Guyan':'#EE6677','CB3':'#4477AA'}
STYLES={'Full15':'-.','Guyan':'--','CB3':'-'}
LABELS={'Full15':'Full order','Guyan':'Guyan','CB3':'CB (3 modes)'}
plt.rcParams.update({'text.usetex':True,'font.family':'serif','font.serif':['Computer Modern Roman'],
    'font.size':9,'axes.labelsize':9,'xtick.labelsize':9,'ytick.labelsize':9,'legend.fontsize':9,
    'xtick.direction':'in','ytick.direction':'in','xtick.top':True,'ytick.right':True,
    'xtick.minor.visible':False,'ytick.minor.visible':False,'axes.linewidth':.8,'lines.linewidth':1.2,
    'lines.markersize':4,'legend.frameon':False,'axes.grid':False,'figure.constrained_layout.use':True,
    'savefig.dpi':600,'savefig.pad_inches':.02})

def main(results,out):
    out.mkdir(parents=True,exist_ok=True);(out/'previews').mkdir(exist_ok=True)
    dyn=json.loads((results/'dynamics.json').read_text('utf-8'));resp=json.loads((results/'responses.json').read_text('utf-8'))
    data=np.load(results/'dynamics_arrays.npz');figures=[];series=[];current=''
    def digest(x):return hashlib.sha256(np.ascontiguousarray(x,dtype='<f8').tobytes()).hexdigest()
    def line(ax,x,y,name,source,**kwargs):
        x=np.asarray(x);y=np.asarray(y)
        assert x.ndim==y.ndim==1 and len(x)==len(y) and np.isfinite(x).all() and np.isfinite(y).all()
        obj=ax.plot(x,y,color=COLORS.get(name,'#AA3377'),ls=STYLES.get(name,':'),label=LABELS.get(name,name),**kwargs)[0]
        assert np.array_equal(obj.get_xdata(),x) and np.array_equal(obj.get_ydata(),y)
        series.append(dict(figure=current,source=source,method=name,n=len(x),x_sha256=digest(x),y_sha256=digest(y),
                           x_min=float(x.min()),x_max=float(x.max()),y_min=float(y.min()),y_max=float(y.max())))
    def canvas(rows=1,cols=2):
        fig,axs=plt.subplots(rows,cols,figsize=(7.48,2.65*rows),squeeze=False)
        for ax in axs.flat:
            ax.xaxis.set_major_locator(MaxNLocator(5));ax.yaxis.set_major_locator(MaxNLocator(5));ax.minorticks_off()
        return fig,axs
    def limits_equal(axes):
        low=min(ax.get_ylim()[0] for ax in axes);high=max(ax.get_ylim()[1] for ax in axes)
        for ax in axes:ax.set_ylim(low,high)
    def save(fig,axs,name,caption,old=None):
        for ax in axs.flat:
            assert not ax.get_title()
            ax.xaxis.set_minor_locator(NullLocator());ax.yaxis.set_minor_locator(NullLocator())
            for index,obj in enumerate(ax.lines):
                xx=np.asarray(obj.get_xdata(),dtype=float);yy=np.asarray(obj.get_ydata(),dtype=float)
                assert np.isfinite(xx).all() and np.isfinite(yy).all()
                series.append(dict(figure=name,source='Rendered artist; detailed sources in figure caption and driver',
                    artist=index,label=obj.get_label(),n=len(xx),x_sha256=digest(xx),y_sha256=digest(yy)))
        path=out/(name+'.pdf');fig.savefig(path)
        doc=fitz.open(path);assert len(doc)==1 and not doc[0].get_images()
        doc[0].get_pixmap(dpi=600).save(out/(name+'.png'))
        doc[0].get_pixmap(dpi=140).save(out/'previews'/(name+'.png'))
        fonts=doc[0].get_fonts();assert fonts and all('Type3'!=f[2] for f in fonts)
        figures.append(dict(name=name,caption=caption,old_figure=old,pdf=name+'.pdf',png=name+'.png',
            axes=[dict(xlim=ax.get_xlim(),ylim=ax.get_ylim(),xlabel=ax.get_xlabel(),ylabel=ax.get_ylabel()) for ax in axs.flat],
            pdf_vector=True,dpi=600,fonts=[f[3] for f in fonts]))
        plt.close(fig);print(name,flush=True)

    current='01_frequency_convergence';fig,ax=canvas(2)
    for col,d in enumerate([1,2]):
        D=dyn['divisions'][str(d)];rows=D['modal_convergence'];m=[x['internal_modes'] for x in rows]
        for j,c in enumerate(['#4477AA','#EE6677','#228833']):
            y=np.array([x['frequency_error_pct'][j] for x in rows]);ax[0,col].plot(m,y,color=c,ls=['-','--','-.'][j],marker=['o','s','^'][j],label=f'Mode {j+1}')
        ax[0,col].set(xlabel='Retained internal modes',ylabel=r'Frequency error (\%)');ax[0,col].legend()
        rows=D['delayed_mode_convergence'];stable=[x for x in rows if x['stable']]
        line(ax[1,col],[x['internal_modes'] for x in stable],[x['frequency_norm_error_pct'] for x in stable],'CB3',f'dynamics.json division {d} delayed_mode_convergence',marker='o')
        ax[1,col].set(xlabel='Retained internal modes',ylabel=r'FRF norm error (\%)')
    for row in ax:limits_equal(row)
    save(fig,ax,current,'左：划分一；右：划分二。上：前三阶被动频率误差；下：2.9296875ms共同稳定响应点下0.1–10Hz三楼层复频响整体相对误差。横坐标0对应Guyan，3对应正文CB；仅稳定模型作稳态解释。新增收敛图，对应旧稿频率表。')

    current='02_mode_shapes';fig,ax=canvas(2)
    for col,d in enumerate([1,2]):
        phi=data[f'd{d}_full_modes']
        for j in range(2):
            reference=phi[FLOORS,j];scale=max(abs(reference));reference=reference/scale
            for name,m in [('Full15',None),('Guyan',0),('CB3',3)]:
                shapes=phi if m is None else data[f'd{d}_m{m}_modes'];y=shapes[FLOORS,j]
                if np.dot(y,reference)<0:y=-y
                y=y/max(abs(y));line(ax[j,col],np.r_[0,y],[0,1,2,3],name,f'dynamics_arrays d{d} mode {j+1}',marker={'Full15':'^','Guyan':'s','CB3':'o'}[name])
            ax[j,col].set(xlabel='Normalized horizontal displacement',ylabel='Floor');ax[j,col].set_yticks([0,1,2,3]);ax[j,col].set_xlim(-1.1,1.1)
    ax[0,0].legend();save(fig,ax,current,'两种划分的三楼层恢复振型：上排第一阶，下排第二阶；各振型按最大水平位移归一并与完整模型对齐符号。左划分一、右划分二。',6)

    current='03_static_internal_load';fig,ax=canvas()
    for col,d in enumerate([1,2]):
        rows=dyn['divisions'][str(d)]['modal_convergence']
        for name,idx in [('Full15',-1),('Guyan',0),('CB3',3)]:
            line(ax[0,col],np.r_[0,np.array(rows[idx]['static_floors_per_unit'])*1000],[0,1,2,3],name,f'dynamics.json d{d} static',marker={'Full15':'^','Guyan':'s','CB3':'o'}[name])
        ax[0,col].set(xlabel=r'Static displacement / input (mm s$^2$/m)',ylabel='Floor');ax[0,col].set_yticks([0,1,2,3])
    low=min(x.get_xlim()[0] for x in ax.flat);high=max(x.get_xlim()[1] for x in ax.flat)
    for x in ax.flat:x.set_xlim(low,high)
    ax[0,0].legend();save(fig,ax,current,'单位静力等效地震输入下的楼层位移。左划分一、右划分二；划分二中间层的直接受载变形属于被遗漏内部空间。新增机理图，无一一对应旧图。')

    for level in ['normal','near']:
        current=f'04_frf_{level}';fig,ax=canvas(3)
        for col,d in enumerate([1,2]):
            n=dyn['divisions'][str(d)]['selection'][level+'_n'];freq=data['frequency_hz'];ref=data[f'd{d}_n{n}_Full15_frf'][:,1]
            for name in COLORS:
                z=data[f'd{d}_n{n}_{name}_frf'][:,1]
                line(ax[0,col],freq,1000*abs(z),name,f'dynamics_arrays d{d} n{n} {name} FRF middle amplitude')
                line(ax[1,col],freq,np.unwrap(np.angle(z))*180/np.pi,name,f'dynamics_arrays d{d} n{n} {name} FRF middle phase')
                if name!='Full15':line(ax[2,col],freq,1000*abs(z-ref),name,f'dynamics_arrays d{d} n{n} {name} FRF middle absolute complex error')
            ax[0,col].set_ylabel(r'Amplitude (mm s$^2$/m)');ax[1,col].set_ylabel('Phase (deg)');ax[2,col].set_ylabel(r'Complex error (mm s$^2$/m)')
            for row in range(3):ax[row,col].set(xlabel='Frequency (Hz)',xlim=(.1,10))
        for row in ax:limits_equal(row)
        ns=[dyn['divisions'][str(d)]['selection'][level+'_n'] for d in [1,2]]
        ax[0,0].legend();save(fig,ax,current,f'中间层物理恢复频响，左划分一τ={ns[0]*H*1000:.6f}ms、右划分二τ={ns[1]*H*1000:.6f}ms。上幅值、中相位、下相对于同τ Full15的复频响绝对误差。此处为三者共同稳定响应点，完整模型临界前候选点另列。新增频域图。')

    current='05_equal_delay_poles';fig,ax=canvas(2)
    max_tau=max(D['critical_intervals_s'][name][1] for D in dyn['divisions'].values() for name in COLORS if D['critical_intervals_s'][name] is not None)+2*H
    for col,d in enumerate([1,2]):
        D=dyn['divisions'][str(d)]
        for name in COLORS:
            rows=[r for r in D['step_refinement']['4'][name]['scan'] if r['tau_s']<=max_tau]
            line(ax[0,col],1000*np.array([r['tau_s'] for r in rows]),[r['decay'] for r in rows],name,f'dynamics.json d{d} h/4 {name} all-root decay')
            line(ax[1,col],1000*np.array([r['tau_s'] for r in rows]),[r['frequency_hz'] for r in rows],name,f'dynamics.json d{d} h/4 {name} dominant frequency')
        ax[0,col].axhline(0,color='#BBBBBB',lw=.8);ax[0,col].set_ylabel(r'Minimum decay rate (s$^{-1}$)');ax[1,col].set_ylabel('Dominant frequency (Hz)')
        for row in ax[:,col]:row.set(xlabel='Equal delay (ms)',xlim=(0,1000*max_tau))
    for row in ax:limits_equal(row)
    ax[0,0].legend();save(fig,ax,current,'两通道等时滞，步长h/4。上排由全部增广根最大模换算的最小衰减率，过零表示失去渐近稳定；下排对应主导根频率，换支时可跳变。左划分一、右划分二。旧图14为其他实现的双时滞稳定域，仅作历史主题对照。',14)

    current='06_delay_boundary_refinement';fig,ax=canvas()
    for col,d in enumerate([1,2]):
        D=dyn['divisions'][str(d)]
        for name in COLORS:
            intervals=[D['critical_intervals_s'][name]]+[D['step_refinement'][str(f)][name]['critical_interval_s'] for f in [2,4]]
            mid=np.array([np.mean(v) for v in intervals])*1000;err=np.array([(v[1]-v[0])/2 for v in intervals])*1000
            ax[0,col].errorbar([1,2,4],mid,yerr=err,color=COLORS[name],ls=STYLES[name],marker={'Full15':'^','Guyan':'s','CB3':'o'}[name],capsize=3,label=LABELS[name])
        ax[0,col].set(xlabel='Step refinement factor',ylabel='First crossing bracket (ms)');ax[0,col].set_xticks([1,2,4])
    limits_equal(ax[0]);ax[0,0].legend();save(fig,ax,current,'首次失稳的相邻整数网格区间，误差棒是网格区间半宽；标记位于区间中点以便显示，不表示额外精度的临界值。左划分一、右划分二。',14)

    eq_global=max(np.max(abs(np.load(results/resp['divisions'][str(d)]['earthquake'][str(dyn['divisions'][str(d)]['selection']['near_n'])]['file'])[name][:,3:]))*1000 for d in [1,2] for name in COLORS)*1.06
    err_global=max(np.max(abs(np.load(results/resp['divisions'][str(d)]['earthquake'][str(dyn['divisions'][str(d)]['selection']['near_n'])]['file'])[name][:,3:]-np.load(results/resp['divisions'][str(d)]['earthquake'][str(dyn['divisions'][str(d)]['selection']['near_n'])]['file'])['Full15'][:,3:]))*1000 for d in [1,2] for name in ['Guyan','CB3'])*1.06
    for d in [1,2]:
        D=dyn['divisions'][str(d)];n=D['selection']['near_n'];R=resp['divisions'][str(d)];entry=R['earthquake'][str(n)];raw=np.load(results/entry['file'])
        current=f'07_earthquake_division{d}';fig,ax=canvas(3)
        for floor in range(3):
            for name in COLORS:
                y=raw[name][:,floor+3]*1000;line(ax[floor,0],raw['t'],y,name,f'{entry["file"]}:{name} physical floor {floor+1} mm',lw=.85)
                if name!='Full15':line(ax[floor,1],raw['t'],(raw[name][:,floor+3]-raw['Full15'][:,floor+3])*1000,name,f'{entry["file"]} {name}-Full15 physical floor {floor+1} mm',lw=.85)
            ax[floor,0].set_ylabel('Displacement (mm)');ax[floor,1].set_ylabel('Error (mm)')
            for aa in ax[floor]:aa.set(xlabel='Time (s)',xlim=(0,40))
        for aa in ax[:,0]:aa.set_ylim(-eq_global,eq_global)
        for aa in ax[:,1]:aa.set_ylim(-err_global,err_global)
        ax[0,0].legend();ax[0,1].legend()
        save(fig,ax,current,f'划分{d}，共同稳定响应点等时滞{n*H*1000:.6f}ms。三行依次首层、中间层、顶层，左为真实响应，右为同τ缩聚误差；原40s地震记录保持。两划分响应及误差分别使用相同纵轴。',7 if d==1 else [8,9])
        for j,entry in enumerate(R['tones']):
            if entry['n']!=n:continue
            raw=np.load(results/entry['file']);t=raw['t']-entry['loading_duration_s'];f=entry['frequency_hz'];sel=(t>=-5/f)&(t<=max(10/f,min(15,entry['unloading_duration_s'])))
            current=f'08_tone_division{d}_{j+1}';fig,ax=canvas(2)
            for col,floor in enumerate([1,2]):
                for name in COLORS:
                    line(ax[0,col],t[sel],raw[name][sel,floor+3]*1000,name,f'{entry["file"]}:{name} physical floor {floor+1} relative to unloading',lw=.95)
                    if name!='Full15':line(ax[1,col],t[sel],1000*(raw[name][sel,floor+3]-raw['Full15'][sel,floor+3]),name,f'{entry["file"]}:{name} error floor {floor+1}',lw=.95)
                for aa in ax[:,col]:aa.axvline(0,color='#BBBBBB',lw=.8);aa.set_xlabel('Time from unloading (s)')
                ax[0,col].set_ylabel('Displacement (mm)');ax[1,col].set_ylabel('Error (mm)')
            for row in ax:limits_equal(row)
            ax[0,0].legend();save(fig,ax,current,f'划分{d}，等时滞{n*H*1000:.6f}ms，Full15选定频率{f:.6f}Hz。左中间层、右顶层；0s撤去激励并延续时滞历史。显示撤载前5周期与自由响应局部，完整记录另存。新增定频图，无一一对应旧图。')

    current='09_earthquake_errors';fig,ax=canvas(2)
    for col,d in enumerate([1,2]):
        R=resp['divisions'][str(d)]['earthquake'];entries=list(R.values());entries.sort(key=lambda e:e['n'])
        for name in ['Guyan','CB3']:
            x=[e['tau_s']*1000 for e in entries]
            for row,key in enumerate(['to_matched_full','to_original_passive_RK4']):
                y=[e['models'][name][key]['nrmse_range_pct'][1] for e in entries]
                line(ax[row,col],x,y,name,f'responses.json d{d} middle floor {key}',marker='s' if name=='Guyan' else 'o')
                ax[row,col].set(xlabel='Equal delay (ms)',ylabel=r'NRMSE (\%)')
    for row in ax:limits_equal(row)
    ax[0,0].legend();save(fig,ax,current,'中间层地震全记录NRMSE。上排参照同τ Full15，隔离缩聚误差；下排参照原无时滞无控制RK4完整框架，衡量总偏差。两行分母分别取各自完整参照峰峰值，百分比不相加。左划分一、右划分二。新增误差汇总，对应旧稿NRMSE表。')

    current='10_slow_chirp';fig,ax=canvas(2)
    for col,d in enumerate([1,2]):
        entry=resp['divisions'][str(d)]['slow_chirp'];last=entry['runs'][-1];raw=np.load(results/last['file']);f=raw['frequency_samples'];ref=raw['Full15_demodulated'][:,1]
        for name in COLORS:
            y=raw[name+'_demodulated'][:,1];line(ax[0,col],f,1000*abs(y),name,f'{last["file"]} {name} middle demodulated amplitude')
            if name!='Full15':line(ax[1,col],f,1000*abs(y-ref),name,f'{last["file"]} {name} middle demodulated error')
        ax[0,col].set_ylabel(r'Amplitude (mm s$^2$/m)');ax[1,col].set_ylabel(r'Complex error (mm s$^2$/m)')
        for aa in ax[:,col]:aa.set_xlabel('Instantaneous frequency (Hz)')
    for row in ax:limits_equal(row)
    ax[0,0].legend();save(fig,ax,current,'正常非零等时滞下，覆盖Full15第二共振附近的慢扫频同步解调结果。上幅值，下相对于同τ Full15的复幅值误差；扫速减半结果及准稳态检查见表。左划分一、右划分二。旧图为0.1–10Hz/40s快扫，激励不同，属于主题对照。',[10,11,12])

    for d in [1,2]:
        n=dyn['divisions'][str(d)]['selection']['near_n'];entry=resp['divisions'][str(d)]['fast_chirp'][str(n)];raw=np.load(results/entry['file'])
        current=f'11_fast_chirp_division{d}';fig,ax=canvas(3)
        for floor in range(3):
            for name in COLORS:
                line(ax[floor,0],raw['t'],1000*raw[name][:,floor+3],name,f'{entry["file"]}:{name}:floor{floor+1}',lw=.8)
                if name!='Full15':line(ax[floor,1],raw['t'],1000*(raw[name][:,floor+3]-raw['Full15'][:,floor+3]),name,f'{entry["file"]}:error:floor{floor+1}',lw=.8)
            ax[floor,0].set_ylabel('Displacement (mm)');ax[floor,1].set_ylabel('Error (mm)')
            for aa in ax[floor]:aa.set(xlabel='Time (s)',xlim=(0,40))
        limits_equal(ax[:,0]);limits_equal(ax[:,1]);ax[0,0].legend()
        save(fig,ax,current,f'划分{d}，等时滞{n*H*1000:.6f}ms，原0.1–10Hz/40s快速扫频。三行依次三个楼层；左真实响应，右同τ误差。保留原输入用于区分时滞影响与扫速变化。',10 if d==1 else [11,12])

    current='12_peak_story_drift';fig,ax=canvas(2)
    from full15_model import drift
    for col,d in enumerate([1,2]):
        n=dyn['divisions'][str(d)]['selection']['near_n']
        for row,signal in enumerate(['earthquake','fast_chirp']):
            entry=resp['divisions'][str(d)][signal][str(n)];raw=np.load(results/entry['file'])
            for name in COLORS:line(ax[row,col],1000*np.max(abs(drift(raw[name][:,3:])),axis=0),[1,2,3],name,f'{entry["file"]}:{name} peak story drift',marker={'Full15':'^','Guyan':'s','CB3':'o'}[name])
            ax[row,col].set(xlabel='Peak absolute drift (mrad)',ylabel='Storey');ax[row,col].set_yticks([1,2,3])
    for row in ax:
        right=max(aa.get_xlim()[1] for aa in row)
        for aa in row:aa.set_xlim(0,right)
    ax[0,0].legend();save(fig,ax,current,'2.9296875ms等时滞下峰值层间位移角；上地震、下原快速扫频，左划分一、右划分二。层高0.635m；图中mrad=1000×层间位移/层高。',13)

    current='13_prediction_identification';fig,ax=canvas(2)
    for col,d in enumerate([1,2]):
        n=dyn['divisions'][str(d)]['selection']['near_n'];tones=[e for e in resp['divisions'][str(d)]['tones'] if e['n']==n]
        for name in COLORS:
            for row,key in enumerate(['frequency_hz','decay']):
                vals=[e['models'][name]['free_identification'] for e in tones]
                x=[v['expected_frequency_hz' if key=='frequency_hz' else 'expected_decay'] for v in vals];y=[v[key] for v in vals]
                line(ax[row,col],x,y,name,f'responses.json d{d} free identification {key}',marker={'Full15':'^','Guyan':'s','CB3':'o'}[name])
                unit='Hz' if row==0 else r's$^{-1}$';ax[row,col].set(xlabel=f'Predicted ({unit})',ylabel=f'Identified ({unit})')
        for aa in ax[:,col]:
            low=min(aa.get_xlim()[0],aa.get_ylim()[0]);high=max(aa.get_xlim()[1],aa.get_ylim()[1]);aa.plot([low,high],[low,high],color='#BBBBBB',lw=.7,zorder=0);aa.set(xlim=(low,high),ylim=(low,high))
    ax[0,0].legend();save(fig,ax,current,'等时滞2.9296875ms，撤载自由响应的输出识别与全部增广极点预测。上频率，下衰减率；每方法两个点对应完整模型选择的两个激励频段。灰线为完全一致。左划分一、右划分二。新增理论验证图。')

    current='14_fixed_gain_supplement';fig,ax=canvas()
    for col,d in enumerate([1,2]):
        for name in COLORS:
            rows=dyn['divisions'][str(d)]['controlled_supplement'][name]['scan'];rows=[r for r in rows if r['tau_s']<=max_tau]
            line(ax[0,col],1000*np.array([r['tau_s'] for r in rows]),[r['decay'] for r in rows],name,f'dynamics.json d{d} frozen fixed gain')
        ax[0,col].axhline(0,color='#BBBBBB',lw=.8);ax[0,col].set(xlabel='Equal delay (ms)',ylabel=r'Minimum decay rate (s$^{-1}$)')
    limits_equal(ax[0]);ax[0,0].legend();save(fig,ax,current,'历史固定2×4增益的补充结果，原步长。所有方法使用同一增益，不重新设计控制器。左划分一、右划分二；主结果仍为零附加增益、保留物理反馈。',14)

    current='15_critical_frequency';fig,ax=canvas(2);crit=np.load(results/'critical_mechanism.npz')
    for col,d in enumerate([1,2]):
        f=crit[f'd{d}_frequency'];ref=crit[f'd{d}_Full15']
        for name in COLORS:
            yy=crit[f'd{d}_{name}']
            line(ax[0,col],f,1000*np.linalg.norm(yy,axis=1),name,f'critical_mechanism.npz d{d} {name} floor norm')
            if name!='Full15':line(ax[1,col],f,1000*np.linalg.norm(yy-ref,axis=1),name,f'critical_mechanism.npz d{d} {name} error floor norm')
        ax[0,col].set_ylabel(r'FRF norm (mm s$^2$/m)');ax[1,col].set_ylabel(r'Error norm (mm s$^2$/m)')
        for aa in ax[:,col]:aa.set_xlabel('Frequency (Hz)')
    for row in ax:limits_equal(row)
    ax[0,0].legend();save(fig,ax,current,'2.9296875ms共同稳定响应点，首次失稳Full15极点频率的0.8–1.2倍频窗。频窗由完整模型决定；三楼层物理频响二范数及误差。约18Hz的临界运动不在原0.1–10Hz扫频内。左划分一、右划分二。新增稳定性机理图。')

    current='16_sweep_speed_check';fig,ax=canvas()
    for col,d in enumerate([1,2]):
        runs=resp['divisions'][str(d)]['slow_chirp']['runs']
        for name in COLORS:line(ax[0,col],[e['sweep_rate_hz_s'] for e in runs],[e['models'][name]['quasisteady_complex_error_pct'] for e in runs],name,f'responses.json d{d} slow sweep speed check',marker={'Full15':'^','Guyan':'s','CB3':'o'}[name])
        ax[0,col].axhline(1,color='#BBBBBB',lw=.8);ax[0,col].set(xlabel=r'Sweep rate (Hz/s)',ylabel=r'Quasi-steady error (\%)')
    limits_equal(ax[0]);ax[0,0].legend();save(fig,ax,current,'慢扫频复幅值相对于同方法准稳态频响的误差；灰线1%。另以相邻两次扫速减半差不超过1%作为共同终止条件。左划分一、右划分二。该图检验扫频速度，不是缩聚精度排名。')
    (out/'figure_manifest.json').write_text(json.dumps(figures,ensure_ascii=False,indent=2),'utf-8')
    (out/'curve_provenance.json').write_text(json.dumps(series,ensure_ascii=False,indent=2),'utf-8')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--results',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();main(a.results,a.out)
