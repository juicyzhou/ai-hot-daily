#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI HOT 每日速递 —— 生成器
拉取 aihot.virxact.com 的精选 AI 动态，按「年/月/日」归档，并聚合出周报、月报。

产出结构：
  daily/<年>/<月>/<YYYY-MM-DD>.html   每日网页版（卡片式，深色/浅色自适应）
  daily/<年>/<月>/<YYYY-MM-DD>.md     每日 Markdown 版
  weekly/<年>/<月>/<周一日期>.html    每周网页版
  weekly/<年>/<月>/<周一日期>.md      每周 Markdown 版
  monthly/<年>/<年>-<月>.html         每月网页版
  monthly/<年>/<年>-<月>.md           每月 Markdown 版
  index.html                          首页：日报/周报/月报 横向 tab + 折叠树 + 预览

本脚本零第三方依赖，仅用 Python 标准库。
"""
import os
import sys
import json
import html
import argparse
import urllib.request
import urllib.parse
import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST_PATH = os.path.join(ROOT, "manifest.json")
API = "https://aihot.virxact.com/api/public/items"


def load_manifest():
    """读取跨运行累计的「已发布期次清单」，用于归档首页（避免每次只索引当前抓取）。"""
    try:
        with open(MANIFEST_PATH, encoding="utf-8") as f:
            m = json.load(f)
        for k in ("daily", "weekly", "monthly"):
            m.setdefault(k, {})
        return m
    except Exception:
        return {"daily": {}, "weekly": {}, "monthly": {}}


def save_manifest(m):
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(m, f, ensure_ascii=False)
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

# 五大版块（slug -> 中文标签 / 主题色）
CATS = [
    ("ai-models", "模型发布", "#6366f1"),
    ("ai-products", "产品发布", "#06b6d4"),
    ("industry", "行业动态", "#f59e0b"),
    ("paper", "论文研究", "#10b981"),
    ("tip", "技巧与观点", "#ec4899"),
]
CAT_MAP = {c[0]: c for c in CATS}
OTHER = ("other", "其他", "#94a3b8")
WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

# ---------------- 报告页 CSS（被 iframe 加载的独立页面） ----------------
REPORT_CSS = """
:root{
  --indigo:#6366f1; --bg:#f6f7fb; --card:#ffffff; --text:#1e2230;
  --muted:#6b7280; --line:#e6e8f0; --shadow:0 4px 18px rgba(30,34,48,.07);
}
@media (prefers-color-scheme: dark){
  :root{ --bg:#0e1016; --card:#171a23; --text:#e8eaf0; --muted:#9aa3b2;
    --line:#262b38; --shadow:0 4px 18px rgba(0,0,0,.4); }
}
*{box-sizing:border-box}
body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
  background:var(--bg);color:var(--text);line-height:1.6;-webkit-font-smoothing:antialiased}
.wrap{max-width:860px;margin:0 auto;padding:16px 20px 48px}
header.top{margin-bottom:14px}
.brand{display:inline-flex;align-items:center;gap:8px;font-weight:700;color:var(--indigo);letter-spacing:.5px;font-size:13px}
.brand .dot{width:8px;height:8px;border-radius:50%;background:var(--indigo);box-shadow:0 0 0 4px rgba(99,102,241,.18)}
h1{font-size:25px;margin:6px 0 3px}
.sub{color:var(--muted);font-size:14px}
a.back{display:inline-block;margin-top:10px;color:var(--indigo);text-decoration:none;font-size:14px;font-weight:600}
a.back:hover{text-decoration:underline}
.sec{margin:18px 0}
.sec h2{display:flex;align-items:center;gap:10px;font-size:18px;margin:0 0 14px}
.sec h2 .bar{width:4px;height:18px;border-radius:3px;display:inline-block}
.sec h2 .cnt{color:var(--muted);font-weight:500;font-size:14px}
.cards{display:flex;flex-direction:column;gap:14px}
.card{display:block;background:var(--card);border:1px solid var(--line);border-radius:12px;
  padding:16px 18px;text-decoration:none;color:inherit;box-shadow:var(--shadow);transition:transform .12s ease,border-color .12s ease}
