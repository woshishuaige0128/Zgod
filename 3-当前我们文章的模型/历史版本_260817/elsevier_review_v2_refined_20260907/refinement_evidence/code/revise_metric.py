from pathlib import Path
import csv,json,shutil,difflib,re
import numpy as np
TMP=Path(__file__).resolve().parent;NEW=TMP.parents[1].parent/'260817/elsevier_review_v2_refined_20260907'
if TMP.name=='code' and TMP.parent.name=='refinement_evidence':NEW=TMP.parents[1]
DATA=NEW/'refinement_evidence/data';EV=NEW/'refinement_evidence'
source=json.loads((DATA/'explanation_calculations.json').read_text('utf-8'))
csvrows=list(csv.DictReader((DATA/'new_modal_shares.csv').open(encoding='utf-8-sig')))
csvshare={(int(r['division']),r['method'],int(r['physical_dof'])):float(r['share']) for r in csvrows}
rows=[];models=[];checks=[]
for c in source['actuator_contributions']:
 div=c['division'];method=c['method'];total=0
 for j,full,red,old in zip(c['actuated_dofs'],c['full_shares'],c['reduced_shares'],c['relative_changes']):
  value=abs(red/full-1);ref=abs(csvshare[div,method,j]-csvshare[div,'Full',j])/csvshare[div,'Full',j]
  error=abs(value-ref);checks.append({'check':f'{div}/{method}/{j}','error':error,'tolerance':1e-10,'passed':error<1e-10});assert error<1e-10
  rows.append({'division':div,'method':method,'physical_dof':j,'full_share':full,'reduced_share':red,'absolute_relative_deviation':value});total+=value
 assert total>=0
 models.append({'division':div,'method':method,'previous_signed_sum':c['delta_E'],'absolute_relative_deviation_sum':total,'actuated_dofs':c['actuated_dofs']})
