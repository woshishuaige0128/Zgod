import json, math
from pathlib import Path

BLACK='#111111'; BLUE='#0756AD'; RED='#CE1017'
class Scene:
    def __init__(self, figure, width, height):
        self.figure=figure; self.width=width; self.height=height; self.objects=[]
    def add(self, kind, name, **kw):
        self.objects.append(dict(kind=kind,name=f'fig{self.figure}_{name}',**kw))
    def path(self,name,points,color=BLACK,width=3,fill='none',closed=False):
        self.add('path',name,points=points,color=color,lineWidth=width,fill=fill,closed=closed)
    def line(self,name,x1,y1,x2,y2,color=BLACK,width=3):
        self.path(name,[[x1,y1],[x2,y2]],color,width)
    def arrow(self,name,points,color=BLACK,width=3,head=17,both=False):
        self.path(name,points,color,width)
        def tip(label,p,q):
            a=math.atan2(p[1]-q[1],p[0]-q[0]); l=head; w=head*0.34
            bx=p[0]-l*math.cos(a); by=p[1]-l*math.sin(a)
            self.path(name+label,[p,[bx-w*math.sin(a),by+w*math.cos(a)],[bx+0.20*l*math.cos(a),by+0.20*l*math.sin(a)],[bx+w*math.sin(a),by-w*math.cos(a)]],color,0,color,True)
        tip('_head',points[-1],points[-2])
        if both: tip('_tail',points[0],points[1])
    def rect(self,name,x,y,w,h,fill='none',color=BLACK,width=3,radius=0):
        self.add('rect',name,x=x,y=y,w=w,h=h,fill=fill,color=color,lineWidth=width,radius=radius)
    def ellipse(self,name,x,y,w,h,fill='none',color=BLACK,width=3):
        self.add('ellipse',name,x=x,y=y,w=w,h=h,fill=fill,color=color,lineWidth=width)
    def text(self,name,x,y,w,h,text,size=36,color=BLACK,bold=False,italic=False,align='left',runs=None):
        self.add('text',name,x=x,y=y,w=w,h=h,text=text,size=size,color=color,bold=bold,italic=italic,align=align,runs=runs or [{'text':text}])
    def psi(self,name,x,y,index,size=36,color=BLACK,w=110):
        self.text(name,x,y,w,size*1.6,'ψ'+str(index),size,color,runs=[{'text':'ψ','italic':True},{'text':str(index),'baseline':-25,'scale':0.72}])
    def node(self,name,cx,cy,num,r=24,size=31,color=BLACK,fill='#FFFFFF'):
        self.ellipse(name+'_circle',cx-r,cy-r,2*r,2*r,fill,color,2.5)
        self.text(name+'_number',cx-r,cy-r+1,2*r,2*r,str(num),size,color,align='center')
    def rotation(self,name,cx,cy,color=BLACK,r=30,width=2.5,head=15):
        # Bottom semicircle, counterclockwise in mathematical coordinates.
        pts=[[cx+r*math.cos(a),cy+4+r*0.70*math.sin(a)] for a in [math.pi-i*math.pi/36 for i in range(37)]]
        self.arrow(name,pts,color,width,head)
    def support(self,name,x,y,pinned=False,width=60,stroke=3):
        gy=y
        if pinned:
            self.path(name+'_triangle',[[x,y],[x-width*.29,y+width*.44],[x+width*.29,y+width*.44]],BLACK,stroke,'none',True)
            gy=y+width*.44
        self.line(name+'_ground',x-width/2,gy,x+width/2,gy,BLACK,stroke)
        for i in range(6):
            xx=x-width/2+i*width/5
            self.line(name+'_hatch_'+str(i),xx,gy,xx-width*.19,gy+width*.24,BLACK,stroke*.7)
    def save(self,p):
        Path(p).write_text(json.dumps(dict(figure=self.figure,width=self.width,height=self.height,objects=self.objects),ensure_ascii=False,indent=2),encoding='utf-8')