.card:hover{transform:translateY(-2px);border-color:var(--indigo)}
.card-head{display:flex;align-items:flex-start;gap:10px}
.cat-dot{width:9px;height:9px;border-radius:50%;margin-top:8px;flex:none}
.card h3{margin:0;font-size:16.5px;line-height:1.45}
.card .summary{margin:8px 0 0;color:var(--muted);font-size:14px}
.card .meta{display:flex;justify-content:space-between;gap:12px;margin-top:10px;font-size:12.5px;color:var(--muted)}
.card .source{font-weight:600;color:var(--text)}
.nav{display:flex;justify-content:space-between;gap:12px;margin:30px 0 10px;flex-wrap:wrap}
.nav a{color:var(--indigo);text-decoration:none;font-size:14px;font-weight:600;padding:8px 14px;border:1px solid var(--line);border-radius:10px;background:var(--card)}
.nav a.disabled{opacity:.35;pointer-events:none}
.nav a:hover{border-color:var(--indigo)}
footer{margin-top:40px;padding-top:18px;border-top:1px solid var(--line);color:var(--muted);font-size:12.5px}
footer a{color:var(--indigo);text-decoration:none}
footer a:hover{text-decoration:underline}
""".strip()

# ---------------- 首页 SHELL CSS（tab + 折叠树 + 预览） ----------------
SHELL_CSS = """
:root{
  --indigo:#6366f1; --indigo2:#8b5cf6; --bg:#f5f6fb; --panel:#ffffff;
  --text:#1e2230; --muted:#6b7280; --line:#e7e9f2; --shadow:0 6px 24px rgba(30,34,48,.08);
  --hover:#f3f4ff;
}
@media (prefers-color-scheme: dark){
  :root{ --bg:#0d0f16; --panel:#161922; --text:#e8eaf0; --muted:#9aa3b2;
    --line:#262b38; --shadow:0 6px 24px rgba(0,0,0,.45); --hover:#1d2030; }
}
*{box-sizing:border-box}
html,body{margin:0;height:100%}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
  background:var(--bg);color:var(--text);line-height:1.6;-webkit-font-smoothing:antialiased}
.app{max-width:1180px;margin:0 auto;padding:12px 22px 0;height:100vh;display:flex;flex-direction:column}
/* 顶栏 */
.topbar{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;flex-wrap:wrap;margin-bottom:8px;flex:none}
.brand{display:inline-flex;align-items:center;gap:9px;font-weight:700;color:var(--indigo);letter-spacing:.5px;font-size:13px}
.brand .dot{width:9px;height:9px;border-radius:50%;background:linear-gradient(135deg,var(--indigo),var(--indigo2));box-shadow:0 0 0 4px rgba(99,102,241,.16)}
.topbar h1{font-size:23px;margin:5px 0 2px;letter-spacing:.3px}
.topbar .sub{color:var(--muted);font-size:13.5px}
.topbar .today{font-size:13px;color:var(--muted);text-align:right}
.topbar .today b{color:var(--indigo);font-size:15px}
.gh-link{display:inline-flex;align-items:center;justify-content:center;width:34px;height:34px;border-radius:10px;
  border:1px solid var(--line);color:var(--text);background:var(--panel);transition:all .15s ease;flex:none}
