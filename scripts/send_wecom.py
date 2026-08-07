#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把当日 AI HOT 日报推送到企业微信 AIGC 群（纯文本，自动按版块分段规避 2048 字节上限）。

用法:
    python3 scripts/send_wecom.py [REPORT_DATE]     # 默认取昨天（滚动日窗口）
    python3 scripts/send_wecom.py --dry-run         # 只打印分段，不发送

依赖: wecom-cli 已登录（企业微信连接器 connected）。
"""
import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys

CHATID = "wrEGnWGwAAzrhgb5uSwTIXBsDjTUdOXA"
SITE = "https://juicyzhou.github.io/ai-hot-daily"
MAX_BYTES = 1900  # 企业微信文本上限 2048 字节，留安全余量
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def blen(s: str) -> int:
    return len(s.encode("utf-8"))


def parse_markdown(md_path: str):
    """解析日报 md，返回 (sections, total)。sections = [(版块名, [条目行...])]"""
    text = open(md_path, encoding="utf-8").read()
    sections, cur, total = [], None, 0
    for line in text.splitlines():
        if line.startswith("## "):
            cur = (line[3:].strip(), [])
            sections.append(cur)
            continue
        m = re.match(r"^(\d+)\.\s+\*\*(.+?)\*\*\s+—\s+(.+?)（[^（）]*）\s*$", line)
        if m and cur is not None:
            cur[1].append("%s. %s — %s" % (m.group(1), m.group(2).strip(), m.group(3).strip()))
            total += 1
    return sections, total


def build_segments(report_date: str, sections, total: int):
    url = "%s/daily/%s/%s/%s.html" % (SITE, report_date[:4], report_date[5:7], report_date)
    header = (
        "🤖 AI HOT 每日速递 · %s（早08:00更新）\n"
        "统计时段：%s 07:30 ~ 今天 07:30（北京时间）\n"
        "共 %d 条 · 5 大板块\n" % (report_date, report_date, total)
    )
    footer = "📖 完整图文：%s\n数据来源：aihot.virxact.com" % url

    blocks = [
        "【%s】（%d 条）\n" % (name, len(items)) + "\n".join(items)
        for name, items in sections
        if items
    ]

    segments, cur_seg = [], header
    for b in blocks:
        candidate = cur_seg + "\n" + b + "\n"
        if blen(candidate) + 40 > MAX_BYTES and cur_seg.strip() != header.strip():
            segments.append(cur_seg.rstrip())
            cur_seg = b + "\n"
        else:
            cur_seg = candidate
    if blen(cur_seg + "\n" + footer) <= MAX_BYTES:
        segments.append((cur_seg + "\n" + footer).rstrip())
    else:
        segments.append(cur_seg.rstrip())
        segments.append(footer)

    n = len(segments)
    if n > 1:
        segments = [
            (s + "\n（接下一条 %d/%d）" % (i + 1, n)) if i < n - 1 else s
            for i, s in enumerate(segments)
        ]
    return segments


def send(segment: str) -> bool:
    payload = json.dumps(
        {"chat_type": 2, "chatid": CHATID, "msgtype": "text", "text": {"content": segment}},
        ensure_ascii=False,
    )
    r = subprocess.run(["wecom-cli", "msg", "send_message", payload], capture_output=True, text=True)
    out = (r.stdout or "") + (r.stderr or "")
    # wecom-cli 走 MCP 通道，返回体里 errcode 是被转义的（\"errcode\": 0），需归一化后再判断
    flat = out.replace("\\", "")
    ok = '"errcode": 0' in flat or '"errcode":0' in flat
    print("[send] ok=%s %s" % (ok, out.strip()[:300]))
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("report_date", nargs="?", default=None, help="YYYY-MM-DD，默认昨天")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    report_date = args.report_date or (dt.date.today() - dt.timedelta(days=1)).isoformat()
    md_path = os.path.join(ROOT, "daily", report_date[:4], report_date[5:7], report_date + ".md")
    if not os.path.exists(md_path):
        print("[error] 日报不存在: %s（请先运行 scripts/generate.py）" % md_path, file=sys.stderr)
        return 1

    sections, total = parse_markdown(md_path)
    if total == 0:
        print("[error] 未解析到任何条目: %s" % md_path, file=sys.stderr)
        return 1

    segments = build_segments(report_date, sections, total)
    for i, s in enumerate(segments, 1):
        print("--- 段 %d/%d，%d 字节 ---" % (i, len(segments), blen(s)))
        if blen(s) > 2048:
            print("[error] 段 %d 超 2048 字节，需减小 MAX_BYTES" % i, file=sys.stderr)
            return 1

    if args.dry_run:
        for s in segments:
            print("\n" + s)
        return 0

    failed = sum(0 if send(s) else 1 for s in segments)
    print("[done] 共 %d 段，失败 %d 段" % (len(segments), failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
