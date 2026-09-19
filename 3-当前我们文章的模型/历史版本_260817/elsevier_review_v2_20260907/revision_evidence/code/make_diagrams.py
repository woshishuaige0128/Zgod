from pathlib import Path
import subprocess,shutil,json,hashlib,tempfile,re
ROOT=Path(__file__).resolve().parents[2];TMP=Path(__file__).resolve().parent
NEW=ROOT.parent/'260817/elsevier_review_v2_20260907';OUT=NEW/'submit_figure'
if Path(__file__).resolve().parent.name=='code' and Path(__file__).resolve().parent.parent.name=='revision_evidence':
    NEW=Path(__file__).resolve().parents[2];OUT=NEW/'submit_figure'
    TMP=Path(tempfile.gettempdir())/'rths_review_v2_diagram_build';TMP.mkdir(exist_ok=True)
TEMP=TMP/'diagram_build';TEMP.mkdir(exist_ok=True)
base=r'\begin{tikzpicture}[>=Stealth,every node/.style={font=\fontsize{9}{11}\selectfont},line width=.7pt]'+'\n'
end='\n'+r'\end{tikzpicture}'
def line(x1,y1,x2,y2,options=''):
    return rf'\draw[{options}] ({x1:g},{y1:g})--({x2:g},{y2:g});'+'\n'
def node(x,y,value,options=''):
    return rf'\node[{options}] at ({x:g},{y:g}) {{{value}}};'+'\n'
def support(x,y=0,pin=False,color='black'):
    s=''
    if pin:
        s+=rf'\draw[{color}] ({x:g},{y:g})--({x-.15:g},{y-.28:g})--({x+.15:g},{y-.28:g})--cycle;'+'\n';y-=.28
    s+=line(x-.24,y,x+.24,y,color)
    for d in [-.20,-.10,0,.10,.20]:s+=line(x+d,y,x+d-.10,y-.14,color+',line width=.4pt')
    return s
def frame(prototype=False):
    s=''
    for x in [0,2,4,6]:s+=line(x,0,x,5.1)+support(x,pin=prototype and x in [2,4])
    for y in [1.7,3.4,5.1]:s+=line(0,y,6,y)
    return s

# The loop is deliberately the signal path of the retained characteristic equation.
loop=(OUT/'fig01_force_feedback.tex').read_text(encoding='utf-8')
if r'\begin{document}' in loop:loop=loop.split(r'\begin{document}',1)[1].split(r'\end{document}',1)[0].strip()
loop=loop.replace('Channel delays\\\\Force placement $\\mathbf S_a^{\\mathsf T}$','Channel delays $\\mathbf H_a(z)$\\\\Force placement $\\mathbf S_a^{\\mathsf T}$')
loop=loop.replace('Channel delays\\\\Sum over $\\ell$','Channel delays $z^{-n_\\ell}$\\\\Sum over $\\ell$')

# Prototype frame and the original I-beam dimensions are retained.
geom=base+frame(prototype=True)
for x in [0,2,4]:geom+=rf'\draw[<->] ({x},-.85)--({x+2},-.85) node[midway,fill=white] {{762}};'+'\n'
for j in range(3):geom+=rf'\draw[<->] (6.6,{1.7*j:g})--(6.6,{1.7*(j+1):g}) node[midway,fill=white] {{635}};'+'\n'
for y in [.85,2.55,4.25]:geom+=node(-.42,y,r'W5$\times$16','rotate=90')
geom+=node(3,5.6,'Reference frame','red')
# Exact section dimension labels, illustrative proportions (all dimensions in mm).
geom+=r'''\begin{scope}[shift={(8.6,1.0)}]
\draw (0,0) rectangle (2.6,.41);
\draw (0,3.02) rectangle (2.6,3.43);
\draw (1.095,.41) rectangle (1.505,3.02);
\draw[<->] (0,3.8)--(2.6,3.8) node[midway,fill=white] {38};
\draw[<->] (-.45,0)--(-.45,3.43) node[midway,fill=white,rotate=90] {50};
\draw[<->] (3.03,3.02)--(3.03,3.43) node[midway,right] {6};
\draw[<->] (1.095,1.65)--(1.505,1.65);
\draw (1.505,1.65)--(2.35,1.65) node[right] {6};
\node[red] at (1.3,-.55) {Beam I section};
\end{scope}
'''+end

# All original global node and coordinate labels are kept; only numerical support fix is red.
dofs=base
for x in [0,2,4,6]:dofs+=line(x,0,x,5.1)+support(x,color='red' if x in [2,4] else 'black')
for floor in range(4):
    y=floor*1.7
    if floor:dofs+=line(0,y,6,y)
    for j,x in enumerate([0,2,4,6]):
        dofs+=node(x-.36,y+.38,str(4*floor+j+1),'circle,draw,inner sep=1.2pt')
        if floor:
            idx=(floor-1)*5+j+2
            dofs+=rf'\draw[->] ({x-.22:g},{y-.05:g}) arc (195:350:.24);'+'\n'
            dofs+=node(x+.36,y-.31,rf'$\psi_{{{idx}}}$')
    if floor:dofs+=rf'\draw[->] (6.2,{y:g})--(7.1,{y:g}) node[right] {{$\psi_{{{(floor-1)*5+1}}}$}};'+'\n'
