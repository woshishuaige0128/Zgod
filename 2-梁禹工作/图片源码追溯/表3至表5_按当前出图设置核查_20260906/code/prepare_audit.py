from pathlib import Path
import csv, hashlib, json, shutil

ROOT = Path(r'D:/JZ_PhD/10_论文_Papers/Li/RHTS/liangyustability-master')
PAPER = ROOT.parent / '260817'
OUT = Path(__file__).resolve().parents[1]
TEMP = ROOT / 'tmp/table345_audit_20260906/temp'
FULL = PAPER / 'code/导师现场MATLAB全链演示_Fig06至Fig09'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    for p in [OUT/'evidence', OUT/'results', TEMP]:
        p.mkdir(parents=True, exist_ok=True)
    if (OUT/'evidence/source_manifest.json').exists():
        raise RuntimeError('Source manifest already exists; refuse to replace the audit baseline.')
    sources = list((PAPER/'elsevier').glob('main.*'))
    sources += list((PAPER/'elsevier/submit_figure').glob('*'))
    sources += list((PAPER/'figure/results_v2/源码').glob('*.py'))
    sources += list((PAPER/'figure/results_v2/输入数据').glob('*'))
    for case in sorted(FULL.glob('Fig*')):
        sources += list(case.glob('RUN*.m'))
        sources += [p for p in (case/'输入模型与参数').rglob('*') if p.is_file()]
        sources += list((case/'输出/本轮计算数据').glob('*.mat'))
        sources += list((case/'输出/本轮计算数据').glob('*响应.csv'))
    manifest = [{'path':str(p), 'sha256':sha(p), 'bytes':p.stat().st_size} for p in sorted(set(sources)) if p.is_file()]
    (OUT/'evidence/source_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    shutil.copy2(PAPER/'elsevier/main.tex',OUT/'evidence/main_source_readonly.tex')
    for name in ['current.md','WORKFLOW.md']:
        shutil.copy2(ROOT/name,OUT/'evidence'/('before_'+name))
    cases=[]
    for case in sorted(FULL.glob('Fig*')):
        entry=next(case.glob('RUN_FIG*_FULLCHAIN.m'))
        dest=TEMP/case.name
        dest.mkdir()
        shutil.copytree(case/'输入模型与参数',dest/'输入模型与参数')
        original=entry.read_text(encoding='utf-8-sig')
        prefix=original[:original.index('%% 8. 直接使用本轮')]
        funcs=original[original.index('%% 本文件以下为局部函数'):]
        suffix="\n% 本次表格审计仅运行原计算段1--7；不出图、不读取参考响应。\n"
        suffix+="save(fullfile(dataOutputDir,'audit_snapshot.mat'),'M_full','C_full','K_full','M_guyan','C_guyan','K_guyan','M_cb','C_cb','K_cb','T_guyan','T_cb','master_dofs','slave_dofs','time_s','response_mm','computed_matrix','-v7');\n"
        suffix+="fprintf('AUDIT_FRESH_SIMULATION=PASS\\n');\nclear diaryCleanup; clear fileGenCleanup;\n\n"
        (dest/entry.name).write_text(prefix+suffix+funcs,encoding='utf-8')
        cases.append({'figure':case.name[:5], 'source':str(case), 'runtime':str(dest), 'entry':entry.name,
                      'calculation_sections_1_to_7_exact':True,'plots_executed':False,'reference_csv_read':False})
        assert (dest/entry.name).read_text(encoding='utf-8').startswith(prefix)
    (OUT/'evidence/runtime_derivation.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2),encoding='utf-8')
    paths=[str(Path(c['runtime'])/c['entry']).replace('\\','/').replace("'","''") for c in cases]
    runner='\n'.join("run('"+p+"');" for p in paths)+"\nfprintf('ALL_FOUR_FRESH_SIMULATIONS=PASS\\n');\n"
    (TEMP/'run_four_audit_cases.m').write_text(runner,encoding='utf-8')
    notice='<!-- 【在工作前，需要首先启动paper-writing skill，这一行不要删除！！】 -->\n'
    workflow=(ROOT/'WORKFLOW.md').read_text(encoding='utf-8-sig')
    if not workflow.startswith(notice.strip()): workflow=notice+workflow
    plan='''\n\n## 板块29：按当前出图设置核查 elsevier/main.tex 表3、表4、表5（2026-09-06）
用户明确指定当前案例出图设置和 `260817/elsevier/main.tex`。本次只核查，不修改论文、出图设置或原计算资产；图10参数研究保持原进度。

1. 冻结 main.tex、当前投稿图、绘图源码/CSV及全链模型；核对表号与图号。验证：SHA-256与来源映射闭合，表3/4/5分别为模态精度、首层NRMSE、模态重分配比。
2. 在 `tmp/table345_audit_20260906/temp` 复制模型，以原全链入口第1--7段重新生成四套时程和矩阵。验证：每套40961个时刻、0--40 s、dt=1/1024；复算时程与实际绘图CSV最大差<=1e-12 mm。预期：计算口径与当前图相同，不以表中数值调参。
3. 使用当前M/K/T和首层时程独立复算44个表格单元。表3频率误差三位、MAC四位；表4按稿件时域积分、全时程峰峰值归一化及明确频带；表5按稿件m=5、恢复到15个物理坐标、质量归一化及两作动坐标求和。验证：MATLAB/Python独立实现指标差<=1e-8，按显示精度逐格裁决。预期结果：准确列出相符、不符及解释条件，不要求论文历史数值必然通过。
4. 交付逐格CSV、独立单文件HTML和证据；检查来源文件哈希不变、HTML离线/桌面/窄屏/打印可读。记录数值正确性与模型文字一致性差异，完成后停止，不推进其他研究。

## TODO List（本次表格核查追加）
- [ ] 板块29：完成当前main.tex三表44个数值的当前出图口径核查、复算和中文报告。
'''
    (ROOT/'WORKFLOW.md').write_text(workflow+plan,encoding='utf-8')
    current=notice+'''# Current - 工作现场快照

## 当前所在 WORKFLOW 板块
板块29：当前出图设置下的 elsevier/main.tex 表3、表4、表5核查。

## 当前正在执行的具体操作
来源冻结完成，准备从参数重新运行四套MATLAB/Simulink计算；原入口计算段1--7保持原样，仅省去出图和读参考结果。

## 上一步操作的结果
main.aux确认表号；四份投稿响应PDF与results_v2/PDF逐字节一致。出图模型维数为15/6/9与15/5/8，正文写15/6/12，已发现口径差异。

## 下一步计划
复算44个单元并独立跨语言核对，整理HTML报告。

## 关键上下文
交付：figure/表3至表5_按当前出图设置核查_20260906；临时运行：tmp/table345_audit_20260906/temp。
旧current.md完整保存在本次交付evidence/before_current.md；图10参数研究未继续。

## 遇到的问题/阻塞点
无执行阻塞；本次目标为核查当前出图口径，不建立正文声称的另一套模型。
'''
    (ROOT/'current.md').write_text(current,encoding='utf-8')
    print(json.dumps({'sources_frozen':len(manifest),'runtime_cases':cases,'output':str(OUT)},ensure_ascii=False))

if __name__=='__main__': main()
