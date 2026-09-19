from __future__ import annotations

import base64
import hashlib
import html
from pathlib import Path


PACKAGE = Path(__file__).resolve().parent
CODE_ROOT = PACKAGE.parent
OUTPUT = CODE_ROOT / "小论文Fig6至Fig9_MATLAB现场全计算链汇报.html"


CASES = [
    {
        "id": "Fig.6",
        "folder": "Fig06_第一类划分_ElCentro全链计算",
        "entry": "RUN_FIG06_FULLCHAIN.m",
        "condition": "第一类子结构划分；El Centro 1940 NS × 0.40",
        "model": "lvxvjie_guyan_2.slx",
        "master": "[1, 6, 11, 4, 9, 14]",
        "slave": "[2, 3, 5, 7, 8, 10, 12, 13, 15]",
        "dof": "15 / 6 / 9",
        "state": "30 / 12 / 18",
        "windows": "10–11 s；21.5–22.5 s",
        "peak1": "Original 3.28484；Craig–Bampton 3.28973；Guyan 3.35257 mm",
        "peak3": "Original 12.35115；Craig–Bampton 12.34754；Guyan 12.32156 mm",
        "png": "fig06_eq_div1_fullchain.png",
        "sim": "34.861592 s",
        "note": "第一类划分下，Craig–Bampton 几乎贴住 Original；Guyan 也很接近。",
    },
    {
        "id": "Fig.7",
        "folder": "Fig07_第二类划分_ElCentro全链计算",
        "entry": "RUN_FIG07_FULLCHAIN.m",
        "condition": "第二类子结构划分；El Centro 1940 NS × 0.40",
        "model": "lvxvjie_guyan.slx",
        "master": "[1, 11, 4, 9, 14]",
        "slave": "[6, 2, 3, 5, 7, 8, 10, 12, 13, 15]",
        "dof": "15 / 5 / 8",
        "state": "30 / 10 / 16",
        "windows": "10–11 s；21.5–22.5 s",
        "peak1": "Original 3.28484；Craig–Bampton 3.28633；Guyan 3.02304 mm",
        "peak3": "Original 12.35115；Craig–Bampton 12.35089；Guyan 13.42530 mm",
        "png": "fig07_eq_div2_fullchain.png",
        "sim": "5.292458 s",
        "note": "第二类划分把界面自由度减少到 5 个，Guyan 偏差明显增大，这正是图中要展示的现象。",
    },
    {
        "id": "Fig.8",
        "folder": "Fig08_第一类划分_Chirp全链计算",
        "entry": "RUN_FIG08_FULLCHAIN.m",
        "condition": "第一类子结构划分；0.1–10 Hz、40 s 线性 Chirp",
        "model": "lvxvjie_guyan_2.slx",
        "master": "[1, 6, 11, 4, 9, 14]",
        "slave": "[2, 3, 5, 7, 8, 10, 12, 13, 15]",
        "dof": "15 / 6 / 9",
        "state": "30 / 12 / 18",
        "windows": "13–14 s；38–38.3 s",
        "peak1": "Original 8.83496；Craig–Bampton 8.83589；Guyan 8.92547 mm",
        "peak3": "Original 34.56167；Craig–Bampton 34.56446；Guyan 34.70386 mm",
        "png": "fig08_chirp_div1_fullchain.png",
        "sim": "4.442442 s",
        "note": "Chirp 像把频率从低到高连续扫过结构；约 10–13 s 的放大对应扫频靠近结构共振区。",
    },
    {
        "id": "Fig.9",
        "folder": "Fig09_第二类划分_Chirp全链计算",
        "entry": "RUN_FIG09_FULLCHAIN.m",
        "condition": "第二类子结构划分；同一次 0.1–10 Hz、40 s 线性 Chirp",
        "model": "lvxvjie_guyan.slx",
        "master": "[1, 11, 4, 9, 14]",
        "slave": "[6, 2, 3, 5, 7, 8, 10, 12, 13, 15]",
        "dof": "15 / 5 / 8",
        "state": "30 / 10 / 16",
        "windows": "13–14 s；38–38.3 s",
        "peak1": "Original 8.83496；Craig–Bampton 8.83771；Guyan 8.91072 mm",
        "peak3": "Original 34.56167；Craig–Bampton 34.57053；Guyan 38.48789 mm",
        "png": "fig09_chirp_div2_fullchain.png",
        "sim": "4.073415 s",
        "note": "当前小论文使用物理一致的 Chirp 局部窗；它有意修正硕士论文图3-15曾混入 El Centro 局部窗的问题。",
    },
]