for r in rows:r['delta_E']=next(m['absolute_relative_deviation_sum'] for m in models if (m['division'],m['method'])==(r['division'],r['method']))
with (DATA/'actuator_share_deviations.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
(DATA/'modal_share_deviation.json').write_text(json.dumps({'definition':'sum of coordinate-wise absolute relative modal-share deviations','formula':'sum_k abs((E_red[d_k]-E_full[d_k])/E_full[d_k])','selected_modes':5,'per_coordinate':rows,'model_totals':models},ensure_ascii=False,indent=2),encoding='utf-8')
(EV/'validation/absolute_metric_numeric_checks.json').write_text(json.dumps({'status':'PASS','checks':checks,'max_error':max(x['error'] for x in checks)},indent=2),encoding='utf-8')

before=(EV/'baseline/main.tex').read_text('utf-8');after=before;ops=[]
def change(old,new,reason):
 global after
 assert after.count(old)==1,(old,after.count(old))
 after=after.replace(old,new,1);ops.append({'old':old,'new':new,'reason':reason})
change('the corresponding natural frequencies (Hz) are listed beneath each panel.','the corresponding natural frequencies (Hz) are listed within each panel.','图6频率已移入相应子图，使用8pt。')
change('while a modal redistribution ratio measures the change in low-order modal content associated with the actuator-driven DOFs.',r'while a \rev{modal-share deviation measures the magnitude of the change in low-order modal content at the actuator-driven DOFs.}','引言中的指标名称和用途与绝对变化定义一致。')
change('The change in low-order modal distribution is described by a modal redistribution ratio, which combines the relative changes at the actuated coordinates.','The change in low-order modal distribution is measured by a modal-share deviation, which combines the magnitudes of the relative changes at the actuated coordinates.','按用户选择将指标用于衡量变化幅度。')
change('The modal redistribution ratio is then obtained as',r'The \rev{modal-share deviation} is then obtained as','统一公式引导语。')
oldformula=r'''\Delta E=\sum_{k=1}^{n_{\mathrm{a}}}
	\frac{E^{\mathrm{red}}(d_{k})-E^{\mathrm{full}}(d_{k})}{E^{\mathrm{full}}(d_{k})}.'''
newformula=r'''\rev{\Delta E=\sum_{k=1}^{n_{\mathrm{a}}}
	\left|\frac{E^{\mathrm{red}}(d_{k})-E^{\mathrm{full}}(d_{k})}{E^{\mathrm{full}}(d_{k})}\right|.}'''
change(oldformula,newformula,'逐个坐标先取绝对值再相加；不是对原求和结果取绝对值。')
change(r'Equation \eqref{eq:energy-change} sums the relative change of the modal share of each actuated coordinate. \rev{The terms have separate denominators and retain their signs; their sum is a modal-share indicator rather than a total energy-transfer measure or a stability criterion.}',r'\rev{Equation \eqref{eq:energy-change} sums the magnitudes of the relative modal-share changes at the actuated coordinates. A smaller value indicates better preservation of the selected modal distribution.}','以偏离程度说明指标，删除围绕正负和抵消的旧论述。')
change('The modal redistribution ratio finally describes how the low-order modal shares at the actuated coordinates change under condensation.','The modal-share deviation finally measures the change in low-order modal shares at the actuated coordinates under condensation.','统一结果章节的指标介绍。')
change(r'\subsection{Modal redistribution ratio and applicability of the two methods}',r'\subsection{\rev{Modal-share deviation} and applicability of the two methods}','章节标题随指标名称更新。')
change(r'The modal redistribution ratio of Eq. \eqref{eq:energy-change} is listed in Table \ref{tab:energy}. \rev{It is evaluated from the full-frame accuracy models using their first five modes. Guyan gives \(-0.0414\) in division I and \(0.8914\) in division II; the corresponding Craig--Bampton values are \(0.0039\) and \(0.0365\). Craig--Bampton is closer to zero in magnitude in both divisions, indicating a smaller change in the selected coordinate shares. The signed values do not have the same ordering in both divisions.}',r'The \rev{modal-share deviation} of Eq. \eqref{eq:energy-change} is listed in Table \ref{tab:energy}. \rev{It is evaluated from the full-frame accuracy models using their first five modes. Guyan gives \(0.0455\) in division I and \(1.3859\) in division II; the corresponding Craig--Bampton values are \(0.0039\) and \(0.0423\). Craig--Bampton gives the smaller deviation in both divisions and more closely preserves the selected coordinate shares.}','更新四个模型的指标和对应判断，删除原有符号排序讨论。')
change(r'\caption{Modal redistribution ratio of the four condensed models.}',r'\caption{\rev{Modal-share deviation} of the four condensed models.}','表5标题统一为变化幅度。')
change(r'I  & \rev{-0.0414} & \rev{0.0039}',r'I  & \rev{0.0455} & \rev{0.0039}','表5划分I改为逐项绝对值之和。')
change(r'II & \rev{0.8914} & \rev{0.0365}',r'II & \rev{1.3859} & \rev{0.0423}','表5划分II改为逐项绝对值之和。')
change(r'Figure \ref{fig:modal-shares} resolves this change into the physical-coordinate distribution and the two actuator contributions. In division II, Guyan increases the first-storey share by 113.87\% and decreases the third-storey share by 24.73\%, whose signed relative contributions sum to \(\Delta E=0.8914\). Craig--Bampton gives changes of 3.94\% and \(-0.29\%\) at the same coordinates. The figure thus locates the redistribution that the scalar index combines, while also showing why its sign cannot be read as a change in total modal energy.',r'Figure \ref{fig:modal-shares} shows the physical-coordinate distribution and the relative deviation at each actuated coordinate. In division II, the Guyan first- and third-storey shares deviate from the full-order values by 113.87\% and 24.73\%, giving \(\Delta E=1.3859\). The corresponding Craig--Bampton deviations are 3.94\% and 0.29\%, with \(\Delta E=0.0423\). The coordinate-wise comparison locates the changes combined by the scalar index.','右图按幅度解读；保持数值来源和坐标定位，删除对正负的反复强调。')
change(r'Low-order modal-share distribution and actuator contributions. (a,c) Shares on the fifteen physical coordinates. (b,d) Signed relative changes at the two actuated coordinates, whose sum gives the ratio in Table \ref{tab:energy}. The top and bottom rows correspond to divisions I and II, respectively.',r'Low-order modal-share distribution and coordinate-wise deviations. (a,c) Shares on the fifteen physical coordinates. (b,d) Magnitudes of the relative deviations at the two actuated coordinates, whose sum is reported in Table \ref{tab:energy}. The top and bottom rows correspond to divisions I and II, respectively.','图15图注与全部非负柱值一致。')
change('The modal-share ratio is available once a reduced model has been formed and can be used alongside frequency and response errors to inspect the effect of a retained-coordinate choice. Its separate coordinate contributions are particularly useful when a horizontal coordinate is condensed. Stability is assessed from the delayed closed-loop model, including its regulator and integration algorithm; the present ratio provides no threshold for the admissible channel delays.','The modal-share deviation is available once a reduced model has been formed and can be used alongside frequency and response errors to inspect the effect of a retained-coordinate choice. Its coordinate-wise values are particularly useful when a horizontal coordinate is condensed. Delay stability is assessed from the closed-loop model with its regulator and integration algorithm.','统一指标名称，精简重复限制，保留一次明确的稳定性分析口径。')
change(r'The full-frame modal redistribution ratios are 0.0039 and 0.0365 for Craig--Bampton and \(-0.0414\) and 0.8914 for Guyan in divisions I and II, respectively. Their coordinate-wise contributions describe the change in low-order modal distribution; closed-loop poles remain the criterion for delay stability.',r'The full-frame modal-share deviations are 0.0039 and 0.0423 for Craig--Bampton and 0.0455 and 1.3859 for Guyan in divisions I and II, respectively. These values show that Craig--Bampton more closely preserves the low-order modal distribution at the actuated coordinates.','结论同步新指标四值，围绕模态分布保真性表述。')
assert re.findall(r'\\vspace\{-[^}]+\}',after)==re.findall(r'\\vspace\{-[^}]+\}',before)
for stale in ['0.8914','0.0365','-0.0414','signed relative','retain their signs','The signed values','modal redistribution ratio']:
 assert stale not in after,stale
(NEW/'main.tex').write_text(after,encoding='utf-8')
(EV/'manuscript_changes.json').write_text(json.dumps(ops,ensure_ascii=False,indent=2),encoding='utf-8')
(EV/'main_changes.diff').write_text(''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='previous_main.tex',tofile='main.tex')),encoding='utf-8')
if Path(__file__).resolve()!=(EV/'code/revise_metric.py').resolve():shutil.copy2(__file__,EV/'code/revise_metric.py')
print(json.dumps({'operations':len(ops),'models':models,'max_numeric_difference':max(x['error'] for x in checks)},ensure_ascii=False,indent=2))
