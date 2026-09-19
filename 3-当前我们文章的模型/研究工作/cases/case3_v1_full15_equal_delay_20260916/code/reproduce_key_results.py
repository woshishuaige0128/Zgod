"""Recompute principal results in a self-contained code/data copy."""
import argparse,json
from pathlib import Path
import numpy as np
from scipy import linalg as la
from full15_model import *
from case_dynamics import eigensystem

def main(out):
 _,inp,_,_=load_sources();expected={1:[.02661109322087812,.024377926642632674],2:[.9842180053037713,.15909537306366456]};rows=[]
 for d in [1,2]:
  models=family(d);ys={name:simulate(R,3,inp['eq_on_grid'][:-1])[0] for name,R in models.items()}
  for j,name in enumerate(['Guyan','CB3']):
   err=error_metrics(ys[name][:,3:],ys['Full15'][:,3:])['nrmse_range_pct'][1]
   delta=abs(err-expected[d][j]);assert delta<=1e-10
   rows.append(dict(division=d,method=name,middle_nrmse_pct=err,absolute_reproduction_delta=delta))
  for name,R in models.items():
   endpoints={1:{'Full15':(17,18),'Guyan':(14,15),'CB3':(16,17)},2:{'Full15':(21,22),'Guyan':(14,15),'CB3':(18,19)}}[d][name]
   stable=eigensystem(R,endpoints[0],H/4);unstable=eigensystem(R,endpoints[1],H/4)
   assert stable['stable'] and not unstable['stable']
   rows.append(dict(division=d,method=name,endpoint_n=list(endpoints),rho=[stable['rho'],unstable['rho']]))
 out.mkdir(exist_ok=True,parents=True);(out/'independent_reproduction.json').write_text(json.dumps(dict(status='PASS',results=rows),indent=2),'utf8');print('PASS key responses and six boundary brackets')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=Path);main(p.parse_args().out)
