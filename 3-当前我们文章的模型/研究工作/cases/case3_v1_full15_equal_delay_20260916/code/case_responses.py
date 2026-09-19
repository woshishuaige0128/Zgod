"""Matched earthquake, sinusoid/unloading and chirp response cases."""
import argparse,json,time
from pathlib import Path
import numpy as np
from scipy import linalg as la
from scipy.signal import fftconvolve
from scipy.io import loadmat,savemat
from full15_model import *
from case_dynamics import eigensystem,compact

def harmonic_fit(t,y,f):
    mat=np.column_stack([np.cos(2*np.pi*f*t),np.sin(2*np.pi*f*t),np.ones(len(t))])
    coef=la.lstsq(mat,y)[0]
    return coef[0]-1j*coef[1]

def compare_complex(measured,expected):
    threshold=1e-6*np.max(abs(expected));valid=abs(expected)>threshold
    amp=np.full(len(expected),np.nan);phase=amp.copy()
    amp[valid]=100*abs(abs(measured[valid])/abs(expected[valid])-1)
    phase[valid]=abs(np.angle(measured[valid]/expected[valid],deg=True))
    return dict(amplitude_error_pct=amp.tolist(),phase_error_deg=phase.tolist(),valid=valid.tolist(),
                complex_error_norm_pct=float(100*la.norm(measured-expected)/la.norm(expected)))

def discrete_convolution(F,n,u):
    impulse=np.zeros(len(u));impulse[0]=1
    impulse_y,_=simulate(F,n,impulse)
    return np.column_stack([fftconvolve(impulse_y[:,j],u)[:len(u)+1] for j in range(6)])

def rk4_passive(F,u,h=H):
    """Independent first-order RK4, linear interpolation of fixed input samples."""
    r=F.order;Ac=np.block([[np.zeros((r,r)),np.eye(r)],[-la.solve(F.M,F.K),-la.solve(F.M,F.C)]])
    bc=np.r_[np.zeros(r),la.solve(F.M,F.f)]
    # Polynomial closed form of the four stages under linear input over a step.
    I=np.eye(2*r);A2=Ac@Ac;A3=A2@Ac;A4=A3@Ac
    P=I+h*Ac+h*h*A2/2+h**3*A3/6+h**4*A4/24
    b0=h/2*bc+h*h/3*Ac@bc+h**3/8*A2@bc+h**4/24*A3@bc
    b1=h/2*bc+h*h/6*Ac@bc+h**3/24*A2@bc
    x=np.zeros(2*r);y=np.zeros((len(u),3))
    for k in range(len(u)-1):x=P@x+b0*u[k]+b1*u[k+1];y[k+1]=F.Yn@x[:r]
    return y

def identify_free(y,h,target_frequency):
    """Output-only delay-embedding DMD; no theoretical roots enter the fit."""
    stride=max(1,int(round(1/(200*h))));dt=h*stride
    yy=y[int(round(.2/h))::stride][:1200]
    if len(yy)<250:raise RuntimeError('Free record too short for modal identification')
    length=50;count=len(yy)-length
    X=np.vstack([yy[j:j+count].T for j in range(length)])
    X1=np.vstack([yy[j+1:j+count+1].T for j in range(length)])
    U,s,Vh=la.svd(X,full_matrices=False);rank=min(30,int(np.count_nonzero(s/s[0]>1e-9)))
    At=U[:,:rank].T@X1@Vh[:rank].T@np.diag(1/s[:rank]);z=la.eigvals(At)
    cand=z[(np.imag(z)>1e-7)&(abs(z)<1.001)&(abs(z)>1e-10)]
    poles=np.log(cand)/dt
    if len(poles)==0:raise RuntimeError('No oscillatory poles identified')
    p=poles[np.argmin(abs(poles.imag/(2*np.pi)-target_frequency))]
    fitres=la.norm(X1-U[:,:rank]@At@U[:,:rank].T@X)/la.norm(X1)
    return dict(frequency_hz=float(p.imag/(2*np.pi)),decay=float(-p.real),rank=rank,
                embedding_residual=float(fitres),sample_step_s=dt,start_s=.2,duration_s=len(yy)*dt)

