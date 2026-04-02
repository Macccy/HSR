# -*- coding: utf-8 -*-
"""從 link.txt 第一行 Gachabase URL 抓取技能／行跡區塊，寫入 all_json.csv（Lv1 HTML + 空階層位）。

自動解析 URL 中的角色 ID、頁面上的 trace-{id}xxx 與是否含 skill-type-14（Elation）。
"""
from __future__ import annotations

import csv
import html
import os
import re

import requests
from bs4 import BeautifulSoup

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

BASE_SKILL_MAP = [
    ("skill-type-1", "Basic ATK"),
    ("skill-type-2", "Skill"),
    ("skill-type-3", "Ultimate"),
    ("skill-type-7", "Technique"),
    ("skill-type-0", "Talent"),
]

TRACE_LABELS = [
    ("Adesc", "ASCEND CALCULATOR A"),
    ("Bdesc", "ASCEND CALCULATOR B"),
    ("Cdesc", "ASCEND CALCULATOR C"),
]

HEADERS = (
    ["type", "name", "title"]
    + [f"desc_lv{i}" for i in range(1, 16)]
    + [f"raw_html_lv{i}" for i in range(1, 16)]
    + ["tier1", "tier2", "tier3"]
)

HDR = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0.0.0"}


def load_url() -> str:
    path = os.path.join(SCRIPT_DIR, "link.txt")
    with open(path, "r", encoding="utf-8") as f:
        line = f.readline().strip()
    if not line:
        raise SystemExit("link.txt 第一行為空")
    return line


def char_id_from_url(url: str) -> str:
    m = re.search(r"/characters/(\d+)/", url)
    if not m:
        raise SystemExit("URL 需包含 /characters/<數字ID>/")
    return m.group(1)


def discover_trace_section_ids(soup: BeautifulSoup, char_id: str) -> list[str]:
    """例如 1505 → trace-1505101, trace-1505102（排除 trace-stat-*）。"""
    out = []
    for sec in soup.find_all("section", id=True):
        sid = sec.get("id") or ""
        if "trace-stat" in sid:
            continue
        if re.fullmatch(rf"trace-{re.escape(char_id)}\d{{3}}", sid):
            out.append(sid)
    return sorted(out)


def strip_vue_comments(s: str) -> str:
    return re.sub(r"<!--.*?-->", "", s, flags=re.DOTALL)


def normalize_inline_highlights(fragment: str) -> str:
    s = strip_vue_comments(fragment)
    s = s.replace("color: #f29e38;", "color: #f29e38ff;")
    s = re.sub(
        r'<div class="inline-block inline-flex cursor-pointer text-hsr-highlight">([^<]*)</div>',
        r'<span style="color: #f29e38ff;"><strong>\1</strong></span>',
        s,
    )
    return s


def prose_to_html(text: str) -> str:
    t = text.strip()
    parts: list[str] = []
    last = 0
    for m in re.finditer(r"\d+(?:\.\d+)?%?", t):
        parts.append(html.escape(t[last : m.start()]))
        parts.append(
            f'<span style="color: #f29e38ff;"><strong>{html.escape(m.group(0))}</strong></span>'
        )
        last = m.end()
    parts.append(html.escape(t[last:]))
    return "".join(parts).replace("\n", "<br>")


def parse_skill_section(soup: BeautifulSoup, section_id: str) -> tuple[str, str, str]:
    sec = soup.find("section", id=section_id)
    if not sec:
        return "", "", ""
    outer = sec.select_one("div.flex.flex-col.gap-2\\.5.text-sm > div.flex.flex-col.gap-2\\.5")
    if not outer:
        return "", "", ""
    header = outer.select_one("div.flex.gap-2\\.5.items-center div.flex.flex-col.min-h-10")
    name = ""
    title = ""
    if header:
        nb = header.select_one("span.font-bold span")
        if nb:
            name = nb.get_text(strip=True)
        ht = header.select_one("span.text-hsr-highlight-2")
        if ht:
            title = ht.get_text(strip=True).strip("[]")
    spans = [c for c in outer.children if getattr(c, "name", None) == "span"]
    desc_html = ""
    if spans:
        best = max(spans, key=lambda s: len(s.get_text()))
        desc_html = normalize_inline_highlights(str(best))
    return name, title, desc_html


def parse_trace_section(soup: BeautifulSoup, section_id: str, fallback_name: str) -> tuple[str, str]:
    sec = soup.find("section", id=section_id)
    if not sec:
        return (fallback_name or "", "")
    h = sec.find(["h2", "h3"])
    name = h.get_text(strip=True) if h else (fallback_name or "")
    body = sec.get_text("\n", strip=True)
    if "Requirement" in body:
        body = body.split("Requirement", 1)[0].strip()
    lines = [ln.strip() for ln in body.split("\n") if ln.strip()]
    if not lines:
        return name, ""
    if lines[0] == name:
        desc_text = " ".join(lines[1:])
    else:
        desc_text = " ".join(lines)
    return name, prose_to_html(desc_text)


def csv_row(skill_type: str, name: str, title: str, lv1_html: str) -> dict:
    row = {"type": skill_type, "name": name, "title": title}
    for i in range(15):
        row[f"desc_lv{i + 1}"] = lv1_html if i == 0 else ""
        row[f"raw_html_lv{i + 1}"] = lv1_html if i == 0 else ""
    row["tier1"] = row["tier2"] = row["tier3"] = ""
    return row


def main() -> None:
    url = load_url()
    char_id = char_id_from_url(url)
    r = requests.get(url, headers=HDR, timeout=60)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    rows: list[dict] = []
    for sec_id, stype in BASE_SKILL_MAP:
        n, t, h = parse_skill_section(soup, sec_id)
        rows.append(csv_row(stype, n, t, h))

    if soup.find("section", id="skill-type-14"):
        n, t, h = parse_skill_section(soup, "skill-type-14")
        rows.append(csv_row("Elation Skill", n, t, h))

    trace_ids = discover_trace_section_ids(soup, char_id)
    for i, tid in enumerate(trace_ids[:3]):
        stype, calc_title = TRACE_LABELS[i] if i < len(TRACE_LABELS) else ("Ddesc", "ASCEND CALCULATOR D")
        n, h = parse_trace_section(soup, tid, "")
        rows.append(csv_row(stype, n, calc_title, h))

    rows.append(
        csv_row(
            "Ddesc",
            "Extra Attributes",
            "ASCEND CALCULATOR D",
            "",
        )
    )

    out = os.path.join(SCRIPT_DIR, "all_json.csv")
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=HEADERS)
        w.writeheader()
        for row in rows:
            w.writerow(row)
    print("寫入", out, "共", len(rows), "列（角色 ID", char_id, "）")


if __name__ == "__main__":
    main()
