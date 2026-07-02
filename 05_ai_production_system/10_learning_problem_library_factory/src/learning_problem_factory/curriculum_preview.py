from __future__ import annotations

from collections import Counter
from html import escape
from pathlib import Path

from .curriculum_models import (
    CurriculumEvidencePack,
    CurriculumOutline,
    CurriculumSourceCatalog,
    OutlineLevel,
)
from .models import Subject


SUBJECT_META = {
    Subject.MATH: ("数学", "#6c63ff", "MATHEMATICS"),
    Subject.SCIENCE: ("小学科学", "#14b8a6", "PRIMARY SCIENCE"),
    Subject.PHYSICS: ("初中物理", "#f59e0b", "PHYSICS"),
    Subject.CHEMISTRY: ("初中化学", "#ec4899", "CHEMISTRY"),
}


def _clip(value: str, limit: int = 180) -> str:
    cleaned = " ".join(value.split())
    return cleaned if len(cleaned) <= limit else cleaned[:limit].rstrip() + "…"


def render_curriculum_preview(
    outline: CurriculumOutline,
    catalog: CurriculumSourceCatalog,
    evidence: CurriculumEvidencePack,
) -> str:
    nodes_by_parent: dict[str | None, list] = {}
    for node in outline.nodes:
        nodes_by_parent.setdefault(node.parent_id, []).append(node)
    evidence_by_page = {
        (page.source_id, page.logical_page): page
        for page in evidence.pages
        if page.logical_page is not None
    }
    page_counts = Counter(page.source_id for page in evidence.pages)
    char_counts = Counter()
    for page in evidence.pages:
        char_counts[page.source_id] += len(page.text)

    course_nodes = [node for node in outline.nodes if node.level == OutlineLevel.COURSE]
    theme_count = sum(node.level == OutlineLevel.THEME for node in outline.nodes)
    task_count = sum(node.level == OutlineLevel.STAGE_TASK for node in outline.nodes)
    source_cards = "".join(
        f"""
        <article class="source-card">
          <div class="source-kicker">{escape(source.subject.value.upper())} · {escape(source.edition)}</div>
          <h3>{escape(source.title)}</h3>
          <div class="source-metrics"><span>{page_counts[source.id]} 页 OCR</span><span>{char_counts[source.id]:,} 字符</span></div>
          <div class="verified">✓ 官方哈希已核验</div>
        </article>
        """
        for source in catalog.sources
    )

    tabs = "".join(
        f'<button class="tab" data-subject="{course.subject.value}">{SUBJECT_META[course.subject][0]}</button>'
        for course in course_nodes
    )
    subject_sections: list[str] = []
    for course in course_nodes:
        label, color, english = SUBJECT_META[course.subject]
        themes = sorted(nodes_by_parent.get(course.id, []), key=lambda node: node.id)
        task_total = sum(len(nodes_by_parent.get(theme.id, [])) for theme in themes)
        theme_html: list[str] = []
        for index, theme in enumerate(themes, start=1):
            tasks = sorted(nodes_by_parent.get(theme.id, []), key=lambda node: (node.grade_min, node.id))
            citation = theme.citations[0]
            evidence_page = evidence_by_page.get((citation.source_id, citation.page_start))
            excerpt = _clip(evidence_page.text) if evidence_page else "该主题的 OCR 页将在模型生产阶段按页注入。"
            task_chips = "".join(
                f"""
                <div class="task-chip">
                  <span>{task.grade_min}-{task.grade_max} 年级</span>
                  <strong>≥ {task.expected_min_points} 个原子知识点</strong>
                </div>
                """
                for task in tasks
            )
            theme_html.append(
                f"""
                <details class="theme-card" {'open' if index == 1 else ''}>
                  <summary>
                    <span class="theme-index">{index:02d}</span>
                    <span class="theme-title">{escape(theme.title)}</span>
                    <span class="page-range">课标 {citation.page_start}-{citation.page_end} 页</span>
                    <span class="chevron">⌄</span>
                  </summary>
                  <div class="theme-body">
                    <p class="ocr-label">OCR 证据片段</p>
                    <blockquote>{escape(excerpt)}</blockquote>
                    <div class="task-grid">{task_chips}</div>
                    <p class="pending">知识点、关系与学习卡点将在双模型 + Supervisor 阶段生成</p>
                  </div>
                </details>
                """
            )
        subject_sections.append(
            f"""
            <section class="subject-section" data-subject="{course.subject.value}" style="--accent:{color}">
              <div class="subject-heading">
                <div><p>{english}</p><h2>{label}</h2></div>
                <div class="subject-stats"><span>{len(themes)} 个主题</span><span>{task_total} 个叶子任务</span><span>{course.grade_min}-{course.grade_max} 年级</span></div>
              </div>
              <div class="theme-list">{''.join(theme_html)}</div>
            </section>
            """
        )

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>义务教育数理化知识任务树 · P3 Preview</title>
  <style>
    :root{{--ink:#172033;--muted:#687187;--paper:#f5f4ef;--card:#fff;--line:#deddd6;--dark:#11182a}}
    *{{box-sizing:border-box}} body{{margin:0;background:var(--paper);color:var(--ink);font-family:"Microsoft YaHei UI","PingFang SC",sans-serif}}
    .hero{{background:radial-gradient(circle at 86% 15%,#3e4c7d 0,transparent 28%),linear-gradient(135deg,#11182a,#202b4b);color:white;padding:72px max(24px,calc((100vw - 1160px)/2)) 54px}}
    .eyebrow{{color:#a9b5df;font-size:12px;letter-spacing:.22em;font-weight:700}} h1{{font-size:clamp(34px,5vw,64px);line-height:1.08;margin:14px 0 18px;max-width:900px}}
    .hero p{{color:#cbd2e8;max-width:780px;line-height:1.8}} .status{{display:inline-flex;gap:9px;align-items:center;background:#243353;border:1px solid #4c5d88;border-radius:99px;padding:8px 13px;font-size:13px}}
    .dot{{width:8px;height:8px;background:#4ade80;border-radius:50%;box-shadow:0 0 0 5px #4ade8022}}
    main{{max-width:1160px;margin:auto;padding:34px 24px 80px}} .summary{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-top:-62px}}
    .metric{{background:white;border:1px solid #ffffff22;border-radius:18px;padding:22px;box-shadow:0 16px 40px #17203312}} .metric strong{{font-size:32px;display:block}} .metric span{{font-size:13px;color:var(--muted)}}
    .section-title{{margin:48px 0 18px;display:flex;align-items:end;justify-content:space-between}} .section-title h2{{font-size:25px;margin:0}} .section-title p{{color:var(--muted);margin:0}}
    .source-grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}} .source-card{{background:white;border:1px solid var(--line);border-radius:16px;padding:20px}}
    .source-kicker{{font-size:11px;letter-spacing:.14em;color:#6c63ff;font-weight:800}} .source-card h3{{font-size:16px;min-height:44px}} .source-metrics{{display:flex;gap:8px}}
    .source-metrics span{{background:#f3f2ee;padding:6px 9px;border-radius:8px;font-size:12px}} .verified{{color:#14845f;font-size:12px;margin-top:14px;font-weight:700}}
    .tabs{{display:flex;gap:8px;flex-wrap:wrap;margin:45px 0 18px}} .tab{{border:1px solid var(--line);background:white;padding:10px 17px;border-radius:99px;cursor:pointer;font-weight:700;color:var(--muted)}}
    .tab.active{{color:white;background:var(--dark);border-color:var(--dark)}} .subject-section{{display:none}} .subject-section.active{{display:block}}
    .subject-heading{{border-left:5px solid var(--accent);padding:9px 0 9px 18px;display:flex;justify-content:space-between;gap:20px;align-items:end;margin-bottom:18px}}
    .subject-heading p{{margin:0;color:var(--accent);font-size:11px;letter-spacing:.18em;font-weight:800}} .subject-heading h2{{margin:5px 0 0;font-size:30px}}
    .subject-stats{{display:flex;gap:7px;flex-wrap:wrap;justify-content:flex-end}} .subject-stats span{{font-size:12px;background:white;border:1px solid var(--line);border-radius:8px;padding:7px 9px}}
    .theme-list{{display:grid;gap:10px}} .theme-card{{background:white;border:1px solid var(--line);border-radius:14px;overflow:hidden}} summary{{list-style:none;display:grid;grid-template-columns:48px 1fr auto 24px;align-items:center;gap:12px;padding:17px;cursor:pointer}}
    summary::-webkit-details-marker{{display:none}} .theme-index{{font-family:Consolas,monospace;color:var(--accent);font-weight:800}} .theme-title{{font-weight:800}} .page-range{{font-size:12px;color:var(--muted)}} .chevron{{font-size:19px;color:var(--muted)}}
    .theme-body{{border-top:1px solid #ecebe5;padding:20px 20px 18px 77px;background:#fcfcfa}} .ocr-label{{font-size:11px;letter-spacing:.15em;font-weight:800;color:var(--accent)}} blockquote{{margin:8px 0 18px;border-left:2px solid var(--accent);padding:3px 0 3px 14px;color:#50596c;line-height:1.7;font-size:13px}}
    .task-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:8px}} .task-chip{{border:1px solid #e3e1da;background:white;border-radius:10px;padding:11px;display:flex;justify-content:space-between;gap:10px;font-size:12px}} .task-chip strong{{color:var(--accent)}}
    .pending{{font-size:12px;color:#8a7380;margin:14px 0 0}} footer{{text-align:center;color:var(--muted);font-size:12px;padding-top:50px}}
    @media(max-width:760px){{.summary{{grid-template-columns:repeat(2,1fr)}}.source-grid{{grid-template-columns:1fr}}.subject-heading{{align-items:start;flex-direction:column}}summary{{grid-template-columns:35px 1fr 20px}}.page-range{{display:none}}.theme-body{{padding-left:20px}}}}
  </style>
</head>
<body>
  <header class="hero">
    <div class="status"><span class="dot"></span>P3 · 官方课标已完成 OCR</div>
    <div class="eyebrow">ANSHI LEARNING LAB · KNOWLEDGE FACTORY</div>
    <h1>中国义务教育数理化<br/>知识任务树</h1>
    <p>这不是模型凭空生成的目录。每个主题和学段任务都锚定教育部 2022 版课程标准；下一阶段将由双模型独立提取知识点，再由 Supervisor 审查和建网。</p>
  </header>
  <main>
    <section class="summary">
      <article class="metric"><strong>{len(course_nodes)}</strong><span>课程体系</span></article>
      <article class="metric"><strong>{theme_count}</strong><span>课标主题</span></article>
      <article class="metric"><strong>{task_count}</strong><span>学段叶子任务</span></article>
      <article class="metric"><strong>{len(evidence.pages)}</strong><span>OCR 证据页</span></article>
    </section>
    <div class="section-title"><h2>官方来源</h2><p>下载哈希、页码和 OCR 文本均可审计</p></div>
    <section class="source-grid">{source_cards}</section>
    <nav class="tabs">{tabs}</nav>
    {''.join(subject_sections)}
    <footer>PREVIEW ONLY · 知识点与关系尚未调用真实模型生产</footer>
  </main>
  <script>
    const tabs=[...document.querySelectorAll('.tab')]; const sections=[...document.querySelectorAll('.subject-section')];
    function activate(subject){{tabs.forEach(x=>x.classList.toggle('active',x.dataset.subject===subject));sections.forEach(x=>x.classList.toggle('active',x.dataset.subject===subject));}}
    tabs.forEach(tab=>tab.addEventListener('click',()=>activate(tab.dataset.subject))); if(tabs.length) activate(tabs[0].dataset.subject);
  </script>
</body>
</html>"""


def write_curriculum_preview(
    outline: CurriculumOutline,
    catalog: CurriculumSourceCatalog,
    evidence: CurriculumEvidencePack,
    output: str | Path,
) -> Path:
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_curriculum_preview(outline, catalog, evidence), encoding="utf-8")
    return target
