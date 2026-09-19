from pathlib import Path
import json, re, hashlib, csv, shutil
import numpy as np
from scipy.io import loadmat, savemat
from scipy.linalg import eig

ROOT=Path(r'D:/JZ_PhD/10_论文_Papers/Li/RHTS/liangyustability-master')
OUT=ROOT.parent/'260817/elsevier_review_20260906'
AUD=ROOT/'figure/表3至表5_按当前出图设置核查_20260906'
FIG=OUT/'submit_figure'
font=r'font=\fontsize{9}{11}\selectfont'
(FIG/'fig01_force_feedback.tex').write_text(r'''\begin{tikzpicture}[>=Stealth, every node/.style={font=\fontsize{9}{11}\selectfont}, draw=red, text=red,
block/.style={draw=red,rectangle,align=center,minimum height=12mm,inner sep=3mm}]
\node[draw=red,circle,inner sep=1mm] (sum) at (-4,0) {$\Sigma$};
\node[block,minimum width=40mm] (cr) at (0,0) {CR update\\Numerical inertia, $\mathbf C_0$, $\mathbf K_0$};
\node (state) at (4,0) {$\bm q,\dot{\bm q}$};
\draw[->,red] (-5.3,0) node[above] {$\bm f_{\mathrm{red}}$} -- (sum);
\draw[->,red] (sum) -- (cr);
\draw[->,red] (cr) -- (state);
\node[block,minimum width=34mm] (lqr) at (1.9,2.1) {LQR force\\$-\mathbf K_x\mathbf S_a\bm q-\mathbf K_v\mathbf S_a\dot{\bm q}$};
\node[block] (ldelay) at (-2.1,2.1) {Channel delays\\Force placement $\mathbf S_a^{\mathsf T}$};
\draw[->,red] (3.2,0) |- (lqr.east);
\draw[->,red] (lqr) -- (ldelay);
\draw[->,red] (ldelay.west) -| node[pos=.9,left] {$+$} (sum.north);
\node[block,minimum width=34mm] (reaction) at (1.9,-2.1) {Physical reaction terms\\$\mathbf K_\ell\bm q+\mathbf C_\ell\dot{\bm q}$};
\node[block] (rdelay) at (-2.1,-2.1) {Channel delays\\Sum over $\ell$};
\draw[->,red] (3.2,0) |- (reaction.east);
\draw[->,red] (reaction) -- (rdelay);
\draw[->,red] (rdelay.west) -| node[pos=.9,left] {$-$} (sum.south);
\end{tikzpicture}
''',encoding='utf-8')

def frame(x0=0,y0=0,scale=1,fill=None,dofs=False,actuators=(),title=None):
    a=[rf'\begin{{scope}}[shift={{({x0},{y0})}},scale={scale}]']
    if fill:
        a.append(rf'\fill[red,opacity=.06] (0,0) rectangle (2,{fill*1.7});')
    for x in (0,2,4,6):
        a.append(rf'\draw[red,line width=.8pt] ({x},0)--({x},5.1);')
        a.append(rf'\draw[red,line width=.7pt] ({x-.24},0)--({x+.24},0);')
        for dx in (-.2,-.1,0,.1,.2):
            a.append(rf'\draw[red,line width=.4pt] ({x+dx},0)--({x+dx-.12},-.15);')
    for floor in (1,2,3):
        y=1.7*floor
        a.append(rf'\draw[red,line width=.8pt] (0,{y})--(6,{y});')
        if dofs:
            for j,x in enumerate((0,2,4,6)):
                index=(floor-1)*5+j+2
                a.append(rf'\draw[red,->] ({x+.22},{y}) arc (0:285:.22);')
                a.append(rf'\node[above right,text=red] at ({x+.16},{y+.18}) {{$\psi_{{{index}}}$}};')
            index=(floor-1)*5+1
            a.append(rf'\draw[red,->] (-1.25,{y})--(-.2,{y}) node[pos=0,above] {{$\psi_{{{index}}}$}};')
        if floor in actuators:
            index=(floor-1)*5+1
            a.append(rf'\draw[red,->,line width=1pt] (-1.15,{y})--(-.13,{y}) node[pos=0,above] {{$\psi_{{{index}}}$}};')
    if title:a.append(rf'\node[text=red] at (3,-.65) {{{title}}};')
    a.append(r'\end{scope}')
    return '\n'.join(a)

base=rf'\begin{{tikzpicture}}[>=Stealth,every node/.style={{{font},text=red}}]'+'\n'
geom=base+frame()
for x in (0,2,4):
    geom+=rf'\draw[red,<->] ({x},-.6)--({x+2},-.6) node[midway,fill=white] {{762}};'+'\n'
for i in range(3):
    geom+=rf'\draw[red,<->] (6.75,{1.7*i})--(6.75,{1.7*(i+1)}) node[midway,fill=white] {{635}};'+'\n'
