# -*- coding: utf-8 -*-
"""
從 Gachabase 抓取本資料夾 link.txt 第一行 URL，對照 all_json.csv／slider／silder（不依賴 PyQt6）。
預期 CSV 含 Elation Skill（與本角色 Gachabase 頁一致時）。
執行：py verify_gachabase.py
"""
from __future__ import annotations

import csv
import os
import re
import sys

import requests
from bs4 import BeautifulSoup

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(SCRIPT_DIR, "all_json.csv")
SLIDER_PATH = os.path.join(SCRIPT_DIR, "skill_slider_script.js")
SKILL_SILD_PATH = os.path.join(SCRIPT_DIR, "all_skill_silder.txt")

GACHABASE_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,zh-TW;q=0.8",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
}


def load_url_from_link_txt():
    path = os.path.join(SCRIPT_DIR, "link.txt")
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    return lines[0].strip() if lines else ""


def parse_gachabase_stats(page_text: str) -> dict:
    stats = {}
    for pattern, key in [
        (r"Base HP\s*\n?\s*(\d[\d,]*)", "hp"),
        (r"Base ATK\s*\n?\s*(\d[\d,]*)", "atk"),
        (r"Base DEF\s*\n?\s*(\d[\d,]*)", "def"),
        (r"\bSPD\s*\n?\s*(\d+)", "spd"),
        (r"Taunt\s*\n?\s*(\d+)", "taunt"),
        (r"Energy Cost\s*\n?\s*(\d+)", "energy_cost"),
    ]:
        m = re.search(pattern, page_text, re.IGNORECASE)
        if m:
            stats[key] = int(m.group(1).replace(",", ""))
    return stats


def parse_gachabase_eidolons(page_text: str) -> dict:
    eidolons = {}
    lines = page_text.split("\n")
    eid_start = None
    for i, line in enumerate(lines):
        if line.strip().lower() == "eidolons":
            eid_start = i + 1
            break
    if eid_start is None:
        return eidolons
    eid_end = len(lines)
    for j in range(eid_start, len(lines)):
        low = lines[j].strip().lower()
        if low in ("materials calculator", "materials required", "level calculator"):
            eid_end = j
            break
    section = lines[eid_start:eid_end]
    positions = []
    for i, line in enumerate(section):
        stripped = line.strip()
        if stripped in ("01", "02", "03", "04", "05", "06"):
            positions.append((int(stripped), i))
    for idx, (num, start_i) in enumerate(positions):
        end_i = positions[idx + 1][1] if idx + 1 < len(positions) else len(section)
        block = [l.strip() for l in section[start_i + 1 : end_i] if l.strip()]
        block = [l for l in block if l.lower() != "effects"]
        name = block[0] if block else ""
        desc = " ".join(block[1:]) if len(block) > 1 else ""
        desc = re.sub(r"\s+", " ", desc).strip()
        eidolons[num] = {"name": name, "desc": desc}
    for num in range(1, 7):
        eidolons.setdefault(num, {"name": "", "desc": ""})
    return eidolons


def parse_gachabase_trace_tiers(page_text: str) -> list:
    tiers = []
    lines = page_text.split("\n")
    trace_start = None
    for i, line in enumerate(lines):
        if line.strip().lower() == "traces":
            trace_start = i + 1
            break
    if trace_start is None:
        return tiers
    trace_end = len(lines)
    for j in range(trace_start, len(lines)):
        low = lines[j].strip().lower()
        if low in ("eidolons", "materials calculator", "materials required"):
            trace_end = j
            break
    section = "\n".join(lines[trace_start:trace_end])
    boost_pattern = (
        r"((?:HP|ATK|DEF|SPD|CRIT Rate|CRIT DMG|Elation|Effect Hit Rate|Effect RES|"
        r"Break Effect|Energy Regeneration Rate)\s+Boost)\s*\n\s*(.+?)(?=Breakdown|$)"
    )
    for m in re.finditer(boost_pattern, section, re.IGNORECASE | re.DOTALL):
        label = m.group(1).strip().replace(" Boost", "")
        value_text = m.group(2).strip()
        v = re.search(r"increases?\s+by\s+([\d.]+%?)", value_text, re.I)
        if v:
            tiers.append(f"{label} + {v.group(1)}")
    return tiers


def read_csv_types():
    types = []
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            types.append(row.get("type", "").strip())
    return types


def main() -> int:
    url = load_url_from_link_txt()
    if not url:
        print("FAIL: link.txt 第一行為空")
        return 1
    print("URL:", url)
    r = requests.get(url, headers=GACHABASE_HEADERS, timeout=45)
    r.raise_for_status()
    raw = r.text
    soup = BeautifulSoup(raw, "html.parser")
    page_text = soup.get_text(separator="\n")

    stats = parse_gachabase_stats(page_text)
    eids = parse_gachabase_eidolons(page_text)
    traces = parse_gachabase_trace_tiers(page_text)

    ok = True
    print("\n=== Gachabase 解析（供 skill_viewer 面板）===")
    if len(stats) >= 4:
        print("OK 基礎數值:", stats)
    else:
        print("WARN 基礎數值不完整:", stats)
        ok = False

    named = sum(1 for n in range(1, 7) if (eids.get(n) or {}).get("name"))
    if named == 6:
        print("OK 星魂區塊：6 個名稱已解析")
    else:
        print(f"WARN 星魂名稱僅 {named}/6（檢查頁面是否改版）")
        ok = False

    if traces:
        print(f"OK Traces 小屬性加成列：{len(traces)} 條")
        for t in traces:
            print("   ", t)
    else:
        print("WARN Traces 加成列為空（Ddesc 載入後可能無 Extra Attributes）")

    csv_types = read_csv_types()
    expected_core = [
        "Basic ATK",
        "Skill",
        "Ultimate",
        "Technique",
        "Talent",
        "Elation Skill",
        "Adesc",
        "Bdesc",
        "Cdesc",
        "Ddesc",
    ]
    print("\n=== 對照 HH_extraction_guide / all_json.csv ===")
    missing = [t for t in expected_core if t not in csv_types]
    if not missing:
        print("OK CSV 含核心 type 列（含 Elation Skill、Ddesc）")
    else:
        print("FAIL CSV 缺少 type:", missing)
        ok = False

    if os.path.isfile(SKILL_SILD_PATH):
        txt = open(SKILL_SILD_PATH, "r", encoding="utf-8").read()
        if 'span id="a1"' in txt:
            print("OK all_skill_silder.txt 含 a1 模板")
        else:
            print("WARN all_skill_silder.txt 未見 a1")
    else:
        print("FAIL 缺少 all_skill_silder.txt")
        ok = False

    if os.path.isfile(SLIDER_PATH):
        js = open(SLIDER_PATH, "r", encoding="utf-8").read()
        if "sliderValues" in js and "a1:" in js:
            print("OK skill_slider_script.js 含 sliderValues / a1")
        else:
            print("WARN skill_slider_script.js 結構異常")
    else:
        print("FAIL 缺少 skill_slider_script.js")
        ok = False

    print("\n結果:", "通過（可開 skill_viewer 載入連結再確認 UI）" if ok else "有警告或失敗，請看上文")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