def tone_case(models,n,f,out,tag):
    poles={name:eigensystem(R,n) for name,R in models.items()}
    assert all(p['stable'] for p in poles.values())
    decay=min(p['decay'] for p in poles.values());on=max(8/decay,40/f);off=max(6/decay,20/f,6.)
    n_on=int(np.ceil(on/H));n_off=int(np.ceil(off/H));max_amplitude_error=0.;max_phase_error=0.
    # One shared duration for all models, extended only by settling checks.
    for attempt in range(4):
        t=np.arange(n_on+n_off+1)*H;u=np.cos(2*np.pi*f*t[:-1]);u[n_on:]=0
        arrays=dict(t=t,u=u);metrics={};passed=True;window=int(np.ceil(10/f/H))
        for name,R in models.items():
            y,_=simulate(R,n,u);arrays[name]=y;expected=frequency_response(R,f,n)
            a=harmonic_fit(t[n_on-window:n_on],y[n_on-window:n_on,3:],f)
            before=harmonic_fit(t[n_on-2*window:n_on-window],y[n_on-2*window:n_on-window,3:],f)
            theory=compare_complex(a,expected);settling=compare_complex(before,a)
            valid=np.array(theory['valid']);ae=np.array(theory['amplitude_error_pct'])[valid];pe=np.array(theory['phase_error_deg'])[valid]
            se=np.array(settling['amplitude_error_pct'])[valid];sp=np.array(settling['phase_error_deg'])[valid]
            good=bool(np.max(ae)<=.5 and np.max(pe)<=.5 and np.max(se)<=.5 and np.max(sp)<=.5);passed &=good
            positive=poles[name]['z'][np.imag(poles[name]['z'])>1e-8]
            target=positive[np.argmin(abs(np.angle(positive)/(2*np.pi*H)-f))]
            expectedf=float(np.angle(target)/(2*np.pi*H));expectedd=float(-np.log(abs(target))/H)
            fit=identify_free(y[n_on:,3:],H,expectedf)
            fit['expected_frequency_hz']=expectedf;fit['expected_decay']=expectedd
            fit['frequency_error_pct']=100*abs(fit['frequency_hz']/expectedf-1);fit['decay_error_pct']=100*abs(fit['decay']/expectedd-1)
            fit['passed']=bool(fit['frequency_error_pct']<=.5 and fit['decay_error_pct']<=2)
            # The independent finite convolution predicts both forcing and free
            # response from the same unreinitialized history.
            theory_y=discrete_convolution(R,n,u)
            convolution_res=float(la.norm(y-theory_y)/la.norm(y));assert convolution_res<=1e-9
            metrics[name]=dict(steady_prediction=theory,settling=settling,steady_passed=good,free_identification=fit,
                expected_amplitude=abs(expected).tolist(),expected_phase_deg=np.angle(expected,deg=True).tolist(),
                measured_amplitude=abs(a).tolist(),measured_phase_deg=np.angle(a,deg=True).tolist(),convolution_residual=convolution_res)
        if passed:break
        n_on*=2
    if not passed:raise RuntimeError('Tone did not reach predeclared steady-state tolerance')
    for name in ['Guyan','CB3']:
        metrics[name]['full_record_error']=error_metrics(arrays[name][:,3:],arrays['Full15'][:,3:])
        arrays[name+'_error']=arrays[name][:,3:]-arrays['Full15'][:,3:]
    np.savez_compressed(out/(tag+'.npz'),**arrays)
    return dict(file=tag+'.npz',n=n,tau_s=n*H,frequency_hz=f,loading_duration_s=n_on*H,unloading_duration_s=n_off*H,
                duration_attempts=attempt+1,models=metrics)

def slow_chirp(models,n,peak_hz,out,tag):
    F=models['Full15'];e=eigensystem(F,n);positive=e['z'][np.imag(e['z'])>1e-8]
    z=positive[np.argmin(abs(np.angle(positive)/(2*np.pi*H)-peak_hz))];decay=-np.log(abs(z))/H
    f0=.85*peak_hz;f1=1.15*peak_hz;bandwidth=decay/(2*np.pi)
    duration=max(40.,10/decay,(f1-f0)/(.05*bandwidth**2));pre=max(8/e['decay'],20/f0)
    sample_freq=np.linspace(f0+.1*(f1-f0),f1-.1*(f1-f0),81);runs=[];last=None
    for factor in [1,2,4,8]:
        ns=int(np.ceil(duration*factor/H));np0=int(np.ceil(pre/H));tp=np.arange(np0)*H;ts=np.arange(ns+1)*H
        rate=(f1-f0)/(ns*H);phase=np.r_[2*np.pi*f0*tp,2*np.pi*f0*(np0*H)+2*np.pi*(f0*ts+.5*rate*ts**2)]
        u=np.cos(phase[:-1]);t=np.arange(len(u)+1)*H;arr=dict(t=t,u=u,frequency=f0+rate*ts,frequency_samples=sample_freq)
        summaries={};amps={}
        for name,R in models.items():
            y,_=simulate(R,n,u);arr[name]=y;measured=[]
            for f in sample_freq:
                center=np0+int(round((f-f0)/rate/H));half=int(round(5/f/H));sel=slice(center-half,center+half+1)
                w=np.hanning(2*half+1);ph=phase[sel];design=np.column_stack([np.cos(ph),np.sin(ph),np.ones(len(ph))])
                coef=la.lstsq(design*w[:,None],y[sel,3:]*w[:,None])[0];measured.append(coef[0]-1j*coef[1])
            measured=np.array(measured);expected=np.array([frequency_response(R,f,n) for f in sample_freq]);amps[name]=measured
            arr[name+'_demodulated']=measured;arr[name+'_steady_prediction']=expected
            summaries[name]=dict(quasisteady_complex_error_pct=float(100*la.norm(measured-expected)/la.norm(expected)),
                change_from_previous_pct=None if last is None else float(100*la.norm(measured-last[name])/la.norm(expected)))
        fn=f'{tag}_speed{factor}.npz';np.savez_compressed(out/fn,**arr)
        runs.append(dict(file=fn,duration_s=ns*H,prelude_s=np0*H,sweep_rate_hz_s=rate,speed_factor=factor,models=summaries))
        converged=last is not None and all(s['quasisteady_complex_error_pct']<=1 and s['change_from_previous_pct']<=1 for s in summaries.values())
        last=amps
        if converged:break
    return dict(n=n,tau_s=n*H,band_hz=[f0,f1],selection='85%-115% of reference second peak at normal nonzero delay',
                criterion='All methods: complex amplitude versus FRF and change on halving speed <=1%',converged=bool(converged),runs=runs)