def data_uri(path: Path) -> str:
    mime = "image/png"
    payload = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{payload}"


def file_link(path: Path, label: str) -> str:
    return f'<a class="file-link" href="{html.escape(path.resolve().as_uri())}">{html.escape(label)}</a>'


def render_case(case: dict[str, str]) -> str:
    folder = PACKAGE / case["folder"]
    entry = folder / case["entry"]
    image_path = folder / "输出" / "本轮计算图" / case["png"]
    image = data_uri(image_path)
    path_text = str(entry.resolve())
    return f"""
    <article class="case-card" id="{case['id'].replace('.', '').lower()}">
      <div class="case-head">
        <div><span class="eyebrow">逐图现场卡</span><h3>{case['id']}</h3></div>
        <span class="pass">FULL_CHAIN=PASS</span>
      </div>
      <p class="lead">{html.escape(case['condition'])}</p>
      <div class="open-box">
        <strong>现场只打开这个文件</strong>
        <code>{html.escape(path_text)}</code>
        <div class="button-row">{file_link(entry, '在 MATLAB 关联程序中打开')}<button data-copy="{html.escape(path_text)}">复制路径</button></div>
      </div>
      <figure><img src="{image}" alt="{case['id']} 本轮全计算链输出"><figcaption>{case['id']} 本轮实际计算后直接绘制的 600 dpi 图。</figcaption></figure>
      <div class="mini-grid">
        <div><b>运行模型副本来源</b><span>{case['model']}</span></div>
        <div><b>位移自由度 Original / Guyan / CB</b><span>{case['dof']}</span></div>
        <div><b>状态维数 Original / Guyan / CB</b><span>{case['state']}</span></div>
        <div><b>局部放大窗口</b><span>{case['windows']}</span></div>
        <div><b>一层绝对峰值</b><span>{case['peak1']}</span></div>
        <div><b>三层绝对峰值</b><span>{case['peak3']}</span></div>
      </div>
      <details>
        <summary>本图的主、从自由度和讲解重点</summary>
        <p><b>主自由度：</b><code>{case['master']}</code></p>
        <p><b>从自由度：</b><code>{case['slave']}</code></p>
        <p>{case['note']}</p>
        <p><b>正式包本次 Simulink 仿真耗时：</b>{case['sim']}。首次打开 MATLAB 或首次加载模型会更慢，现场应以最终 PASS 为准，不以单次耗时为准。</p>
      </details>
    </article>
    """


case_sections = "\n".join(render_case(case) for case in CASES)


entries = [PACKAGE / case["folder"] / case["entry"] for case in CASES]
all_runner = PACKAGE / "RUN_ALL_FOUR.m"
guide = PACKAGE / "README_导师现场操作总指南.md"
qa = PACKAGE / "验证记录" / "导师现场演示包验收总报告.txt"