geom+=r'\node[red,align=center] at (3,5.8) {Three bays; three storeys\\Fixed bases in the accuracy model};'+'\n'+r'\end{tikzpicture}'
(FIG/'fig02_geometry.tex').write_text(geom,encoding='utf-8')
(FIG/'fig03_dofs.tex').write_text(base+frame(dofs=True)+'\n'+r'\end{tikzpicture}',encoding='utf-8')
div=base+frame(scale=.77,fill=2,actuators=(1,2),title='(a) Division I')+'\n'
div+=frame(x0=6.45,scale=.77,fill=3,actuators=(1,3),title='(b) Division II')+'\n'+r'\end{tikzpicture}'
(FIG/'fig04_divisions.tex').write_text(div,encoding='utf-8')

# Include numeric matrices so the explicitly stated benchmark can be reconstructed.
params=OUT/'supplementary_data';params.mkdir(exist_ok=True)
for fig in ('Fig06','Fig07'):
    item=next(x for x in json.loads((AUD/'results/python_results.json').read_text(encoding='utf-8'))['source_comparisons'] if x['figure']==fig)
    d=loadmat(item['fresh_snapshot'])
    selected={k:v for k,v in d.items() if k.startswith(('M_','C_','K_','T_')) or k in ('master_dofs','slave_dofs')}
    div='I' if fig=='Fig06' else 'II'
    savemat(params/f'division_{div}_matrices.mat',selected)
    for k in ('M_full','C_full','K_full'):
        if fig=='Fig06':np.savetxt(params/(k+'.csv'),d[k],delimiter=',',fmt='%.17g')
(params/'README.txt').write_text('''Coordinate order: each storey contributes [horizontal translation, rotations at nodes 1,2,3,4].
Storey translations are coordinates 1,6,11. Units: m, rad, kg, N, s.
Matrices come from the fresh MATLAB runs used in the 2026-09-06 table audit.
They define the accuracy models only; they are not a recovered source for the historical stability boundaries.
The transformations act on [master_dofs,slave_dofs] and must be unpermuted to recover coordinates 1..15.
Guyan is the retained-equation implementation, not the congruent static projection.
The three lowest fixed-interface modes form the Craig-Bampton enrichment.
''',encoding='utf-8')

# Recompute the extra prose metrics independently using the existing response files.
extra={}
source=json.loads((AUD/'results/python_results.json').read_text(encoding='utf-8'))['source_comparisons']
for item in source:
    a=np.loadtxt(item['plotted_csv'],delimiter=',',skiprows=1)
    t=a[:,0]
    if item['figure'] in ('Fig07','Fig09'):
        # Same continuous-time/trapezoidal definition as the manuscript, full 0--40 s.
        ref=a[:,4]
        vals=[]
        for col in (5,6):
            vals.append(float(100*np.sqrt(np.trapezoid((a[:,col]-ref)**2,t)/40)/np.ptp(ref)))
        extra[item['figure']+'_middle_NRMSE']=vals
    if item['figure']=='Fig08':
        extra['reference_first_storey_abs_peak_time']=float(t[np.argmax(abs(a[:,1]))])
    if item['figure']=='Fig09':
        mask=(t>=38)&(t<=38.3)
        extra['late_first_storey_Guyan_to_reference_ptp']=float(np.ptp(a[mask,2])/np.ptp(a[mask,1]))
        extra['late_third_storey_Guyan_to_reference_ptp']=float(np.ptp(a[mask,8])/np.ptp(a[mask,7]))
extra['fundamental_crossing_s']=(2.707425741915-.1)/.2475
(OUT/'revision_evidence/additional_metrics.json').write_text(json.dumps(extra,indent=2),encoding='utf-8')

# Final contextual clean-up: all newly changed prose is red.
p=OUT/'main.tex';s=p.read_text(encoding='utf-8')
old=next(x for x in s.split('\n\n') if x.startswith('The formulations of Sections'))
s=s.replace(old,r'\rev{The benchmark uses two coordinate selections associated with the designated substructure divisions. The frame properties, implemented accuracy models, excitations and evaluation indices are specified below.}')
s=s.replace('built from the geometry of the multi-axial',r'built from the \rev{geometry} of the multi-axial')
s=s.replace('The nodal rotations mainly represent local bending and are coupled to the horizontal displacements through the off-diagonal terms of the stiffness matrix, and they are condensed accordingly. Condensing all rotations would shift the higher modes, and several rotations of the numerical substructure are therefore kept.',r'\rev{The retained rotations preserve selected bending coordinates; the remaining rotations are recovered through the reduction basis.}')
# Color the generic projection sentence if altered in future; leave the valid formulation intact now.
p.write_text(s,encoding='utf-8')
print(json.dumps(extra,indent=2))