def main(out,dynamicfile):
    dyn=json.loads(dynamicfile.read_text('utf-8'));assert dyn['status']=='PASS';out.mkdir(parents=True,exist_ok=True)
    frame,inputs,_,gain=load_sources();time_grid=inputs['time'];eq=inputs['eq_on_grid'];fast=inputs['chirp'][:,1]
    assert len(eq)==40961 and len(time_grid)==40961
    F=full_model(1);passive,_=simulate(F,0,eq[:-1]);rk=rk4_passive(F,eq)
    np.savez_compressed(out/'passive_references.npz',t=time_grid,u=eq,CR=passive,RK4=rk)
    results=dict(h=H,passive_integrator_error=error_metrics(passive[:,3:],rk),divisions={})
    for d in [1,2]:
        D=dyn['divisions'][str(d)];models=family(d);data=dict(earthquake={},fast_chirp={},tones=[],controlled={});results['divisions'][str(d)]=data
        for n in D['selection']['representative_n']:
            for signal,u in [('earthquake',eq),('fast_chirp',fast)]:
                ys={name:simulate(R,n,u[:-1])[0] for name,R in models.items()};metrics={};arrays=dict(t=time_grid,u=u,**ys)
                reference=ys['Full15'][:,3:]
                for name,R in models.items():
                    y=ys[name];pred=discrete_convolution(R,n,u[:-1]);check=float(la.norm(y-pred)/la.norm(y));assert check<=1e-9
                    metrics[name]=dict(to_matched_full=error_metrics(y[:,3:],reference),convolution_residual=check,
                        story_drift_to_matched_full=error_metrics(drift(y[:,3:]),drift(reference)))
                    if signal=='earthquake':
                        metrics[name]['to_original_passive_CR']=error_metrics(y[:,3:],passive[:,3:]);metrics[name]['to_original_passive_RK4']=error_metrics(y[:,3:],rk)
                        parts=[y[:,3:]-reference,reference-passive[:,3:],passive[:,3:]-rk]
                        total=y[:,3:]-rk;closure=la.norm(sum(parts)-total)/max(la.norm(total),la.norm(rk)*1e-15);assert closure<=1e-10
                        metrics[name]['response_decomposition_residual']=float(closure)
                    if name!='Full15':arrays[name+'_error_prediction']=pred[:,3:]-discrete_convolution(models['Full15'],n,u[:-1])[:,3:]
                fn=f'd{d}_n{n}_{signal}.npz';np.savez_compressed(out/fn,**arrays);data[signal][str(n)]=dict(file=fn,n=n,tau_s=n*H,models=metrics)
        print(f'Division {d}: earthquakes and fast chirps complete',flush=True)
        for n in sorted(set([D['selection']['normal_n'],D['selection']['near_n']])):
            for j,f in enumerate(D['frequency_cases'][str(n)]['tone_frequencies_hz']):
                entry=tone_case(models,n,f,out,f'd{d}_n{n}_tone{j+1}');data['tones'].append(entry)
                print(f'Division {d}, n={n}, tone {f:.5f} Hz complete',flush=True)
                (out/'responses.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),'utf-8')
        n=D['selection']['normal_n'];peaks=D['frequency_cases'][str(n)]['tone_frequencies_hz']
        data['slow_chirp']=slow_chirp(models,n,peaks[1],out,f'd{d}_n{n}_slow_chirp') if len(peaks)>=2 else dict(status='not applicable; second Full15 peak absent in fixed band',runs=[])
        controlled=family(d,gain=gain)
        for n in D['selection']['representative_n']:
            stable=all(eigensystem(R,n)['stable'] for R in controlled.values())
            if not stable:data['controlled'][str(n)]=dict(n=n,stable=False,response='not computed as a stable accuracy case');continue
            ys={name:simulate(R,n,eq[:-1])[0] for name,R in controlled.items()};fn=f'd{d}_n{n}_controlled_eq.npz'
            np.savez_compressed(out/fn,t=time_grid,u=eq,**ys)
            data['controlled'][str(n)]=dict(n=n,stable=True,file=fn,models={name:error_metrics(y[:,3:],ys['Full15'][:,3:]) for name,y in ys.items()})
        (out/'responses.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),'utf-8')
    results['status']='computed_pending_independent_QA';(out/'responses.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),'utf-8')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--dynamics',type=Path,required=True);a=p.parse_args();main(a.out,a.dynamics)