page = rf"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>小论文 Fig.6–Fig.9 MATLAB 现场全计算链汇报</title>
<style>
:root {{ --ink:#172033; --muted:#5e6878; --navy:#17365d; --blue:#2f6fa9; --red:#e85d6a; --green:#0f7b55; --pale:#f3f6fa; --line:#d9e1ea; --paper:#fff; --warn:#fff3d5; }}
* {{ box-sizing:border-box; }}
html {{ scroll-behavior:smooth; max-width:100%; overflow-x:hidden; }}
body {{ margin:0; max-width:100%; overflow-x:hidden; color:var(--ink); background:#e9eef4; font-family:"Microsoft YaHei","Noto Sans CJK SC",Arial,sans-serif; line-height:1.72; }}
a {{ color:var(--blue); }}
code, pre {{ font-family:Consolas,"Cascadia Mono",monospace; }}
code {{ overflow-wrap:anywhere; word-break:break-word; }}
nav {{ position:sticky; top:0; z-index:5; background:rgba(23,54,93,.96); color:#fff; padding:.7rem max(1rem,calc((100vw - 1180px)/2)); box-shadow:0 4px 18px #0002; }}
nav a {{ color:#fff; text-decoration:none; margin-right:1.1rem; font-size:.92rem; white-space:nowrap; }}
.nav-scroll {{ overflow-x:auto; white-space:nowrap; }}
main {{ width:100%; min-width:0; max-width:1180px; margin:0 auto; background:var(--paper); box-shadow:0 0 30px #23334a22; }}
header {{ padding:4rem 6% 3rem; color:#fff; background:linear-gradient(135deg,#102b4d 0%,#245d8d 70%,#3284a8 100%); }}
header h1 {{ margin:.3rem 0 1rem; font-size:clamp(2rem,5vw,4.2rem); line-height:1.08; letter-spacing:-.04em; max-width:980px; }}
header p {{ max-width:900px; font-size:1.12rem; opacity:.95; }}
.eyebrow {{ text-transform:uppercase; letter-spacing:.12em; font-weight:800; font-size:.75rem; color:#7bc7f2; }}
.status-grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:.8rem; margin-top:2rem; }}
.status-grid div {{ min-width:0; border:1px solid #ffffff55; background:#ffffff16; border-radius:12px; padding:1rem; }}
.status-grid b {{ display:block; font-size:1.35rem; }}
section {{ padding:3.3rem 6%; border-bottom:1px solid var(--line); }}
h2 {{ font-size:clamp(1.65rem,3vw,2.5rem); line-height:1.2; margin:0 0 1rem; color:var(--navy); }}
h3 {{ font-size:1.55rem; margin:.15rem 0; color:var(--navy); }}
h4 {{ margin:1.6rem 0 .5rem; color:var(--navy); }}
.lead {{ font-size:1.08rem; color:#354258; }}
.callout {{ border-left:5px solid var(--blue); background:#edf6fc; padding:1rem 1.2rem; margin:1.2rem 0; border-radius:0 10px 10px 0; }}
.warning {{ border-left-color:#d58b00; background:var(--warn); }}
.proof {{ border-left-color:var(--green); background:#eaf8f2; }}
.quick-table, table {{ width:100%; border-collapse:collapse; margin:1rem 0; }}
th {{ background:var(--navy); color:#fff; text-align:left; }}
th, td {{ padding:.75rem .8rem; border:1px solid var(--line); vertical-align:top; }}
tbody tr:nth-child(even) {{ background:#f7f9fb; }}
.steps {{ counter-reset:step; display:grid; gap:.85rem; margin:1.2rem 0; }}
.step {{ position:relative; min-width:0; padding:1rem 1rem 1rem 4rem; border:1px solid var(--line); border-radius:12px; background:#fff; }}
.step:before {{ counter-increment:step; content:counter(step); position:absolute; left:1rem; top:1rem; width:2rem; height:2rem; display:grid; place-items:center; background:var(--navy); color:#fff; border-radius:50%; font-weight:800; }}
.flow {{ display:flex; align-items:stretch; gap:.45rem; overflow-x:auto; padding:1rem 0 1.2rem; }}
.flow div {{ min-width:130px; flex:1; border:1px solid #bdd0e4; background:#f2f7fb; border-radius:10px; padding:.8rem; text-align:center; font-weight:700; }}
.flow span {{ align-self:center; color:var(--blue); font-size:1.5rem; }}
.code-map {{ display:grid; grid-template-columns:70px 135px 1fr; gap:0; border:1px solid var(--line); border-radius:12px; overflow:hidden; }}
.code-map > div {{ padding:.8rem; border-bottom:1px solid var(--line); }}
.code-map > div:nth-last-child(-n+3) {{ border-bottom:0; }}
.code-map .num {{ font-weight:800; color:#fff; background:var(--navy); text-align:center; }}
.code-map .lines {{ font-family:Consolas,monospace; color:var(--blue); background:#f3f6fa; }}
pre {{ background:#111b2d; color:#e7edf6; padding:1rem; border-radius:10px; overflow:auto; line-height:1.5; }}
.case-card {{ min-width:0; border:1px solid var(--line); border-radius:18px; padding:1.4rem; margin:1.5rem 0 2.3rem; box-shadow:0 8px 26px #213a5b12; }}
.case-head {{ display:flex; justify-content:space-between; align-items:center; gap:1rem; }}
.pass {{ background:#dff5eb; color:var(--green); border:1px solid #a6d8c5; padding:.35rem .65rem; border-radius:999px; font-weight:800; font-size:.84rem; }}
.open-box {{ background:#f6f8fb; border:1px solid var(--line); border-radius:12px; padding:1rem; margin:1rem 0; }}
.open-box code {{ display:block; overflow-wrap:anywhere; margin:.45rem 0; color:#253c5d; }}
.button-row {{ display:flex; flex-wrap:wrap; gap:.55rem; }}
.file-link, button {{ border:0; border-radius:7px; background:var(--navy); color:#fff; padding:.48rem .72rem; text-decoration:none; cursor:pointer; font:inherit; font-size:.88rem; }}
button {{ background:var(--blue); }}
figure {{ margin:1.2rem 0; }}
figure img {{ display:block; width:100%; border:1px solid var(--line); background:#fff; }}
figcaption {{ color:var(--muted); font-size:.86rem; margin-top:.35rem; }}
.mini-grid {{ display:grid; grid-template-columns:repeat(2,1fr); gap:.75rem; }}
.mini-grid div {{ min-width:0; border-left:4px solid var(--blue); background:#f7f9fc; padding:.75rem; }}
.mini-grid b, .mini-grid span {{ display:block; }}
.mini-grid span {{ color:#47546a; margin-top:.2rem; }}
details {{ border:1px solid var(--line); border-radius:10px; padding:.7rem 1rem; margin-top:1rem; }}
summary {{ cursor:pointer; font-weight:800; color:var(--navy); }}
.formula {{ font-family:"Cambria Math",serif; text-align:center; font-size:1.1rem; padding:.7rem; background:#f6f8fb; overflow-x:auto; }}
.boundary-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:1rem; }}
.boundary-grid > div {{ padding:1rem; border-radius:12px; border:1px solid var(--line); }}
footer {{ padding:2rem 6%; background:#102b4d; color:#dce8f4; }}
.small {{ font-size:.88rem; color:var(--muted); }}
@media (max-width:760px) {{
  .status-grid,.mini-grid,.boundary-grid {{ grid-template-columns:1fr; }}
  .status-grid {{ width:100%; }}
  section,header {{ padding-left:5%; padding-right:5%; }}
  .code-map {{ grid-template-columns:52px 95px 1fr; font-size:.87rem; }}
  .flow {{ flex-direction:column; }} .flow span {{ transform:rotate(90deg); }}
  table {{ display:block; overflow-x:auto; white-space:nowrap; }}
  .case-head {{ align-items:flex-start; }}
}}
@media print {{
  @page {{ size:A4; margin:13mm; }}
  body {{ background:#fff; font-size:10pt; }} nav,button {{ display:none !important; }}
  main {{ max-width:none; box-shadow:none; }} header {{ padding:18mm 12mm; -webkit-print-color-adjust:exact; print-color-adjust:exact; }}
  section {{ padding:12mm 8mm; }} .case-card {{ break-inside:avoid; box-shadow:none; }}
  figure {{ break-inside:avoid; }} a {{ color:inherit; text-decoration:none; }} footer {{ display:none; }}
}}
</style>
</head>
<body>
<nav><div class="nav-scroll"><a href="#answer">结论</a><a href="#operate">现场操作</a><a href="#chain">计算链</a><a href="#code">九段代码</a><a href="#figures">逐图说明</a><a href="#boundary">论文差异</a><a href="#qa">验收证据</a></div></nav>
<main>
<header>
  <span class="eyebrow">Doctor Bego · 导师现场汇报用</span>
  <h1>Fig.6–Fig.9<br>MATLAB 全计算链复现</h1>
  <p>四张案例分析图均从结构参数开始重新计算，不读取旧响应来出图。每张图都有一个可单独复制、可独立运行的 MATLAB 入口；Fig.10 按您的要求不在本报告范围内。</p>
  <div class="status-grid"><div><b>4 / 4 PASS</b><span>正式包重跑</span></div><div><b>4 / 4 PASS</b><span>项目外独立副本</span></div><div><b>40961 × 3 × 3</b><span>每图响应数组</span></div><div><b>0</b><span>保存后与当前CSV差值</span></div></div>
</header>

<section id="answer">
  <h2>先给导师一句话结论</h2>
  <p class="lead">“我现在可以针对小论文 Fig.6、Fig.7、Fig.8、Fig.9，分别在 MATLAB 中从 15 自由度结构参数开始，重建 Original、Guyan 和 Craig–Bampton 三套模型，重新生成地震或扫频激励，调用 Simulink 以固定步长积分 40 秒，再用本轮新算的响应直接绘图；四个入口都已在项目外独立运行通过。”</p>
  <div class="callout proof"><b>这次不是读取结果文件的绘图级复现。</b>参考 CSV 到第 9 节才被读取，只用于末端逐点验收；前 8 节已经完成计算和绘图。</div>
  <div class="callout warning"><b>现场建议：</b>先演示 Fig.6 全链，预留 1–2 分钟给 MATLAB 首次加载 Simulink；其余图通常更快。导师若只需要看四图全部通过，再运行根目录的 <code>RUN_ALL_FOUR.m</code>。</div>
  <p>{file_link(guide, '打开总操作指南')}　{file_link(all_runner, '打开四图批量入口')}　{file_link(qa, '打开验收总报告')}</p>
</section>

<section id="operate">
  <h2>现场到底怎么操作 MATLAB</h2>
  <div class="steps">
    <div class="step"><b>启动 MATLAB。</b>本机已用 MATLAB R2025b 验证；需要 Simulink 和 Control System Toolbox。</div>
    <div class="step"><b>在左侧“当前文件夹”的地址栏粘贴演示包路径：</b><code>{html.escape(str(PACKAGE))}</code>，然后回车。</div>
    <div class="step"><b>进入要讲的单图文件夹，双击唯一的 <code>RUN_FIGxx_FULLCHAIN.m</code>。</b>不要直接双击原始 <code>.slx</code> 后按 Run，因为工作区变量和输入适配尚未建立。</div>
    <div class="step"><b>完整演示：</b>点击编辑器上方绿色“运行”或按 <code>F5</code>。<b>逐段讲：</b>先把光标放在最上方“现场全计算链演示入口”的初始化节（第1–62行），按一次 <code>Ctrl+Enter</code>；再从第1节顺序运行到第9节。不能直接从第63行开始。</div>
    <div class="step"><b>看命令窗口。</b>程序会打印 <code>[1/9]</code> 到 <code>[9/9]</code>；最后必须同时出现 <code>STATUS=PASS</code> 和 <code>FULL_CHAIN=PASS</code>。</div>
    <div class="step"><b>在工作区展示证据。</b>依次查看 <code>M_full</code>、<code>M_guyan</code>、<code>M_cb</code>、<code>T_guyan</code>、<code>T_cb</code>、<code>excitation_input</code> 和 <code>response_mm</code>。</div>
    <div class="step"><b>展示运行副本与输出。</b>命令窗口输入 <code>open_system(runtime_model_file)</code> 可打开本轮实际运行的模型副本；图和数据保存在当前单图文件夹的 <code>输出</code> 内。</div>
  </div>
  <h3>现场可直接输入的核对命令</h3>
  <pre>size(M_full)       % 应为 15×15
size(M_guyan)      % 第一类6×6；第二类5×5
size(M_cb)         % 第一类9×9；第二类8×8
size(T_guyan)      % 15×6 或 15×5
size(T_cb)         % 15×9 或 15×8
size(response_mm)  % 必须为 40961×3×3
max_abs_difference_to_current
open_system(runtime_model_file)</pre>
  <table class="quick-table"><thead><tr><th>小论文图</th><th>MATLAB 中打开的主文件</th><th>工况</th></tr></thead><tbody>
    {''.join(f'<tr><td>{c["id"]}</td><td>{file_link(PACKAGE/c["folder"]/c["entry"], c["entry"])}</td><td>{html.escape(c["condition"])}</td></tr>' for c in CASES)}
  </tbody></table>
</section>

<section id="chain">
  <h2>这条计算链到底在做什么</h2>
  <p class="lead">可以把三种模型想成三张“结构地图”：Original 把全部 15 个位移自由度都留下；Guyan 只保留界面上的关键自由度，用静力关系猜回其余位移；Craig–Bampton 除界面自由度外，还保留 3 个固定界面振动模态，因此通常能更好地跟住动力响应。</p>
  <div class="flow"><div>几何与材料<br><code>PDmonicanshu.m</code></div><span>→</span><div>15×15<br>M、C、K</div><span>→</span><div>Guyan / CB<br>缩聚</div><span>→</span><div>三套<br>状态空间</div><span>→</span><div>El Centro<br>或 Chirp</div><span>→</span><div>Simulink<br>ode4</div><span>→</span><div>40961×3×3<br>楼层响应</div><span>→</span><div>本轮数据<br>直接绘图</div><span>→</span><div>最后才读<br>参考CSV验收</div></div>
  <div class="boundary-grid">
    <div><h3>Original</h3><p>直接求解全部 15 个二阶自由度。状态向量由位移和速度组成，所以状态维数为 30。</p></div>
    <div><h3>Guyan</h3><p>假设从自由度惯性作用可忽略，用刚度静力平衡将它们表达成主自由度。第一类保留6个，第二类保留5个二阶自由度。</p></div>
    <div><h3>Craig–Bampton</h3><p>在静力约束模态之外再保留3个从自由度固定界面模态。第一类为6+3=9个，第二类为5+3=8个二阶自由度。</p></div>
    <div><h3>同一把尺子比较</h3><p>三套模型最后都恢复成一、二、三层的物理位移，单位为 mm，所以图上比较的是同一物理量。</p></div>
  </div>
  <h3>二阶动力方程如何进入 Simulink</h3>
  <div class="formula">M q̈ + C q̇ + K q = f　→　ẋ = A x + B f，　A = [0　I; −M⁻¹K　−M⁻¹C]</div>
  <p>每个二阶自由度有“位移”和“速度”两个状态，所以 15 个自由度变成 30 个状态；6 个自由度变成 12 个状态。程序把三套状态空间分别放入 <code>G_1</code>、<code>G_2</code>、<code>G_3</code>，由同一个激励并行驱动。</p>
</section>

<section id="code">
  <h2>入口初始化 + 九段代码：逐段应该怎么讲</h2>
  <p>四个入口的主体代码完全相同，文件名用于自动选择图号、划分、激励和输出名。以下行号以 Fig.6 的 <code>RUN_FIG06_FULLCHAIN.m</code> 为例，另外三份对应位置一致。若采用 <code>Ctrl+Enter</code> 逐节演示，必须先运行第1–62行的入口初始化节。</p>
  <div class="code-map">
    <div class="num">入口</div><div class="lines">1–62</div><div><b>初始化现场。</b>清理旧状态，根据当前脚本文件名识别 Fig.6/7/8/9，建立本图输入、参考和输出路径，把 Simulink 缓存限制在本图 <code>输出</code> 文件夹，并开始记录现场日志。</div>
    <div class="num">1</div><div class="lines">63–86</div><div><b>建立原结构。</b>运行本图文件夹自带的 <code>PDmonicanshu.m</code>。其中几何和材料参数位于16–24行，质量矩阵装配位于26–40行，刚度矩阵位于43–104行，Rayleigh阻尼位于106–122行。输出 <code>M_full</code>、<code>C_full</code>、<code>K_full</code>，均为15×15。</div>
    <div class="num">2</div><div class="lines">88–102</div><div><b>复制并适配 Simulink。</b>冻结原 <code>.slx</code> 不修改；程序复制到 <code>输出/运行模型副本</code>，加入本轮 <code>From Workspace</code> 输入、改成本地地震路径，并固定求解器。第二类模型只在副本中补齐三层 Guyan、Craig–Bampton 输出线。</div>
    <div class="num">3</div><div class="lines">104–125</div><div><b>重新缩聚。</b>按当前图的 <code>master</code>、<code>slave</code> 重排 M/C/K，计算 <code>T_guyan</code>；求固定界面特征向量，按频率排序并保留前3阶，形成 <code>T_cb</code>。</div>
    <div class="num">4</div><div class="lines">127–134</div><div><b>建立三套状态空间并恢复楼层位移。</b>Original、Guyan、Craig–Bampton 分别形成 <code>G_1</code>、<code>G_2</code>、<code>G_3</code>；恢复矩阵把降阶坐标投影回一、二、三层水平位移。</div>
    <div class="num">5</div><div class="lines">136–158</div><div><b>现场产生激励。</b>Fig.6/7 从 <code>EQ.mat</code> 取 El Centro 并乘0.40；Fig.8/9 用公式逐点生成0.1–10 Hz线性Chirp。这里产生的是加速度输入，不是响应。</div>
    <div class="num">6</div><div class="lines">160–168</div><div><b>真正进行数值积分。</b>调用派生模型，求解器为四阶定步长 Runge–Kutta <code>ode4</code>，步长 <code>dt=1/1024 s</code>，终止时间40 s。</div>
    <div class="num">7</div><div class="lines">169–189</div><div><b>整理本轮响应。</b><code>simout3</code>、<code>simout</code>、<code>simout1</code> 分别是一、二、三层；每个输出的3列是 Original、Guyan、Craig–Bampton。最终形成 <code>response_mm(时间,楼层,方法)</code>，即40961×3×3。</div>
    <div class="num">8</div><div class="lines">191–203</div><div><b>直接使用新算数据出图。</b>没有读取参考CSV。每张图画一层和三层；每层含0–40 s全时程和两个局部窗，保存矢量PDF与600 dpi PNG。</div>
    <div class="num">9</div><div class="lines">205–228</div><div><b>末端验收。</b>直到图已经画完，程序才读取 <code>参考结果_仅用于末端验收</code>，比较40961×10个数字；小于1e−12 mm才打印两个PASS。</div>
  </div>
  <h3>真正执行计算的局部函数</h3>
  <table><thead><tr><th>函数/行号</th><th>作用</th><th>现场可以指出的变量</th></tr></thead><tbody>
    <tr><td><code>prepare_model_copy</code><br>290–368</td><td>复制和适配模型副本，设定 <code>ode4</code>、40 s、固定步长；修复第二类模型三层输出。</td><td><code>runtime_model_file</code></td></tr>
    <tr><td><code>build_reduction_models</code><br>370–428</td><td>主从自由度重排、Guyan缩聚、固定界面模态排序、Craig–Bampton变换和楼层恢复矩阵。</td><td><code>T_guyan</code>、<code>T_cb</code>、<code>M_guyan</code>、<code>M_cb</code></td></tr>
    <tr><td><code>second_order_ss</code><br>430–438</td><td>把 M/C/K 二阶方程改写成一阶状态空间。</td><td><code>G_1</code>、<code>G_2</code>、<code>G_3</code></td></tr>
    <tr><td><code>run_one_simulation</code><br>448–461</td><td>把本轮激励送入 Simulink 并调用 <code>sim()</code>。</td><td><code>simulation_output</code></td></tr>
    <tr><td><code>make_response_arrays</code><br>463–480</td><td>将三个楼层输出统一为40961×3×3。</td><td><code>time_s</code>、<code>response_mm</code></td></tr>
    <tr><td><code>plot_journal_figure</code><br>506–603</td><td>按小论文布局绘制六个坐标轴并输出PDF/PNG。</td><td><code>fig</code></td></tr>
  </tbody></table>
  <h3>核心缩聚公式：现场要诚实说明</h3>
  <pre>% 梁禹现存路线中的 Guyan 写法
T  = [eye(nm); -Kss\Ksm];
Mg = Mmm - Mms*(Kss\Ksm);
Cg = Cmm - Cms*(Kss\Ksm);
Kg = Kmm - Kms*(Kss\Ksm);

% Craig–Bampton：约束模态 + 前3个固定界面模态
Tcb = [eye(nm), zeros(nm,3); -Kss\Ksm, phi(:,1:3)];
Mcb = Tcb' * M * Tcb;
Ccb = Tcb' * C * Tcb;
Kcb = Tcb' * K * Tcb;</pre>
</section>

<section id="figures">
  <h2>每一张图：打开什么、算什么、应该看到什么</h2>
  {case_sections}
</section>

<section id="boundary">
  <h2>与硕士论文和小论文理论表述的差别</h2>
  <div class="boundary-grid">
    <div><h3>可以确认</h3><ul><li>四图都能从参数和模型重新算出，不依赖旧响应作为计算输入。</li><li>每图有40961个时间点，0–40 s，步长1/1024 s。</li><li>保存后的四份新算CSV与当前参考CSV逐字节相同。</li><li>Craig–Bampton保留3个固定界面模态。</li></ul></div>
    <div><h3>不能混说</h3><ul><li>这不是找回梁禹当年保存的 MATLAB 工作区。</li><li>原始第二类 <code>.slx</code> 不能原样直接运行；只在派生副本中补线。</li><li>历史 Guyan 代码不是小论文理论部分的完整双侧合同投影。</li><li>Fig.9当前小论文版本不会与硕士论文图3-15的历史混合窗口完全相同。</li></ul></div>
  </div>
  <h3>差别一：Guyan 代码与小论文理论公式</h3>
  <p>小论文理论部分写的是 <code>T' * M * T</code>、<code>T' * C * T</code>、<code>T' * K * T</code> 的双侧合同投影；现存计算代码使用上面所列的单侧缩聚式。为了追踪“梁禹现存代码怎样得到图”，本演示保留历史写法。因此可以说“结果链稳定复现”，不能说“代码已经证明理论公式完全一致”。</p>
  <h3>差别二：Fig.9 与硕士论文图3-15</h3>
  <p>硕士论文图3-15的0–40 s主图来自第二类划分 Chirp 三层响应，但两个局部窗历史上混入了第二类 El Centro 三层响应的10–11 s和21.5–22.5 s。当前小论文 Fig.9 采用物理一致版本：主图和两个局部窗全部来自同一次 Chirp 计算，窗口为13–14 s和38–38.3 s。这是修正数据源混用，不是复现失败。</p>
  <h3>为什么不能直接运行原始 SLX</h3>
  <p>原模型要求工作区中先存在 <code>G_1</code>、<code>G_2</code>、<code>G_3</code>、<code>T</code>、<code>T_cb</code> 等变量，并保存了作者电脑的旧绝对路径；第二类模型的三层 Guyan 和 Craig–Bampton 输出还缺连接。主脚本先计算变量，再复制原模型，在副本中接入本轮输入和补齐输出；冻结输入不改。</p>
</section>

<section id="qa">
  <h2>我如何证明这套现场演示稳定</h2>
  <table><thead><tr><th>验收项</th><th>实际结果</th></tr></thead><tbody>
    <tr><td>正式包一次运行四图</td><td><code>ALL_FOUR_FULL_CHAINS=PASS</code>，4/4通过。</td></tr>
    <tr><td>项目外独立副本</td><td>复制到 <code>C:\Windows\Temp\liangyu_live_demo_board27_20260901_01</code>，从 <code>tempdir</code> 调用，4/4通过。</td></tr>
    <tr><td>输入与代码冻结清单</td><td>36/36个条目哈希通过；每个单图文件夹9个固定条目。</td></tr>
    <tr><td>数值</td><td>MATLAB内存最大差4.9737991503207013e−14 mm；CSV格式化后最大差0，且四对CSV的SHA-256分别相同。</td></tr>
    <tr><td>输出尺寸</td><td>四图均为40961×3×3，无NaN/Inf，时间步长误差0。</td></tr>
    <tr><td>图形</td><td>4个单页纯矢量PDF；4个600 dpi PNG；无Type 3字体。</td></tr>
  </tbody></table>
  <div class="callout"><b>黄色警告怎样判断：</b><code>Chirp Signal2</code>、<code>Step1</code> 或第二类模型 <code>Demux2</code> 的未连接警告来自被旁路的原模型遗留块。警告后继续到 <code>FULL_CHAIN=PASS</code> 属于正常；红色错误或缺少最终PASS才是失败。</div>
  <p class="small">本HTML所有图像都以 Base64 内嵌，无外部字体、样式表、脚本或图片依赖。复制这一个HTML文件即可离线查看和打印。</p>
</section>

<footer>
  <b>交付范围：</b>小论文案例分析 Fig.6–Fig.9；Fig.10 不在本报告范围。<br>
  <span>生成于 2026-09-01。计算证据等级：现存代码与必要模型适配路线的计算级复现。</span>
</footer>
</main>
<script>
document.querySelectorAll('button[data-copy]').forEach(function(btn) {{
  btn.addEventListener('click', async function() {{
    try {{ await navigator.clipboard.writeText(btn.dataset.copy); btn.textContent='已复制'; }}
    catch (e) {{ btn.textContent='请手动复制上方路径'; }}
  }});
}});
</script>
</body>
</html>
"""


OUTPUT.write_text(page, encoding="utf-8")
digest = hashlib.sha256(OUTPUT.read_bytes()).hexdigest().upper()
print(f"STATUS=PASS")
print(f"OUTPUT={OUTPUT}")
print(f"BYTES={OUTPUT.stat().st_size}")
print(f"SHA256={digest}")
print(f"EMBEDDED_PNG={len(CASES)}")