dofs+=r'\draw[->] (-.7,5.1)--(-.7,5.95) node[above] {$y$};'+'\n'+r'\draw[->] (6.4,-.45)--(7.3,-.45) node[right] {$x$};'+end

# The two local structures stay separate. Black = geometry; red = retained physical DOFs.
def local(div,physical=False):
    s='';floors=2 if div==1 and physical else 3
    if physical:
        xs=[0,1.7]
        for x in xs:s+=line(x,0,x,floors*1.7)+support(x,pin=(x==1.7))
        for j,x in enumerate(xs):s+=node(x-.32,.32,str(j+1),'circle,draw,red,inner sep=1pt')
        for f in range(1,floors+1):s+=line(0,f*1.7,1.7,f*1.7)
        present={f:[0,1] for f in range(1,floors+1)}
    else:
        xs=[0,1.7,3.4,5.1]
        for x in xs[2:]:s+=line(x,0,x,5.1)+support(x,pin=(x==3.4))
        for j in [2,3]:s+=node(xs[j]-.32,.32,str(j+1),'circle,draw,inner sep=1pt')
        if div==1:
            s+=line(0,3.4,0,5.1)+line(1.7,3.4,1.7,5.1)
            s+=line(0,5.1,5.1,5.1);present={1:[1,2,3],2:[0,1,2,3],3:[0,1,2,3]}
            for f in [1,2]:s+=line(1.7,f*1.7,5.1,f*1.7)
        else:
            for f in [1,2,3]:s+=line(1.7,f*1.7,5.1,f*1.7)
            present={f:[1,2,3] for f in [1,2,3]}
    for f,js in present.items():
        y=f*1.7
        for j in js:
            x=xs[j] if not physical else xs[j];idx=(f-1)*5+j+2
            # Node labels use the global numbering of the complete frame.
            s+=node(x-.32,y+.32,str(4*f+j+1),'circle,draw,inner sep=1pt'+(',red' if physical and f==1 else ''))
            retained=(not physical and j==2);color='red' if retained else 'black'
            s+=rf'\draw[->,{color}] ({x-.19:g},{y-.06:g}) arc (195:350:.20);'+'\n'
            s+=node(x+.29,y-.27,rf'$\psi_{{{idx}}}$',color)
        horizontal=(f-1)*5+1
        retain_h=(not physical) or (f in ([1,2] if div==1 else [1,3]))
        col='red' if retain_h else 'black';xend=1.7 if physical else 5.1
        s+=rf'\draw[->,{col}] ({xend+.15:g},{y:g})--({xend+.8:g},{y:g}) node[right] {{$\psi_{{{horizontal}}}$}};'+'\n'
    return s
divisions=base
for div,yshift in [(1,6.5),(2,0)]:
    divisions+=rf'\begin{{scope}}[shift={{(0,{yshift})}}]'+'\n'+local(div)
    divisions+=node(2.5,5.8,f'({"a" if div==1 else "b"}) Division {"I"*div}: numerical substructure','red')
    divisions+=node(7,2.8,r'$+$')
    divisions+=r'\begin{scope}[shift={(8.15,0)}]'+'\n'+local(div,True)
    divisions+=node(1.1,5.8,'Physical substructure','red')+r'\end{scope}'+'\n'+r'\end{scope}'+'\n'
divisions+=node(5.6,-.65,'Red coordinates are retained; the other labelled coordinates are condensed.','red')+end

manifest=[]
for name,body in [('fig01_force_feedback',loop),('fig02_geometry',geom),('fig03_dofs',dofs),('fig04_divisions',divisions)]:
    source=r'''\documentclass[tikz,border=3pt]{standalone}
\usepackage{amsmath,bm,xcolor}
\usetikzlibrary{arrows.meta}
\begin{document}
'''+body+'\n'+r'\end{document}'+'\n'
    (OUT/(name+'.tex')).write_text(source,encoding='utf-8')
    (TEMP/(name+'.tex')).write_text(source,encoding='utf-8')
    p=subprocess.run(['pdflatex','-interaction=nonstopmode','-halt-on-error',name+'.tex'],cwd=TEMP,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    (TEMP/(name+'_build.txt')).write_bytes(p.stdout);assert p.returncode==0,p.stdout[-2000:]
    shutil.copy2(TEMP/(name+'.pdf'),OUT/(name+'.pdf'))
    import fitz
    pdf=fitz.open(OUT/(name+'.pdf'));pdf[0].get_pixmap(dpi=600).save(OUT/(name+'.png'));pdf.close()
    manifest.append({'file':name,'pdf_sha256':hashlib.sha256((OUT/(name+'.pdf')).read_bytes()).hexdigest()})
(NEW/'revision_evidence/data/diagram_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
if Path(__file__).resolve()!=(NEW/'revision_evidence/code/make_diagrams.py').resolve():shutil.copy2(__file__,NEW/'revision_evidence/code/make_diagrams.py')
print('DIAGRAMS_COMPILED=4')
