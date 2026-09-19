import json,hashlib
from pathlib import Path
import numpy as np
from PIL import Image,ImageOps,ImageDraw,ImageFont
import fitz
from delay_model import CASE

def main():
    rows=json.loads((CASE/'results/selected_delays.json').read_text('utf-8'))
    records=json.loads((CASE/'results/figure_records.json').read_text('utf-8'))
    assert len(records)==2*len(rows)+3
    digest=lambda x:hashlib.sha256(np.asarray(x,dtype=np.float64).tobytes()).hexdigest()
    checks=[];limits={}
    def check(name,value):
        checks.append({'name':name,'passed':bool(value)});assert value,name
    for r in records:
        with fitz.open(CASE/'figures'/r['pdf']) as doc:
            check(r['name']+'_single_page',len(doc)==1)
            check(r['name']+'_vector',not doc[0].get_images())
            check(r['name']+'_embedded_fonts',bool(doc[0].get_fonts()) and all(f[1] for f in doc[0].get_fonts()))
            check(r['name']+'_no_type3',all('Type3' not in f[2] for f in doc[0].get_fonts()))
        im=Image.open(CASE/'figures'/r['png']);check(r['name']+'_600dpi',min(im.info.get('dpi',(0,0)))>=599)
        if r['kind']!='case':continue
        data=np.load(CASE/'results'/f"{r['key']}_responses.npz");t=data['time_s'];exc=r['input']
        for floor in range(3):
            ref=data[f'{exc}_Uncondensed19_physical_mm'][:,floor]
            for col in range(2):
                a=r['axes'][floor*2+col]
                names=['Full15','Uncondensed19','Guyan6','CB12'] if col==0 else ['Guyan6','CB12']
                for idx,name in enumerate(names):
                    y=data[f'{exc}_{name}_physical_mm'][:,floor].copy()
                    if col:y-=ref
                    if r['unstable']:y=np.where(abs(y)>1e-12,abs(y),np.nan)
                    line=a['lines'][idx]
                    check(f"{r['name']}_{floor}_{col}_{name}_x",line['x_sha256']==digest(t))
                    check(f"{r['name']}_{floor}_{col}_{name}_y",line['y_sha256']==digest(y))
                if not r['unstable']:
                    key=(exc,floor,col)
                    if key not in limits:limits[key]=a['ylim']
                    check(f"{r['name']}_{floor}_{col}_shared_limits",a['ylim']==limits[key])
    # Review contact sheets are independent exports for visual inspection.
    target=CASE.parents[1]/'temp/divisionII_delays_20260916/visual_qa';target.mkdir(parents=True,exist_ok=True)
    font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',25)
    for start in range(0,len(records),6):
        canvas=Image.new('RGB',(1800,3*650),'#e5ebef');draw=ImageDraw.Draw(canvas)
        for j,r in enumerate(records[start:start+6]):
            im=Image.open(CASE/'figures'/r['png']).convert('RGB');im.thumbnail((880,605))
            x=(j%2)*900+(900-im.width)//2;y=(j//2)*650+40
            canvas.paste(im,(x,y));draw.text(((j%2)*900+12,(j//2)*650+7),r['name'],font=font,fill='black')
        canvas.save(target/f'contact_{start+1:02d}.png')
    result={'status':'NUMERICAL_PASS','checks':len(checks),'figures':len(records),'curve_data_and_scaling_verified':True,'checks_detail':checks,'visual_review':'pending'}
    (CASE/'results/figure_checks.json').write_text(json.dumps(result,indent=2),'utf-8')
    print('FIGURE_CHECKS',len(checks),'PASS; visual contacts',len(list(target.glob('contact_*.png'))))

if __name__=='__main__':main()
