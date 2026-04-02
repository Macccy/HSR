# -*- coding: utf-8 -*-
"""從 link.txt 第一行 Gachabase URL 抓取技能／行跡區塊，寫入 all_json.csv（Lv1 HTML + 空階層位）。"""
from __future__ import annotations

import csv
import html
import os
import re

import requests
from bs4 import BeautifulSoup

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

SKILL_SECTION_MAP = [
    ("skill-type-1", "Basic ATK"),
    ("skill-type-2", "Skill"),
    ("skill-type-3", "Ultimate"),
    ("skill-type-7", "Technique"),
    ("skill-type-0", "Talent"),
    ("skill-type-14", "Elation Skill"),
]

TRACE_SECTION_IDS = [
    ("trace-8010101", "Adesc", "ASCEND CALCULATOR A", "On Cloud Nine"),
    ("trace-8010102", "Bdesc", "ASCEND CALCULATOR B", "Screw It, We Ball"),
    ("trace-8010103", "Cdesc", "ASCEND CALCULATOR C", "Aha, Sic 'Em!"),
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
    """先找數字再上傳逸，避免 &#x27; 內的數字被誤標高亮。"""
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
        return fallback_name, ""
    h = sec.find(["h2", "h3"])
    name = h.get_text(strip=True) if h else fallback_name
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
    r = requests.get(url, headers=HDR, timeout=60)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    rows: list[dict] = []
    for sec_id, stype in SKILL_SECTION_MAP:
        n, t, h = parse_skill_section(soup, sec_id)
        rows.append(csv_row(stype, n, t, h))

    for sec_id, stype, calc_title, name_fb in TRACE_SECTION_IDS:
        n, h = parse_trace_section(soup, sec_id, name_fb)
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
    print("寫入", out, "共", len(rows), "列")


if __name__ == "__main__":
    main()