.gh-link:hover{color:#fff;background:var(--indigo);border-color:var(--indigo);transform:translateY(-1px);box-shadow:0 4px 12px rgba(99,102,241,.35)}
.gh-link svg{width:19px;height:19px;fill:currentColor}
.brand .gh-link{width:23px;height:23px;border-radius:7px;margin-left:9px;vertical-align:middle}
.brand .gh-link svg{width:13px;height:13px}
/* tab（横向 3 个，带外框，位于左侧列顶部） */
.tabs{display:flex;gap:6px;background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:5px;box-shadow:var(--shadow);width:100%;margin-bottom:10px;flex:none}
.tab{border:none;background:transparent;color:var(--muted);font-size:15px;font-weight:600;
  padding:9px 22px;border-radius:10px;cursor:pointer;transition:all .15s ease;font-family:inherit}
.tab:hover{color:var(--text)}
.tab.active{background:linear-gradient(135deg,var(--indigo),var(--indigo2));color:#fff;box-shadow:0 4px 14px rgba(99,102,241,.35)}
/* 布局：左侧列( tab框 + 树 ) 与右侧内容同顶对齐；内容撑满视口高度 */
.layout{flex:1;min-height:0;display:flex;gap:18px;align-items:stretch}
.left-col{width:288px;flex:none;height:100%;display:flex;flex-direction:column;min-height:0}
.sidebar{flex:1;min-height:0;overflow:auto;padding:2px 2px}
.divider{flex:none;width:1px;background:var(--line);margin:2px 0}
.detail{flex:1;min-width:0;display:flex;flex-direction:column;height:100%}
.detail-bar{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:2px 4px 8px}
.detail-bar .dt-title{font-weight:700;font-size:14.5px;display:flex;align-items:center;gap:8px}
.detail-bar .dt-title .pill{font-size:11px;font-weight:700;color:#fff;background:var(--indigo);padding:2px 9px;border-radius:999px}
.detail-bar a.open{color:var(--indigo);text-decoration:none;font-size:13px;font-weight:600;white-space:nowrap}
.detail-bar a.open:hover{text-decoration:underline}
iframe#frame{width:100%;flex:1 1 auto;min-height:0;border:none;background:var(--bg)}
/* 折叠树 */
.group{margin-bottom:6px}
.group-head{width:100%;display:flex;align-items:center;gap:8px;background:transparent;border:none;
  padding:10px 10px;cursor:pointer;color:var(--text);font-size:14px;font-weight:700;border-radius:10px;font-family:inherit}
.group-head:hover{background:var(--hover)}
.chev{display:inline-block;transition:transform .18s ease;color:var(--muted);font-size:11px}
.group.open .chev{transform:rotate(90deg)}
.g-count{margin-left:auto;font-size:12px;color:var(--muted);background:var(--hover);
  padding:1px 9px;border-radius:999px;font-weight:600}
.children{overflow:hidden;max-height:0;transition:max-height .25s ease;padding-left:6px}
.group.open .children{max-height:2000px}
.leaf{display:flex;align-items:center;gap:9px;padding:9px 12px;margin:2px 0;border-radius:10px;
  text-decoration:none;color:var(--text);font-size:14px;cursor:pointer;transition:all .12s ease}
.leaf:hover{background:var(--hover)}
.leaf .l-dot{width:7px;height:7px;border-radius:50%;background:var(--indigo);flex:none;opacity:.55}
.leaf .l-label{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.leaf .l-count{font-size:11.5px;color:var(--muted);background:var(--hover);padding:1px 8px;border-radius:999px}
.leaf.active{background:linear-gradient(135deg,rgba(99,102,241,.14),rgba(139,92,246,.10));color:var(--indigo);font-weight:700}
.leaf.active .l-dot{opacity:1;background:var(--indigo)}
.empty{color:var(--muted);padding:40px 16px;text-align:center;font-size:14px}
footer.page{margin-top:34px;padding-top:16px;border-top:1px solid var(--line);color:var(--muted);font-size:12.5px}
/* 响应式 */
@media (max-width:820px){
  .app{height:auto}
  .layout{flex:none;flex-direction:column;height:auto}
  .left-col{width:100%;height:auto}
  .sidebar{width:100%;height:auto;max-height:300px}
  .divider{display:none}
  iframe#frame{height:62vh;flex:none}
}
""".strip()


def esc(s):
    return html.escape(str(s if s is not None else ""), quote=True)


def to_bj(dt_utc):
    return dt_utc + datetime.timedelta(hours=8)


def parse_iso(s):
    return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))


def now_bj():
    return to_bj(datetime.datetime.now(datetime.timezone.utc))


def human_time(iso, ref):
    if not iso:
        return ""
    try:
        bj = to_bj(parse_iso(iso))
    except Exception:
        return ""
    d = (ref - bj).total_seconds()
    if d < 0:
        d = 0
    if d < 60:
        return "刚刚"
    if d < 3600:
        return f"{int(d // 60)} 分钟前"
    if d < 86400:
        return f"今天 {bj:%H:%M}"
    if d < 172800:
        return f"昨天 {bj:%H:%M}"
    return f"{bj.month}/{bj.day} {bj:%H:%M}"


def date_key(iso):
    if iso:
        try:
            return to_bj(parse_iso(iso)).strftime("%Y-%m-%d")
        except Exception:
            pass
    return now_bj().strftime("%Y-%m-%d")


# 滚动日：每天 07:30 起算，07:30 之前的数据归到前一天。
# 例：2026-08-05 06:00 发布的资讯归到 2026-08-04 的日报里。
DAY_BOUNDARY_HOUR = 7
DAY_BOUNDARY_MIN = 30


def rolling_day_key(dt_bj):
    """按滚动日（07:30 起）返回所属日报的日期字符串。dt_bj 为北京时间。"""
    if (dt_bj.hour, dt_bj.minute) < (DAY_BOUNDARY_HOUR, DAY_BOUNDARY_MIN):
        return (dt_bj - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    return dt_bj.strftime("%Y-%m-%d")


def monday_of(dt_bj):
    return (dt_bj - datetime.timedelta(days=dt_bj.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0)


def fetch(since_iso, take=100, max_items=400):
    items, cursor, page = [], None, 0
    while len(items) < max_items:
        url = f"{API}?mode=selected&since={urllib.parse.quote(since_iso)}&take={take}"
        if cursor:
            url += "&cursor=" + urllib.parse.quote(cursor)
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.load(r)
        except Exception as e:
            print(f"[warn] 拉取数据失败: {e}", file=sys.stderr)
            break
        items.extend(data.get("items", []))
        if not data.get("hasNext") or not data.get("nextCursor"):
            break
        cursor = data["nextCursor"]
        page += 1
        if page > 6:
            break
    seen, uniq = set(), []
    for it in items:
        iid = it.get("id")
        if iid in seen:
            continue
        seen.add(iid)
        uniq.append(it)
    return uniq


def categorize(items):
    """按板块分组；板块内按综合分（score × 板块权重 + 时效加分）降序排列，
    重要的排在前。"""
    groups = {c[0]: [] for c in CATS}
    other = []
    cat_w = {"industry": 1.5, "ai-models": 1.3, "paper": 1.1, "ai-products": 1.0, "tip": 0.8}
    ref = now_bj()
    def imp(it):
        s = float(it.get("score") or 50)
        cw = cat_w.get(it.get("category") or "tip", 1.0)
        try:
            age_h = (ref - to_bj(parse_iso(it.get("publishedAt") or it.get("discoveredAt")))).total_seconds() / 3600
        except Exception:
            age_h = 999
        tw = 20 if age_h < 24 else (12 if age_h < 48 else (6 if age_h < 72 else 0))
        return s * cw + tw
    for it in items:
        it["_imp"] = imp(it)
        cat = it.get("category") or "other"
        if cat in groups:
            groups[cat].append(it)
        else:
            other.append(it)
    if other:
        groups["other"] = other
    for k in groups:
        groups[k].sort(key=lambda x: -x.get("_imp", 0))
    return groups


def item_html(it, ref):
    color = CAT_MAP.get(it.get("category"), OTHER)[2]
    title = esc(it.get("title") or it.get("title_en") or "（无标题）")
    url = esc(it.get("url") or it.get("permalink") or "#")
    summary = esc(it.get("summary") or "")
    source = esc(it.get("source") or "")
    t = human_time(it.get("publishedAt") or it.get("discoveredAt"), ref)
    return f"""      <a class="card" href="{url}" target="_blank" rel="noopener">
        <div class="card-head">
          <span class="cat-dot" style="background:{color}"></span>
          <h3>{title}</h3>
        </div>
        <p class="summary">{summary}</p>
        <div class="meta"><span class="source">{source}</span><span class="time">{t}</span></div>
      </a>"""


def report_sections(items, ref):
    groups = categorize(items)
    cats = list(CATS)
    if "other" in groups:
        cats.append(OTHER)
    parts = []
    for slug, label, color in cats:
        g = groups.get(slug, [])
        if not g:
            continue
        cards = "\n".join(item_html(it, ref) for it in g)
        parts.append(f"""    <section class="sec">
      <h2><span class="bar" style="background:{color}"></span>{label}<span class="cnt">{len(g)} 条</span></h2>
      <div class="cards">
{cards}
      </div>
    </section>""")
    return "\n".join(parts)


def render_report(rel_prefix, period_label, title, subtitle, items, ref,
                  prev_file, next_file, md_file):
    secs = report_sections(items, ref)
    prev_link = (f'<a href="{prev_file}">← 上一{period_label}</a>'
                 if prev_file else '<a class="disabled">← 上一{period_label}</a>'.replace("{period_label}", period_label))
    next_link = (f'<a href="{next_file}">下一{period_label} →</a>'
                 if next_file else f'<a class="disabled">下一{period_label} →</a>')
    back = rel_prefix + "index.html"
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<style>{REPORT_CSS}</style>
</head>
<body>
<div class="wrap">
  <header class="top">
    <span class="brand"><span class="dot"></span>AI HOT 每日速递</span>
    <h1>{esc(title)}</h1>
    <div class="sub">{esc(subtitle)}</div>
    <a class="back" href="{back}" target="_top">← 返回首页 / 归档</a>
  </header>
{secs}
  <div class="nav">
    {prev_link}
    <a href="{md_file}">查看 Markdown 版 →</a>
    {next_link}
  </div>
  <footer>数据来源：由 juicyzhou 设定任务自动整理 · GitHub：<a href="https://github.com/juicyzhou/ai-hot-daily" target="_blank" rel="noopener">git@github.com:juicyzhou/ai-hot-daily.git</a></footer>
</div>
</body>
</html>"""


def render_report_md(title, subtitle, items, ref):
    groups = categorize(items)
    out = [f"# 🤖 {title}", f"> {subtitle}", ""]
    n = 0
    cats = list(CATS)
    if "other" in groups:
        cats.append(OTHER)
    for slug, label, color in cats:
        g = groups.get(slug, [])
        if not g:
            continue
        out.append(f"## {label}")
        for it in g:
            n += 1
            t = it.get("title") or it.get("title_en") or "（无标题）"
            url = it.get("url") or it.get("permalink") or ""
            source = it.get("source") or ""
            tm = human_time(it.get("publishedAt") or it.get("discoveredAt"), ref)
            summary = (it.get("summary") or "").strip()
            line = f"{n}. **{t}** — {source}"
            if tm:
                line += f"（{tm}）"
            out.append(line)
            if summary:
                out.append(f"   {summary}")
            if url:
                out.append(f"   {url}")
            out.append("")
    out.append("---")
    out.append("数据来源：aihot.virxact.com")
    return "\n".join(out)


# ---------------- 首页 SHELL ----------------
SHELL_TMPL = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI HOT 每日速递 · 归档</title>
<style>__SHELL_CSS__</style>
</head>
<body>
<div class="app">
  <div class="topbar">
    <div>
      <span class="brand"><span class="dot"></span>AI HOT 每日速递
        <a class="gh-link" href="https://github.com/juicyzhou/ai-hot-daily" target="_blank" rel="noopener" title="GitHub 仓库：juicyzhou/ai-hot-daily" aria-label="GitHub">
          <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"></path></svg>
        </a>
      </span>
      <h1>AI 圈每日热点</h1>
    </div>
    <div class="today">今日（北京时间）<br><b>__TODAY__</b></div>
  </div>

  <div class="layout">
    <div class="left-col">
      <div class="tabs" id="tabs">
        <button class="tab active" data-tab="daily">日报</button>
        <button class="tab" data-tab="weekly">周报</button>
        <button class="tab" data-tab="monthly">月报</button>
      </div>
      <nav class="sidebar" id="sidebar"></nav>
    </div>
    <div class="divider"></div>
    <section class="detail">
      <div class="detail-bar">
        <div class="dt-title"><span class="pill" id="dt-pill">日报</span><span id="dt-title">—</span></div>
        <a class="open" id="dt-open" href="#" target="_blank">打开原页 ↗</a>
      </div>
      <iframe id="frame" src="about:blank" title="预览"></iframe>
    </section>
  </div>

  <footer class="page">数据来源：由 juicyzhou 设定任务自动整理 · GitHub：<a href="https://github.com/juicyzhou/ai-hot-daily" target="_blank" rel="noopener">git@github.com:juicyzhou/ai-hot-daily.git</a></footer>
</div>
<script>
const INDEX = __INDEX_JSON__;
const PILL = { daily:"日报", weekly:"周报", monthly:"月报" };
let activeTab = "daily";
const selected = {};   // period -> path (记忆每个 tab 的当前选择)

function makeLeaf(period, leaf, isDefault){
  const a = document.createElement("a");
  a.className = "leaf" + (isDefault ? " active" : "");
  a.href = "#";
  a.dataset.path = leaf.path;
  const dot = document.createElement("span"); dot.className = "l-dot";
  const lab = document.createElement("span"); lab.className = "l-label"; lab.textContent = leaf.label;
  a.appendChild(dot); a.appendChild(lab);
  if (leaf.count != null){
    const c = document.createElement("span"); c.className = "l-count"; c.textContent = leaf.count;
    a.appendChild(c);
  }
  a.addEventListener("click", (e)=>{ e.preventDefault(); selectLeaf(period, leaf, a); });
  return a;
}

function buildTab(period){
  const data = INDEX[period];
  const def = selected[period] || data.defaultPath;
  const sb = document.getElementById("sidebar");
  sb.innerHTML = "";
  if (!data.nodes.length){
    sb.innerHTML = '<div class="empty">暂无数据，先跑一次生成器吧～</div>';
    return;
  }
  data.nodes.forEach(node=>{
    if (node.children){               // 折叠分组（月 / 年）
      const hasDef = node.children.some(c => c.path === def);
      const g = document.createElement("div");
      g.className = "group" + (hasDef ? " open" : "");
      const h = document.createElement("button");
      h.className = "group-head";
      h.innerHTML = '<span class="chev">▶</span><span>'+esc(node.label)+'</span>'+
                    '<span class="g-count">'+node.children.length+'</span>';
      const list = document.createElement("div"); list.className = "children";
      node.children.forEach(ch => list.appendChild(makeLeaf(period, ch, ch.path === def)));
      h.addEventListener("click", ()=> g.classList.toggle("open"));
      g.appendChild(h); g.appendChild(list);
      sb.appendChild(g);
    } else {                          // 平铺叶子（单年月的月份）
      sb.appendChild(makeLeaf(period, node, node.path === def));
    }
  });
}

function selectLeaf(period, leaf, el){
  selected[period] = leaf.path;
  document.querySelectorAll(".leaf.active").forEach(x=>x.classList.remove("active"));
  if (el) el.classList.add("active");
  document.getElementById("frame").src = leaf.path;
  document.getElementById("dt-title").textContent = leaf.label;
  document.getElementById("dt-open").href = leaf.path;
}

function switchTab(period){
  activeTab = period;
  document.querySelectorAll(".tab").forEach(t=>t.classList.toggle("active", t.dataset.tab===period));
  document.getElementById("dt-pill").textContent = PILL[period];
  buildTab(period);
  const def = selected[period] || INDEX[period].defaultPath;
  // 触发默认预览
  const el = document.querySelector('.leaf[data-path="'+CSS.escape(def)+'"]');
  const leafObj = findLeaf(INDEX[period], def);
  if (leafObj) selectLeaf(period, leafObj, el);
}

function findLeaf(data, path){
  for (const n of data.nodes){
    if (n.children){ const f = n.children.find(c=>c.path===path); if (f) return f; }
    else if (n.path === path) return n;
  }
  return null;
}

function esc(s){ const d=document.createElement("div"); d.textContent=s; return d.innerHTML; }

document.getElementById("tabs").addEventListener("click", e=>{
  const b = e.target.closest(".tab"); if (!b) return;
  switchTab(b.dataset.tab);
});

// 初始：日报 + 最新一天
switchTab("daily");
</script>
</body>
</html>"""


def render_index(index_data):
    today = now_bj().strftime("%Y-%m-%d %H:%M")
    html = (SHELL_TMPL
            .replace("__SHELL_CSS__", SHELL_CSS)
            .replace("__TODAY__", today)
            .replace("__INDEX_JSON__", json.dumps(index_data, ensure_ascii=False)))
    return html


def rel_prefix_for(filepath):
    d = os.path.dirname(filepath)
    rel = os.path.relpath(ROOT, d)        # 从文件目录回到仓库根
    return rel + "/" if rel != "." else ""


def write_pair(html_path, md_path, html_content, md_content):
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)


def main():
    ap = argparse.ArgumentParser(description="生成 AI HOT 每日/周/月速递")
    ap.add_argument("--since-days", type=int, default=31, help="回看天数（默认 31 天，保证周报/月报覆盖完整周期）")
    ap.add_argument("--take", type=int, default=100, help="每次拉取条数上限")
    args = ap.parse_args()

    manifest = load_manifest()
    ref = now_bj()
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    since = (now_utc - datetime.timedelta(days=args.since_days)).strftime("%Y-%m-%dT%H:%M:%SZ")

    print(f"[info] 拉取最近 {args.since_days} 天精选（since={since}）...")
    items = fetch(since, args.take)
    print(f"[info] 拉到 {len(items)} 条")

    # 分组
    # 日报：按滚动日（07:30 起），例如 08-05 06:00 的资讯归入 08-04 日报
    daily = {}     # date -> [items]
    weekly = {}    # monday_date -> [items]
    monthly = {}   # (y,m) -> [items]
    for it in items:
        bj = to_bj(parse_iso(it.get("publishedAt") or it.get("discoveredAt")
                             or now_utc.isoformat()))
        dk = rolling_day_key(bj)
        daily.setdefault(dk, []).append(it)
        mk = monday_of(bj).strftime("%Y-%m-%d")
        weekly.setdefault(mk, []).append(it)
        monthly.setdefault((bj.year, bj.month), []).append(it)

    # ---------- 日报 ----------
    daily_dates = sorted(daily.keys())
    for i, dk in enumerate(daily_dates):
        y, m, _ = dk.split("-")
        its = daily[dk]
        ddir = os.path.join(ROOT, "daily", y, m)
        os.makedirs(ddir, exist_ok=True)
        prev_f = f"{daily_dates[i-1]}.html" if i > 0 else None
        next_f = f"{daily_dates[i+1]}.html" if i < len(daily_dates)-1 else None
        html_path = os.path.join(ddir, f"{dk}.html")
        md_path = os.path.join(ddir, f"{dk}.md")
        wk = WEEKDAYS[parse_iso(dk + "T00:00:00+08:00").weekday()]
        title = f"AI HOT 每日速递 · {dk}"
        # 滚动窗口：日报 = 当天 07:30 ~ 次日 07:30
        dk_date = parse_iso(dk + "T00:00:00+08:00")
        next_dk = (dk_date + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        subtitle = f"共 {len(its)} 条精选 · 统计时段 {dk} 07:30 ~ {next_dk} 07:30（北京时间）"
        write_pair(
            html_path, md_path,
            render_report(rel_prefix_for(html_path), "天", title, subtitle, its, ref, prev_f, next_f, f"{dk}.md"),
            render_report_md(title, subtitle, its, ref),
        )
        manifest["daily"][dk] = {
            "path": f"daily/{y}/{m}/{dk}.html",
            "label": f"{dk} {wk}",
            "count": len(its),
        }
    print(f"[ok] 日报：{len(daily_dates)} 期（{daily_dates[0]} ~ {daily_dates[-1]}）")

    # ---------- 周报 ----------
    wk_dates = sorted(weekly.keys())
    for i, mk in enumerate(wk_dates):
        mdt = parse_iso(mk + "T00:00:00+08:00")
        wk_num = mdt.isocalendar()[1]
        sunday = mdt + datetime.timedelta(days=6)
        range_label = f"{mdt:%m-%d}~{sunday:%m-%d}"
        its = weekly[mk]
        y, m = mdt.year, mdt.month
        wdir = os.path.join(ROOT, "weekly", str(y), f"{m:02d}")
        os.makedirs(wdir, exist_ok=True)
        prev_f = f"{wk_dates[i-1]}.html" if i > 0 else None
        next_f = f"{wk_dates[i+1]}.html" if i < len(wk_dates)-1 else None
        title = f"AI HOT 每周速递 · 第{wk_num}周（{range_label}）"
        subtitle = f"共 {len(its)} 条精选 · 统计时段 {range_label}（北京时间）"
        html_path = os.path.join(wdir, f"{mk}.html")
        md_path = os.path.join(wdir, f"{mk}.md")
        write_pair(
            html_path, md_path,
            render_report(rel_prefix_for(html_path), "周", title, subtitle, its, ref, prev_f, next_f, f"{mk}.md"),
            render_report_md(title, subtitle, its, ref),
        )
        manifest["weekly"][mk] = {
            "path": f"weekly/{y}/{m:02d}/{mk}.html",
            "label": f"第{wk_num}周 · {range_label}",
            "count": len(its),
        }
    print(f"[ok] 周报：{len(wk_dates)} 期")

    # ---------- 月报 ----------
    mo_keys = sorted(monthly.keys())
    for i, (y, m) in enumerate(mo_keys):
        its = monthly[(y, m)]
        mdir = os.path.join(ROOT, "monthly", str(y))
        os.makedirs(mdir, exist_ok=True)
        prev_key = mo_keys[i-1] if i > 0 else None
        next_key = mo_keys[i+1] if i < len(mo_keys)-1 else None
        prev_f = f"{prev_key[0]}-{prev_key[1]:02d}.html" if prev_key else None
        next_f = f"{next_key[0]}-{next_key[1]:02d}.html" if next_key else None
        title = f"AI HOT 每月速递 · {y} 年 {m} 月"
        subtitle = f"共 {len(its)} 条精选 · 统计时段 {y}-{m:02d}（北京时间）"
        fname = f"{y}-{m:02d}"
        html_path = os.path.join(mdir, f"{fname}.html")
        md_path = os.path.join(mdir, f"{fname}.md")
        write_pair(
            html_path, md_path,
            render_report(rel_prefix_for(html_path), "月", title, subtitle, its, ref, prev_f, next_f, f"{fname}.md"),
            render_report_md(title, subtitle, its, ref),
        )
        manifest["monthly"][f"{y}-{m:02d}"] = {
            "path": f"monthly/{y}/{y}-{m:02d}.html",
            "label": f"{y} 年 {m} 月",
            "count": len(its),
        }
    print(f"[ok] 月报：{len(mo_keys)} 期")

    # ---------- 构建首页 INDEX（基于 manifest，跨运行累计全部历史期次）----------
    def latest_key(d):
        return max(d.keys()) if d else ""

    # 日报：按月分组（年-月）
    daily_nodes = []
    d_groups = {}
    for dk, e in manifest["daily"].items():
        y, m, _ = dk.split("-")
        d_groups.setdefault((y, m), []).append((dk, e))
    for (y, m) in sorted(d_groups.keys(), reverse=True):
        children = [{
            "label": e["label"],
            "path": e["path"],
            "count": e["count"],
        } for dk, e in sorted(d_groups[(y, m)], key=lambda x: x[0], reverse=True)]
        daily_nodes.append({"label": f"{y} 年 {m} 月", "children": children})

    # 周报：按月分组（周一所在月）
    weekly_nodes = []
    w_groups = {}
    for mk, e in manifest["weekly"].items():
        parts = e["path"].split("/")          # weekly/<y>/<m>/<mk>.html
        w_groups.setdefault((parts[1], parts[2]), []).append((mk, e))
    for (y, m) in sorted(w_groups.keys(), reverse=True):
        children = [{
            "label": e["label"],
            "path": e["path"],
            "count": e["count"],
        } for mk, e in sorted(w_groups[(y, m)], key=lambda x: x[0], reverse=True)]
        weekly_nodes.append({"label": f"{y} 年 {m} 月", "children": children})

    # 月报：跨年则按年分组，单年则平铺
    monthly_nodes = []
    years = sorted({k.split("-")[0] for k in manifest["monthly"].keys()})
    if len(years) > 1:
        m_groups = {}
        for key, e in manifest["monthly"].items():
            m_groups.setdefault(key.split("-")[0], []).append((key, e))
        for y in sorted(m_groups.keys(), reverse=True):
            children = [{
                "label": e["label"],
                "path": e["path"],
                "count": e["count"],
            } for key, e in sorted(m_groups[y], key=lambda x: x[0], reverse=True)]
            monthly_nodes.append({"label": f"{y} 年", "children": children})
    else:
        for key, e in sorted(manifest["monthly"].items(), key=lambda x: x[0], reverse=True):
            monthly_nodes.append({
                "label": e["label"],
                "path": e["path"],
                "count": e["count"],
            })

    index_data = {
        "daily": {
            "defaultPath": manifest["daily"][latest_key(manifest["daily"])]["path"]
                           if manifest["daily"] else "",
            "nodes": daily_nodes,
        },
        "weekly": {
            "defaultPath": manifest["weekly"][latest_key(manifest["weekly"])]["path"]
                           if manifest["weekly"] else "",
            "nodes": weekly_nodes,
        },
        "monthly": {
            "defaultPath": manifest["monthly"][latest_key(manifest["monthly"])]["path"]
                           if manifest["monthly"] else "",
            "nodes": monthly_nodes,
        },
    }

    save_manifest(manifest)
    with open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8") as f:
        f.write(render_index(index_data))
    print(f"[ok] index.html 已生成（累计归档：日报 {len(manifest['daily'])} / 周报 {len(manifest['weekly'])} / 月报 {len(manifest['monthly'])} 期）")


if __name__ == "__main__":
    main()
