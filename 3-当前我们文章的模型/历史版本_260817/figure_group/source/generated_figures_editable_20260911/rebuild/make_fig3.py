from pathlib import Path
from scene import Scene,BLACK,BLUE
s=Scene(3,1122,1402)
xs=[102,359,616,872]; ys=[1252,910,574,241]
for j,x in enumerate(xs):
    s.line(f'column_{j+1}',x,ys[3],x,ys[0]-(15 if j in [1,2] else 0),width=3.6)
for level in range(1,4):
    y=ys[level]
    s.arrow(f'floor_{level}_translation',[[xs[0],y],[1023,y]],width=3.4,head=27)
    s.psi(f'floor_{level}_psi',1033,y-31,1+(level-1)*5,44,w=89)
    for j,x in enumerate(xs):
        s.rotation(f'rotation_{level}_{j+1}',x,y+3,r=34,width=3,head=21)
        s.psi(f'psi_{level}_{j+1}',x+28,y+29,2+(level-1)*5+j,43,w=95)
for level in range(4):
    for j,x in enumerate(xs):
        cx=x-39 if level<3 else x-4
        cy=ys[level]-53 if level else 1187
        s.node(f'node_{level*4+j+1}',cx,cy,level*4+j+1,r=31,size=40)
for j,x in enumerate(xs):
    s.support(f'support_{j+1}',x,ys[0]-(14 if j in [1,2] else 0),pinned=j in [1,2],width=80,stroke=4)
    if j in [1,2]:s.ellipse(f'pin_{j+1}',x-6,ys[0]-20,12,12,'#FFFFFF',BLACK,3)
s.arrow('axis_y',[[44,215],[44,84]],'#0069DF',3.8,head=32)
s.text('axis_y_label',28,5,65,70,'y',55,'#003B80',italic=True)
s.arrow('axis_x',[[933,1346],[1057,1346]],'#0069DF',3.8,head=32)
s.text('axis_x_label',1070,1300,52,74,'x',55,'#003B80',italic=True)
s.save(Path(__file__).with_name('fig3.json'))
print('Figure 3:',len(s.objects),'native objects')
