from __future__ import annotations

import base64
import html
import re
import struct
from pathlib import Path


REPORT_NAME = "小论文案例分析Fig6至Fig10_复现汇报.html"


def png_data_uri(path: Path) -> tuple[str, int, int, int]:
    raw = path.read_bytes()
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"不是有效PNG：{path}")
    width, height = struct.unpack(">II", raw[16:24])
    uri = "data:image/png;base64," + base64.b64encode(raw).decode("ascii")
    return uri, width, height, len(raw)


def assert_pass_report(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("STATUS=PASS"):
        raise RuntimeError(f"验收报告未通过：{path}")


def make_figure_card(
    figure_id: str,
    title: str,
    meaning: str,
    folder: str,
    output_text: str,
    input_text: str,
    windows: str,
    check_text: str,
    evidence: str,
    image_uri: str,
    width: int,
    height: int,
) -> str:
    return f"""
    <article class="figure-card" id="{figure_id.lower()}">
      <div class="figure-head">
        <div><span class="eyebrow">{html.escape(figure_id)}</span><h3>{html.escape(title)}</h3></div>
        <span class="status pass">已生成并验证</span>
      </div>
      <p>{html.escape(meaning)}</p>
      <figure>
        <img src="{image_uri}" width="{width}" height="{height}"
             alt="{html.escape(title)}" loading="eager">
        <figcaption>{html.escape(figure_id)}最终MATLAB输出预览；页面内嵌图片，不依赖旁置文件。</figcaption>
      </figure>
      <div class="fact-grid">
        <div><strong>独立文件夹</strong><code>{html.escape(folder)}</code></div>
        <div><strong>运行入口</strong><code>RUN_THIS_FIGURE.m</code></div>
        <div><strong>验证入口</strong><code>VERIFY_THIS_FIGURE.m</code></div>
        <div><strong>最终输出</strong><code>{html.escape(output_text)}</code></div>
        <div><strong>输入</strong><span>{html.escape(input_text)}</span></div>
        <div><strong>局部窗口/坐标合同</strong><span>{html.escape(windows)}</span></div>
        <div><strong>实际验证</strong><span>{html.escape(check_text)}</span></div>
        <div><strong>证据等级</strong><span>{html.escape(evidence)}</span></div>
      </div>
    </article>
    """


def build_report(root: Path) -> str:
    figures = [
        {
            "id": "Fig.6",
            "title": "第一类子结构划分的 El Centro 地震响应",
            "meaning": "上排为一层位移，下排为三层位移；每排包含完整40 s响应和两个局部放大窗口。",
            "folder": "Fig06_第一类划分_ElCentro响应",
            "output": "fig06_eq_div1.pdf / fig06_eq_div1.png",
            "input": "第一类划分_ElCentro地震响应.csv，40961×10，0–40 s，步长1/1024 s",
            "windows": "10–11 s；21.5–22.5 s",
            "check": "6个坐标轴、18条实际XData/YData；最大误差0",
            "evidence": "既有响应计算快照的绘图级重排",
            "png": root / "Fig06_第一类划分_ElCentro响应" / "输出" / "PNG" / "fig06_eq_div1.png",
            "report": root / "Fig06_第一类划分_ElCentro响应" / "输出" / "validation_report.txt",
        },
        {
            "id": "Fig.7",
            "title": "第二类子结构划分的 El Centro 地震响应",
            "meaning": "展示第二类划分下的一层和三层响应，使Guyan、Craig–Bampton与原结构的差异可以直接比较。",
            "folder": "Fig07_第二类划分_ElCentro响应",
            "output": "fig07_eq_div2.pdf / fig07_eq_div2.png",
            "input": "第二类划分_ElCentro地震响应.csv，40961×10，0–40 s，步长1/1024 s",
            "windows": "10–11 s；21.5–22.5 s",
            "check": "6个坐标轴、18条实际XData/YData；最大误差0",
            "evidence": "既有响应计算快照的绘图级重排",
            "png": root / "Fig07_第二类划分_ElCentro响应" / "输出" / "PNG" / "fig07_eq_div2.png",
            "report": root / "Fig07_第二类划分_ElCentro响应" / "输出" / "validation_report.txt",
        },
        {
            "id": "Fig.8",
            "title": "第一类子结构划分的 Chirp 扫频响应",
            "meaning": "Chirp激励的频率随时间变化，图中完整响应和局部窗口共同展示三种模型的幅值与相位差。",
            "folder": "Fig08_第一类划分_Chirp响应",
            "output": "fig08_chirp_div1.pdf / fig08_chirp_div1.png",
            "input": "第一类划分_Chirp响应.csv，40961×10，0–40 s，步长1/1024 s",
            "windows": "13–14 s；38–38.3 s",
            "check": "6个坐标轴、18条实际XData/YData；最大误差0",
            "evidence": "既有响应计算快照的绘图级重排",
            "png": root / "Fig08_第一类划分_Chirp响应" / "输出" / "PNG" / "fig08_chirp_div1.png",
            "report": root / "Fig08_第一类划分_Chirp响应" / "输出" / "validation_report.txt",
        },
        {
            "id": "Fig.9",
            "title": "第二类子结构划分的 Chirp 扫频响应",
            "meaning": "第二类划分中Guyan与原结构的差异更明显；局部窗口用于看清完整时程中重叠的线。",
            "folder": "Fig09_第二类划分_Chirp响应",
            "output": "fig09_chirp_div2.pdf / fig09_chirp_div2.png",
            "input": "第二类划分_Chirp响应.csv，40961×10，0–40 s，步长1/1024 s",
            "windows": "13–14 s；38–38.3 s",
            "check": "6个坐标轴、18条实际XData/YData；最大误差0",
            "evidence": "既有响应计算快照的绘图级重排",
            "png": root / "Fig09_第二类划分_Chirp响应" / "输出" / "PNG" / "fig09_chirp_div2.png",
            "report": root / "Fig09_第二类划分_Chirp响应" / "输出" / "validation_report.txt",
        },
        {
            "id": "Fig.10",
            "title": "两类子结构划分的双作动器时滞稳定域",
            "meaning": "横轴和纵轴分别是两个作动器的时滞。边界以内外对应稳定性变化；两面板分别对应第一类和第二类划分。",
            "folder": "Fig10_双时滞稳定域",
            "output": "fig10_stability_domain.pdf / fig10_stability_domain.png",
            "input": "6份论文矢量边界CSV；点数72/69/67/69/56/53，合计386点",
            "windows": "两轴从0开始；真实首个采样点为0.9765625 ms；按point_order连接",
            "check": "6条实际plot曲线、386点；最大逐点误差0",
            "evidence": "梁禹论文边界的绘图级逐点复现；计算级复现未通过",
            "png": root / "Fig10_双时滞稳定域" / "输出" / "PNG" / "fig10_stability_domain.png",
            "report": root / "Fig10_双时滞稳定域" / "输出" / "validation_report.txt",
        },
    ]

    cards: list[str] = []
    embedded_bytes = 0
    for item in figures:
        assert_pass_report(item["report"])
        uri, width, height, byte_count = png_data_uri(item["png"])
        embedded_bytes += byte_count
        cards.append(
            make_figure_card(
                item["id"], item["title"], item["meaning"], item["folder"],
                item["output"], item["input"], item["windows"], item["check"], item["evidence"],
                uri, width, height,
            )
        )

    standalone_report = root / "验证记录" / "独立复制运行" / "独立复制运行总报告.txt"
    assert_pass_report(standalone_report)

    figure_cards = "\n".join(cards)
    html_text = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="小论文案例分析Fig.6至Fig.10自包含MATLAB复现汇报">
  <link rel="icon" href="data:,">
  <title>小论文案例分析 Fig.6–Fig.10 复现汇报</title>
  <style>
    :root {{
      color-scheme: light;
      --ink:#18212b; --muted:#5b6673; --line:#d8dee6; --paper:#ffffff;
      --wash:#f3f6f9; --blue:#2f6f9f; --red:#d95565; --green:#16724a;
      --amber:#9a5b00; --shadow:0 10px 28px rgba(24,33,43,.08);
    }}
    * {{ box-sizing:border-box; }}
    html {{ scroll-behavior:smooth; }}
    body {{ margin:0; color:var(--ink); background:#e9eef3; font-family:"Microsoft YaHei","Segoe UI",sans-serif; line-height:1.72; }}
    a {{ color:#175d91; text-underline-offset:3px; }}
    .page {{ max-width:1180px; margin:0 auto; background:var(--paper); min-height:100vh; box-shadow:var(--shadow); }}
    header {{ padding:56px 64px 42px; background:linear-gradient(135deg,#16394f 0%,#285f78 58%,#4c8291 100%); color:white; }}
    header .kicker {{ letter-spacing:.12em; font-size:.82rem; opacity:.82; font-weight:700; }}
    h1 {{ margin:.25rem 0 .75rem; font-size:clamp(2rem,5vw,3.55rem); line-height:1.16; }}
    header p {{ max-width:850px; font-size:1.08rem; margin:0; color:#eaf3f7; }}
    .headline-status {{ display:flex; flex-wrap:wrap; gap:10px; margin-top:24px; }}
    .pill {{ border:1px solid rgba(255,255,255,.35); background:rgba(255,255,255,.12); padding:6px 12px; border-radius:999px; font-size:.88rem; }}
    nav {{ position:sticky; top:0; z-index:10; padding:12px 24px; background:rgba(255,255,255,.96); backdrop-filter:blur(8px); border-bottom:1px solid var(--line); display:flex; gap:8px; flex-wrap:wrap; justify-content:center; }}
    nav a {{ color:#2d4658; text-decoration:none; font-weight:700; font-size:.9rem; padding:5px 9px; border-radius:6px; }}
    nav a:hover {{ background:#eaf1f5; }}
    main {{ padding:42px 64px 64px; }}
    section {{ scroll-margin-top:78px; margin-bottom:54px; }}
    h2 {{ font-size:1.75rem; margin:0 0 18px; padding-bottom:9px; border-bottom:3px solid #3d788f; }}
    h3 {{ font-size:1.28rem; margin:.15rem 0; line-height:1.35; }}
    p {{ margin:.6rem 0 1rem; }}
    .lead {{ font-size:1.08rem; }}
    .summary-grid, .status-grid {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:14px; }}
    .metric, .panel {{ border:1px solid var(--line); border-radius:12px; background:var(--paper); box-shadow:0 4px 14px rgba(24,33,43,.05); }}
    .metric {{ padding:20px; }}
    .metric strong {{ display:block; color:#1c5c78; font-size:1.65rem; line-height:1.1; }}
    .metric span {{ color:var(--muted); font-size:.91rem; }}
    .callout {{ border-left:5px solid var(--blue); background:#edf5f8; padding:18px 22px; border-radius:0 10px 10px 0; }}
    .callout.warning {{ border-left-color:var(--amber); background:#fff6e8; }}
    .flow {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:20px; align-items:stretch; }}
    .flow .step {{ position:relative; padding:20px 18px; background:var(--wash); border-radius:12px; border:1px solid var(--line); }}
    .flow .step:not(:last-child)::after {{ content:"→"; position:absolute; right:-17px; top:42%; color:#668; font-size:1.45rem; font-weight:800; }}
    .step b {{ display:block; color:#245f78; margin-bottom:6px; }}
    .figure-card {{ padding:24px; margin:22px 0; border:1px solid var(--line); border-radius:14px; box-shadow:var(--shadow); break-inside:avoid; }}
    .figure-head {{ display:flex; align-items:flex-start; justify-content:space-between; gap:16px; }}
    .eyebrow {{ color:var(--blue); font-weight:800; font-size:.84rem; letter-spacing:.08em; }}
    .status {{ display:inline-block; padding:5px 10px; border-radius:999px; font-size:.82rem; font-weight:800; white-space:nowrap; }}
    .pass {{ color:#0b5d3a; background:#dff4e9; }}
    .limit {{ color:#855000; background:#ffedc7; }}
    figure {{ margin:18px 0; border:1px solid #e1e5ea; background:white; border-radius:10px; padding:12px; overflow:hidden; }}
    figure img {{ display:block; width:100%; height:auto; object-fit:contain; }}
    figcaption {{ color:var(--muted); font-size:.82rem; padding:8px 2px 0; }}
    .fact-grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px 18px; }}
    .fact-grid > div {{ display:flex; flex-direction:column; border-top:1px solid #edf0f3; padding-top:9px; min-width:0; }}
    .fact-grid strong {{ font-size:.83rem; color:#52606c; }}
    code {{ font-family:Consolas,"Cascadia Mono",monospace; overflow-wrap:anywhere; color:#233a4a; background:#edf2f5; border-radius:4px; padding:2px 5px; }}
    .table-wrap {{ overflow-x:auto; border:1px solid var(--line); border-radius:10px; }}
    table {{ width:100%; border-collapse:collapse; min-width:720px; }}
    th,td {{ padding:11px 13px; text-align:left; vertical-align:top; border-bottom:1px solid var(--line); }}
    th {{ background:#edf3f6; color:#294959; }}
    tr:last-child td {{ border-bottom:0; }}
    ol.steps li {{ margin:.55rem 0; padding-left:.35rem; }}
    details {{ border:1px solid var(--line); border-radius:10px; padding:12px 16px; margin:12px 0; }}
    summary {{ cursor:pointer; font-weight:800; color:#285e76; }}
    footer {{ padding:26px 64px 40px; border-top:1px solid var(--line); color:var(--muted); font-size:.88rem; }}
    .small {{ color:var(--muted); font-size:.88rem; }}
    @media (max-width:850px) {{
      header, main, footer {{ padding-left:22px; padding-right:22px; }}
      .summary-grid, .status-grid, .flow, .fact-grid {{ grid-template-columns:minmax(0,1fr); }}
      .flow .step:not(:last-child)::after {{ content:"↓"; right:auto; left:50%; top:auto; bottom:-23px; }}
      .figure-head {{ flex-direction:column; }}
      nav {{ justify-content:flex-start; overflow-x:auto; flex-wrap:nowrap; }}
      nav a {{ white-space:nowrap; }}
    }}
    @media print {{
      @page {{ size:A4; margin:13mm; }}
      body, .page {{ background:white; box-shadow:none; }}
      nav {{ display:none; }}
      header {{ background:white!important; color:black; padding:0 0 18px; border-bottom:2px solid #333; }}
      header p {{ color:#333; }}
      .headline-status .pill {{ border-color:#777; background:white; }}
      main {{ padding:22px 0 0; }} footer {{ padding:14px 0 0; }}
      .figure-card, .metric, .panel {{ box-shadow:none; }}
      .figure-card {{ padding:11px; margin:10px 0; }}
      .figure-head {{ flex-direction:row; gap:8px; }}
      .figure-card > p {{ margin:.2rem 0 .45rem; }}
      figure {{ margin:7px 0; padding:5px; }}
      figcaption {{ padding-top:3px; font-size:.72rem; }}
      .fact-grid {{ grid-template-columns:repeat(2,minmax(0,1fr)); gap:2px 10px; }}
      .fact-grid > div {{ padding-top:3px; }}
      .fact-grid strong, .fact-grid span, .fact-grid code {{ font-size:.72rem; line-height:1.35; }}
      .status {{ font-size:.72rem; padding:3px 7px; }}
      .table-wrap {{ overflow:visible; }}
      table {{ min-width:0; font-size:.76rem; line-height:1.38; }}
      th,td {{ padding:6px 7px; overflow-wrap:anywhere; }}
      section, .figure-card, figure, table {{ break-inside:avoid; }}
      h2, h3 {{ break-after:avoid; }}
    }}
  </style>
</head>
<body>
<div class="page">
  <header>
    <div class="kicker">RHTS CASE-STUDY FIGURE REPRODUCTION</div>
    <h1>小论文案例分析<br>Fig.6–Fig.10 复现汇报</h1>
    <p>这份单文件报告说明五张案例分析结果图如何生成、每张图对应哪段MATLAB代码、已经验证到什么程度，以及哪些结论仍不能升级为计算级复现。</p>
    <div class="headline-status">
      <span class="pill">5个独立MATLAB图包</span><span class="pill">10/10随机位置运行通过</span>
      <span class="pill">5份纯矢量PDF</span><span class="pill">5份600 dpi PNG</span>
    </div>
  </header>
  <nav aria-label="报告目录">
    <a href="#summary">结论</a><a href="#scope">范围</a><a href="#logic">工作逻辑</a>
    <a href="#figures">逐图映射</a><a href="#validation">验证</a><a href="#operate">MATLAB操作</a>
    <a href="#boundary">证据边界</a><a href="#action">下一步</a>
  </nav>
  <main>
    <section id="summary">
      <h2>一、管理者摘要</h2>
      <p class="lead"><strong>五张案例分析结果图已经整理为可单独复制运行的MATLAB图包，并完成真实运行与视觉验收。</strong>每个文件夹都带齐输入CSV、绘图入口、验证入口、输出和操作说明；运行任何一张图不需要原工程路径，也不需要其他图的公共函数。</p>
      <div class="summary-grid">
        <div class="metric"><strong>5/5</strong><span>单图包完成</span></div>
        <div class="metric"><strong>10/10</strong><span>随机位置双轮运行通过</span></div>
        <div class="metric"><strong>0</strong><span>实际绘图坐标最大误差</span></div>
        <div class="metric"><strong>0</strong><span>PDF内嵌位图与Type 3字体</span></div>
      </div>
      <div class="callout warning">
        <strong>最重要的判断：</strong>Fig.6–Fig.9稳定复现了现有响应CSV的绘图结果；Fig.10稳定复现了梁禹论文中提取的386个边界点。前者没有重跑Simulink，后者没有从闭环极点重新计算稳定域，因此当前完成的是绘图级复现。
      </div>
      <p><strong>当前是否需要您操作：</strong>不需要。五张图现在均可直接使用；只有当目标升级为“从物理模型重新求解”时，才需要另立计算级复现任务。</p>
      <p class="small"><strong>实测环境：</strong>MATLAB R2025b（25.2.0.2998904），Windows 64位；本报告不把这一台电脑上的通过结果外推为所有MATLAB版本和操作系统均兼容。</p>
    </section>

    <section id="scope">
      <h2>二、范围与依据</h2>
      <p>本次范围只包含小论文案例分析的数值结果图：Fig.6、Fig.7、Fig.8、Fig.9和Fig.10。案例结构、自由度和子结构划分示意图Fig.1–Fig.5，以及表格和能量指标，不在本次交付范围内。</p>
      <div class="table-wrap"><table>
        <thead><tr><th>证据对象</th><th>本报告怎样使用</th><th>结论身份</th></tr></thead>
        <tbody>
          <tr><td>4份40961×10响应CSV</td><td>绘制两类划分在El Centro与Chirp激励下的一层、三层响应</td><td>既有计算快照</td></tr>
          <tr><td>6份论文矢量边界CSV</td><td>按原始点序绘制两类划分的双时滞稳定边界，共386点</td><td>论文矢量边界提取结果</td></tr>
          <tr><td>10份MATLAB入口/验证代码</td><td>每图独立读取、绘制、导出并逐点复核</td><td>本次新建可执行交付</td></tr>
          <tr><td>MATLAB与图件验收记录</td><td>证明真实运行、路径独立、数值一致和图件可用</td><td>本次实际验证</td></tr>
        </tbody>
      </table></div>
    </section>

    <section id="logic">
      <h2>三、梁禹结果到小论文图片的工作逻辑</h2>
      <div class="flow">
        <div class="step"><b>1. 取得结果数据</b><span>响应图读取现有时程CSV；稳定域图读取论文矢量边界点。</span></div>
        <div class="step"><b>2. 锁定绘图合同</b><span>固定列身份、点序、时间窗、单位换算、颜色、线型和面板顺序。</span></div>
        <div class="step"><b>3. MATLAB绘图</b><span>每张图只用自己文件夹中的输入，生成矢量PDF和600 dpi PNG。</span></div>
        <div class="step"><b>4. 独立验证</b><span>重新读取输入，比较实际XData/YData，并在随机位置复制运行。</span></div>
      </div>
      <p>三种方法始终保持同一身份：Original为深灰虚线和圆标记，Craig–Bampton为红色实线和方标记，Guyan为蓝色点划线和三角标记。响应CSV中列顺序是Original、Guyan、Craig–Bampton，代码在绘图时重新排列图例，但不会交换数据列。</p>
    </section>

    <section id="figures">
      <h2>四、每张图由哪个代码生成</h2>
      {figure_cards}
    </section>

    <section id="validation">
      <h2>五、怎样证明它们可以稳定复现</h2>
      <div class="status-grid">
        <div class="metric"><strong>10/10</strong><span>输入文件SHA-256匹配</span></div>
        <div class="metric"><strong>72条</strong><span>Fig.6–Fig.9实际绘图线合计</span></div>
        <div class="metric"><strong>386点</strong><span>Fig.10逐点核对</span></div>
        <div class="metric"><strong>5/5</strong><span>PDF渲染目视通过</span></div>
      </div>
      <ol>
        <li><strong>输入门：</strong>4份响应CSV与6份边界CSV的SHA-256均与封存值一致。</li>
        <li><strong>数据门：</strong>Fig.6–Fig.9每图检查6个坐标轴、18条实际图线；Fig.10检查6条图线和386点，最大误差均为0。</li>
        <li><strong>路径门：</strong>五个文件夹各复制并改名到随机临时位置运行两轮，共10次全部通过；代码未发现绝对路径、父目录、<code>cd</code>、<code>pwd</code>或<code>addpath</code>依赖。</li>
        <li><strong>图件门：</strong>5份PDF均为单页纯矢量图，内嵌位图数0、Type 3字体数0；5份PNG均为600 dpi。</li>
        <li><strong>视觉门：</strong>PDF重新渲染并与历史图并排检查，未发现标签裁切、面板重叠、图例缺失或曲线身份互换。</li>
      </ol>
      <p class="small">两轮PNG比较忽略MATLAB写入的生成时间元数据，直接比较解码像素。Fig.7–Fig.10逐像素一致；Fig.6仅1个像素单通道差1级，占全图1.3166×10<sup>−7</sup>，低于1×10<sup>−6</sup>验收上限，数值数据完全一致。</p>
      <details>
        <summary>展开查看10份输入文件的SHA-256</summary>
        <ul>
          <li><code>E7149DD6777B2127527393CE1D7B126B040576F0A535618BE33E882738ACFC40</code> — 第一类划分_ElCentro地震响应.csv</li>
          <li><code>2899DFD2C03B22AAEE701C7E4B3B70E40D49668531BB6734FA6B52E8246B5E5D</code> — 第二类划分_ElCentro地震响应.csv</li>
          <li><code>2FDC6B5BF3B48118A51DD147ECE32B6711CEFDCD702D88EEC64CFC4E6A13DF49</code> — 第一类划分_Chirp响应.csv</li>
          <li><code>88919C2AFA4FC431EDB08772A1DCB091B6D8DC1445253C0A4D30334223040457</code> — 第二类划分_Chirp响应.csv</li>
          <li><code>0FC5115AED9C1EC3F709A89CB5F47751181B42AEC2804001980693EE47E09B45</code> — 图4-4_Original_论文矢量边界.csv</li>
          <li><code>96B7ADBBB508524C70F8655E3B9B92757DACEF8CE74653CE12B47704B3985942</code> — 图4-4_CB_论文矢量边界.csv</li>
          <li><code>1E0CDC14A84BD65DB2A561741671ACB16DA2EFE00CB8E880B4A4F03FDD07FB10</code> — 图4-4_Guyan_论文矢量边界.csv</li>
          <li><code>54C3A337998F4AA4C663D51F324385A3F6315053E8279AB57ED706AF26AD0570</code> — 图4-5_Original_论文矢量边界.csv</li>
          <li><code>2EF896D5C601B147AE22C00AE2E1FD6762A92B042BB19116271550F48C8C7DA5</code> — 图4-5_CB_论文矢量边界.csv</li>
          <li><code>BB68AF002B787510A03EFE946A03ECBFC6966060CA0D4FDD9B23A1AD9B0A3694</code> — 图4-5_Guyan_论文矢量边界.csv</li>
        </ul>
      </details>
      <details>
        <summary>展开查看五张输出图的结构规格</summary>
        <ul>
          <li>Fig.6、Fig.7：3531×2151像素，600 dpi；PDF为单页纯矢量。</li>
          <li>Fig.8、Fig.9：3624×2117像素，600 dpi；PDF为单页纯矢量。</li>
          <li>Fig.10：3510×1474像素，600 dpi；PDF为单页纯矢量。</li>
        </ul>
      </details>
    </section>

    <section id="operate">
      <h2>六、在MATLAB中一步一步生成任意一张图</h2>
      <ol class="steps">
        <li>在Windows资源管理器中进入需要绘制的 <code>FigXX_...</code> 文件夹。移动图包时必须复制整个文件夹。</li>
        <li>双击 <code>RUN_THIS_FIGURE.m</code>，让MATLAB打开它。</li>
        <li>点击编辑器上方绿色“运行”按钮。代码会从脚本自身位置寻找 <code>输入数据</code>，不要求当前工作目录正确。</li>
        <li>在本图文件夹的 <code>输出/PDF</code> 和 <code>输出/PNG</code> 查看结果。</li>
        <li>双击并运行 <code>VERIFY_THIS_FIGURE.m</code>；命令窗口应显示PASS，且 <code>输出/validation_report.txt</code> 第一行应为 <code>STATUS=PASS</code>。</li>
      </ol>
      <div class="callout"><strong>一次生成全部五张图：</strong>在 <code>code</code> 根目录运行 <code>RUN_ALL_FIGURES.m</code>，随后运行 <code>VERIFY_ALL_FIGURES.m</code>。</div>
    </section>

    <section id="boundary">
      <h2>七、证据边界、风险与正确表述</h2>
      <div class="table-wrap"><table>
        <thead><tr><th>对象</th><th>当前可以确认</th><th>仍未闭合</th><th>正确表述</th></tr></thead>
        <tbody>
          <tr><td>Fig.6–Fig.9</td><td>CSV到MATLAB图线的列映射、时间窗和实际坐标稳定可重复</td><td>本包没有从模型重新计算这些40961点响应</td><td>既有响应快照的绘图级重排</td></tr>
          <tr><td>Fig.10</td><td>论文边界386点、点序和毫秒换算稳定可重复；坐标轴从0开始</td><td>没有从闭环特征方程或谱半径网格重新求出边界</td><td>论文矢量边界的绘图级逐点复现</td></tr>
          <tr><td>新MATLAB PDF</td><td>数据、方法身份和版式合同通过</td><td>与历史Python/论文PDF不是二进制相同文件</td><td>MATLAB重新排版的可复现矢量图</td></tr>
        </tbody>
      </table></div>
      <p>Fig.10看起来“从0开始”指坐标轴下限为0，不表示必须伪造一个原点数据。采样步2按公式 <code>(step−1)×1000/1024</code> 换算为0.9765625 ms；代码保留这个真实首点。</p>
      <p>响应图的完整40 s曲线不显示密集标记，局部窗口才显示圆形、方形和三角形；Fig.10每条边界只均匀显示最多9个标记，但全部386个点都由折线连接。标记稀疏不代表中间数据被删除。</p>
    </section>

    <section id="action">
      <h2>八、当前状态与下一步</h2>
      <p><span class="status pass">当前任务完成</span> 五个图包、根批量入口、逐图说明、数值验证、随机位置双轮运行和图件视觉验收均已完成。您现在不需要补充路径或安装额外公共函数。</p>
      <p><strong>后续工作尚未授权：</strong>表格整理、重新运行Simulink，以及Fig.10计算级稳定域闭合仍属于后续独立任务。开展这些工作前需要另行确定范围和验收标准。</p>
    </section>

    <details>
      <summary>查看主要证据文件名称</summary>
      <ul>
        <li><code>README_从这里开始.md</code>：MATLAB总操作说明。</li>
        <li><code>来源与证据总表.csv</code>：逐图输入、论文对照和证据等级。</li>
        <li><code>验证记录/最终验收报告.md</code>：运行、数值和图件验收详情。</li>
        <li><code>验证记录/独立复制运行/独立复制运行清单.csv</code>：10次随机位置运行记录。</li>
        <li><code>验证记录/文件清单.csv</code>：交付文件及SHA-256。</li>
      </ul>
    </details>
  </main>
  <footer>
    <strong>报告日期：</strong>2026-09-01　
    <strong>范围：</strong>小论文案例分析Fig.6–Fig.10　
    <strong>内嵌图片：</strong>5张，共{embedded_bytes:,}字节。<br>
    本HTML将核心正文、样式和图片全部内嵌，可单独复制并离线打开。
  </footer>
</div>
</body>
</html>
"""
    return html_text


def validate_generated_html(text: str) -> None:
    required = [
        "管理者摘要", "范围与依据", "工作逻辑", "每张图由哪个代码生成",
        "怎样证明它们可以稳定复现", "MATLAB中一步一步", "证据边界",
        "Fig06_第一类划分_ElCentro响应", "Fig10_双时滞稳定域",
        "计算级复现未通过", "10/10", "STATUS=PASS",
    ]
    missing = [item for item in required if item not in text]
    if missing:
        raise RuntimeError(f"HTML缺少关键内容：{missing}")
    if text.count("data:image/png;base64,") != 5:
        raise RuntimeError("HTML内嵌PNG数量不是5")
    if re.search(r"(?:src|href)=[\"']https?://", text, flags=re.I):
        raise RuntimeError("HTML包含外部HTTP资源")
    if "<meta charset=\"utf-8\">" not in text.lower():
        raise RuntimeError("HTML缺少UTF-8字符集声明")


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    output = root / REPORT_NAME
    report = build_report(root)
    validate_generated_html(report)
    output.write_text(report, encoding="utf-8", newline="\n")
    print(f"HTML_REPORT={output}")
    print(f"HTML_BYTES={output.stat().st_size}")
    print("EMBEDDED_PNG_COUNT=5")
    print("EXTERNAL_HTTP_RESOURCES=0")


if __name__ == "__main__":
    main()
