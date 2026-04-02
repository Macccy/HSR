# -*- coding: utf-8 -*-
import os
import re
import csv
from datetime import datetime
from urllib.parse import urljoin, urlparse
import requests
from PIL import Image
from io import BytesIO
try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

# 統一下載目錄與 CSV 記錄路徑（與 materials_download_log 欄位對齊）
DEFAULT_DOWNLOAD_ROOT = r"C:\Users\User\OneDrive\桌面\python\hsr\img"
DEFAULT_CSV_PATH = r"C:\Users\User\OneDrive\桌面\python\hsr\materials_download_log.csv"
CSV_FIELDNAMES = [
    "Filename", "local_path", "url", "status", "file_size_kb", "timestamp",
    "item_id", "item_name", "URL", "Type", "Featured ID", "Upload Date"
]

# Gachabase 角色頁抓取用（與 skill_viewer.GACHABASE_HEADERS 對齊）
GACHABASE_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,zh-TW;q=0.8",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
}

_RE_GACHABASE_CDN = re.compile(
    r"https://cdn\.gachabase\.net/hsr/assets/([a-f0-9]{32})\.png", re.I
)
_RE_GACHABASE_CONV = re.compile(
    r"https://img\.gachabase\.net/conv/hsr/assets/([a-f0-9]{32})\.png", re.I
)


def _gachabase_cdn_from_any_url(url):
    """從 cdn 或 img/conv URL 取得標準 cdn.png 連結。"""
    if not url:
        return None
    m = _RE_GACHABASE_CDN.search(url)
    if m:
        h = m.group(1).lower()
        return f"https://cdn.gachabase.net/hsr/assets/{h}.png"
    m = _RE_GACHABASE_CONV.search(url)
    if m:
        h = m.group(1).lower()
        return f"https://cdn.gachabase.net/hsr/assets/{h}.png"
    return None


def parse_gachabase_image_plan(html):
    """
    依 section 子樹與屬性整理要下載的 cdn URL（Skills / Traces / Eidolons / Materials）。
    回傳 dict:
      skills, traces, eidolon_big, eidolon_small: list[str] cdn url
      materials: list[str] cdn url（依 DOM 順序去重）
    """
    if BeautifulSoup is None:
        raise RuntimeError("需要安裝 beautifulsoup4：pip install beautifulsoup4")
    soup = BeautifulSoup(html, "html.parser")
    plan = {
        "skills": [],
        "traces": [],
        "eidolon_big": [],
        "eidolon_small": [],
        "materials": [],
    }

    def append_preview_urls(section, group_filter, out_list):
        if section is None:
            return
        for tag in section.find_all(True):
            g = tag.get("data-preview-group") or ""
            if group_filter and g != group_filter:
                continue
            u = tag.get("data-preview-src") or ""
            cdn = _gachabase_cdn_from_any_url(u)
            if cdn:
                out_list.append(cdn)

    sec_skills = soup.find("section", id="skills")
    append_preview_urls(sec_skills, "character-skill-icon", plan["skills"])

    sec_traces = soup.find("section", id="traces")
    append_preview_urls(sec_traces, "character-trace-icon", plan["traces"])

    sec_eid = soup.find("section", id="eidolons")
    if sec_eid:
        for tag in sec_eid.find_all(True):
            g = tag.get("data-preview-group") or ""
            u = tag.get("data-preview-src") or ""
            cdn = _gachabase_cdn_from_any_url(u)
            if not cdn:
                continue
            if g == "eidolons":
                plan["eidolon_big"].append(cdn)
            elif g == "eidolon-icons":
                plan["eidolon_small"].append(cdn)

    sec_lv = soup.find("section", id="level-calculator")
    if sec_lv:
        seen_m = set()
        for img in sec_lv.find_all("img"):
            src = (img.get("src") or "").strip()
            cdn = _gachabase_cdn_from_any_url(src)
            if not cdn:
                continue
            h = cdn.rsplit("/", 1)[-1].replace(".png", "")
            if h in seen_m:
                continue
            seen_m.add(h)
            plan["materials"].append(cdn)

    return plan


def run_download_gachabase(page_url, char_name, download_folder=None, verbose=True):
    """
    從 Gachabase 角色頁（HTML）解析 Skills / Traces / Eidolons / Materials 圖片並下載為 WebP。
    不依賴 Hakush API。回傳 (成功筆數, 失敗的說明列表)。
    """
    if download_folder is None:
        download_folder = DEFAULT_DOWNLOAD_ROOT
    safe_name = re.sub(r'[^\w\s-]', '', (char_name or "character").strip()) or "character"
    safe_name = re.sub(r"\s+", "_", safe_name)

    os.makedirs(download_folder, exist_ok=True)
    log_rows = []
    csv_downloaded = _load_csv_downloaded_set(DEFAULT_CSV_PATH)

    try:
        r = requests.get(page_url, headers=GACHABASE_HEADERS, timeout=45)
        r.raise_for_status()
    except Exception as e:
        if verbose:
            print(f"❌ 無法取得 Gachabase 頁面: {e}")
        return (0, [str(e)])

    try:
        plan = parse_gachabase_image_plan(r.text)
    except Exception as e:
        if verbose:
            print(f"❌ 解析頁面失敗: {e}")
        return (0, [str(e)])

    if verbose:
        print(f"📁 資料夾: {download_folder}")
        print(f"🌐 Gachabase: {page_url}")
        print(
            f"   解析：skill={len(plan['skills'])} trace={len(plan['traces'])} "
            f"eidolon圖={len(plan['eidolon_small'])} eidolon畫={len(plan['eidolon_big'])} "
            f"material={len(plan['materials'])}"
        )

    jobs = []  # (final_base_name, cdn_url, row_type)
    for i, u in enumerate(plan["skills"], 1):
        jobs.append((f"{safe_name}_gb_skill{i:02d}", u, "gachabase_skill"))
    for i, u in enumerate(plan["traces"], 1):
        jobs.append((f"{safe_name}_gb_trace{i:02d}", u, "gachabase_trace"))
    for i, u in enumerate(plan["eidolon_small"], 1):
        jobs.append((f"{safe_name}_gb_eidolon_icon{i}", u, "gachabase_eidolon_icon"))
    for i, u in enumerate(plan["eidolon_big"], 1):
        jobs.append((f"{safe_name}_gb_eidolon_art{i}", u, "gachabase_eidolon_art"))
    for u in plan["materials"]:
        h = u.rsplit("/", 1)[-1].replace(".png", "")[:12]
        jobs.append((f"{safe_name}_gb_mat_{h}", u, "gachabase_material"))

    downloaded_count = 0
    failed_images = []
    min_b = MIN_IMAGE_SIZE_GACHABASE

    for base, cdn_url, row_type in jobs:
        final_path = os.path.join(download_folder, f"{base}.webp")
        final_fn = os.path.basename(final_path)
        if final_fn in csv_downloaded and os.path.exists(final_path) and os.path.getsize(final_path) >= min_b:
            downloaded_count += 1
            if verbose:
                print(f"⏭️ {final_fn}（已存在，略過）")
            continue

        tmp_png = os.path.join(download_folder, f"_tmp_{base}.png")
        ok = download_image(
            cdn_url, tmp_png, verbose=False, referer=page_url, min_bytes=min_b
        )
        if not ok:
            log_rows.append(
                _log_row(final_path, cdn_url, "failed", None, "", safe_name, page_url, row_type)
            )
            failed_images.append(base)
            if verbose:
                print(f"❌ {base}.webp")
            if os.path.exists(tmp_png):
                try:
                    os.remove(tmp_png)
                except OSError:
                    pass
            continue

        if convert_to_webp(tmp_png, final_path):
            downloaded_count += 1
            try:
                sz = os.path.getsize(final_path) / 1024.0
            except Exception:
                sz = None
            log_rows.append(
                _log_row(final_path, cdn_url, "success", sz, "", safe_name, page_url, row_type)
            )
            if verbose:
                print(f"✅ {os.path.basename(final_path)}")
        else:
            failed_images.append(base)
            log_rows.append(
                _log_row(final_path, cdn_url, "failed", None, "", safe_name, page_url, row_type)
            )
            if verbose:
                print(f"❌ {base}.webp（轉 WebP 失敗）")

    try:
        _append_csv_log(log_rows, DEFAULT_CSV_PATH)
    except Exception as e:
        if verbose:
            print(f"⚠️ 寫入 CSV 失敗: {e}")

    if verbose:
        print(f"\n📊 Gachabase 下載：成功 {downloaded_count}，失敗 {len(failed_images)}")
    return (downloaded_count, failed_images)

def read_config():
    """讀取配置文件"""
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(script_dir, "link.txt")
        with open(config_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            if len(lines) < 3:
                raise ValueError("link.txt 至少需要三行：URL、ID、NAME")
            ID = lines[1].strip()
            NAME = lines[2].strip()
            return ID, NAME
    except FileNotFoundError:
        print("❌ 找不到 link.txt 文件")
        return None, None
    except Exception as e:
        print(f"❌ 讀取配置文件錯誤: {e}")
        return None, None

def get_character_data(char_id):
    """從 API 獲取角色資料"""
    api_url = f"https://api.hakush.in/hsr/data/en/character/{char_id}.json"
    try:
        response = requests.get(api_url, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"⚠️ 獲取角色資料失敗: {e}")
        return None

def name_to_url_slug(name):
    """將技能名稱轉換為 URL slug 格式"""
    # 移除特殊字符，只保留字母數字和空格
    slug = re.sub(r'[^\w\s-]', '', name.lower())
    # 將空格替換為連字符
    slug = re.sub(r'\s+', '-', slug.strip())
    # 移除連續的連字符
    slug = re.sub(r'-+', '-', slug)
    return slug

# 最小有效圖標大小（字節），避免保存 HTML 錯誤頁
MIN_IMAGE_SIZE = 2000
# Gachabase 小圖示（128px PNG）可能小於 2000 bytes，放寬驗證
MIN_IMAGE_SIZE_GACHABASE = 200

def is_valid_image_content(data, min_length=None):
    """檢查二進制內容是否為有效圖片（WebP 或 PNG 魔術字節 + 大小）"""
    mlen = min_length if min_length is not None else MIN_IMAGE_SIZE
    if not data or len(data) < mlen:
        return False
    # WebP: RIFF....WEBP
    if data[:4] == b'RIFF' and len(data) >= 12 and data[8:12] == b'WEBP':
        return True
    # PNG
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        return True
    # JPEG
    if len(data) >= 3 and data[:3] == b'\xff\xd8\xff':
        return True
    return False

def _load_csv_downloaded_set(csv_path):
    """讀取 CSV，回傳 status 為 success 的 Filename 集合，供檢查重複、跳過已下載。"""
    out = set()
    if not os.path.isfile(csv_path):
        return out
    try:
        with open(csv_path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if (row.get("status") or "").strip().lower() == "success":
                    fn = (row.get("Filename") or "").strip()
                    if fn:
                        out.add(fn)
    except Exception:
        pass
    return out


def _append_csv_log(log_rows, csv_path):
    """將下載記錄追加寫入 CSV（若檔案不存在則寫入表頭）。"""
    if not log_rows:
        return
    file_exists = os.path.isfile(csv_path)
    os.makedirs(os.path.dirname(os.path.abspath(csv_path)) or ".", exist_ok=True)
    with open(csv_path, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
        if not file_exists:
            writer.writeheader()
        writer.writerows(log_rows)


def _log_row(local_path, url, status, file_size_kb, item_id, item_name, char_url, row_type):
    """組出一筆 CSV 記錄（欄位與 materials_download_log 對齊）。"""
    return {
        "Filename": os.path.basename(local_path),
        "local_path": os.path.abspath(local_path),
        "url": url or "",
        "status": status,
        "file_size_kb": f"{file_size_kb:.2f}" if file_size_kb is not None else "",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "item_id": item_id or "",
        "item_name": item_name or "",
        "URL": char_url or "",
        "Type": row_type or "",
        "Featured ID": "",
        "Upload Date": "",
    }


def _collect_item_ids_from_char_data(char_data):
    """從角色 API 的 SkillTrees / Ranks 中收集所有 MaterialList 的 ItemID。"""
    item_ids = set()
    for tree_key, levels in (char_data.get("SkillTrees") or {}).items():
        for lv_key, point in (levels or {}).items():
            for item in (point.get("MaterialList") or []):
                iid = item.get("ItemID")
                if iid is not None:
                    item_ids.add(int(iid))
    return sorted(item_ids)


# 素材圖標 URL：與 #char-material 內一致，使用 itemfigures
def _item_icon_url_candidates(item_id, referer):
    return [
        (f"https://api.hakush.in/hsr/UI/itemfigures/{item_id}.webp", referer),
        (f"https://api.hakush.in/hsr/UI/item/{item_id}.webp", referer),
        (f"https://raw.githubusercontent.com/Mar-7th/StarRailRes/master/icon/item/{item_id}.png", None),
    ]


def fetch_char_material_from_api(char_id, char_data, download_folder, referer, log_rows, verbose=True, csv_downloaded=None):
    """
    當網頁 #char-material 為空（SPA 未渲染）時，改從 API MaterialList 取得 ItemID，
    依 itemfigures URL 下載素材圖標；若 CSV 內已有該 Filename 且檔案存在則跳過。
    """
    csv_downloaded = csv_downloaded or set()
    item_ids = _collect_item_ids_from_char_data(char_data)
    if not item_ids:
        return 0
    char_url = f"https://hsr20.hakush.in/char/{char_id}"
    os.makedirs(download_folder, exist_ok=True)
    count = 0
    for item_id in item_ids:
        # 與 #char-material 內 img 檔名一致：itemfigures/2.webp -> 2.webp
        safe_name = f"{item_id}.webp"
        save_path = os.path.join(download_folder, safe_name)
        if safe_name in csv_downloaded and os.path.exists(save_path) and os.path.getsize(save_path) >= MIN_IMAGE_SIZE:
            count += 1
            continue
        if os.path.exists(save_path) and os.path.getsize(save_path) >= MIN_IMAGE_SIZE:
            try:
                size_kb = os.path.getsize(save_path) / 1024.0
            except Exception:
                size_kb = None
            log_rows.append(_log_row(save_path, "", "success", size_kb, char_id, "", char_url, "char_material"))
            count += 1
            continue
        for url, ref in _item_icon_url_candidates(item_id, referer):
            if download_image(url, save_path, verbose=False, referer=ref):
                try:
                    size_kb = os.path.getsize(save_path) / 1024.0
                except Exception:
                    size_kb = None
                log_rows.append(_log_row(save_path, url, "success", size_kb, char_id, "", char_url, "char_material"))
                count += 1
                if verbose:
                    print(f"✅ [char-material] {safe_name}")
                break
        else:
            log_rows.append(_log_row(save_path, "", "failed", None, char_id, "", char_url, "char_material"))
    return count


def fetch_char_material_images(char_id, download_folder, referer, log_rows, verbose=True, char_data=None, csv_downloaded=None):
    """
    先從目標網站 hsr20.hakush.in/char/{char_id} 取得 div#char-material 內所有圖片（src 為 itemfigures/*.webp）；
    若頁面為 SPA 導致無 #char-material 或無圖片，改從 API MaterialList 用 itemfigures URL 下載。
    若 csv_downloaded 內已有該 Filename 且檔案存在則跳過。
    """
    csv_downloaded = csv_downloaded or set()
    char_url = f"https://hsr20.hakush.in/char/{char_id}"
    count = 0
    if BeautifulSoup is not None:
        try:
            r = requests.get(
                char_url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"},
                timeout=30,
            )
            r.raise_for_status()
        except Exception as e:
            if verbose:
                print(f"⚠️ 無法取得角色頁面 (#char-material): {e}")
        else:
            soup = BeautifulSoup(r.text, "html.parser")
            container = soup.find("div", id="char-material") or soup.find(id="char-material")
            imgs = container.find_all("img") if container else []
            if imgs:
                os.makedirs(download_folder, exist_ok=True)
                for img in imgs:
                    src = (img.get("src") or img.get("data-src") or "").strip()
                    if not src:
                        continue
                    abs_url = urljoin(char_url, src)
                    parsed = urlparse(abs_url)
                    # 與 div 內一致：itemfigures/2.webp -> 2.webp
                    safe_name = os.path.basename(parsed.path) or "material.webp"
                    if not re.search(r"\.(webp|png|jpg|jpeg|gif)$", safe_name, re.I):
                        safe_name += ".webp"
                    save_path = os.path.join(download_folder, safe_name)
                    if safe_name in csv_downloaded and os.path.exists(save_path) and os.path.getsize(save_path) >= MIN_IMAGE_SIZE:
                        count += 1
                        continue
                    ok = download_image(abs_url, save_path, verbose=False, referer=referer)
                    size_kb = os.path.getsize(save_path) / 1024.0 if ok and os.path.exists(save_path) else None
                    log_rows.append(
                        _log_row(save_path, abs_url, "success" if ok else "failed", size_kb, char_id, "", char_url, "char_material")
                    )
                    if ok:
                        count += 1
                        if verbose:
                            print(f"✅ [char-material] {safe_name}")
                return count
            if verbose:
                print("⚠️ 頁面中無 #char-material 或無圖片（可能為 SPA），改從 API MaterialList 下載素材圖")
    if char_data:
        count = fetch_char_material_from_api(
            char_id, char_data, download_folder, referer, log_rows, verbose=verbose, csv_downloaded=csv_downloaded
        )
    elif verbose:
        print("⚠️ 略過素材圖下載（無 char_data 且頁面無 #char-material）")
    return count


def download_image(url, save_path, verbose=True, referer=None, min_bytes=None):
    """下載圖片並保存，僅在內容為有效圖片時才寫入。min_bytes 可覆寫最小檔案大小門檻。"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
        }
        if referer:
            headers['Referer'] = referer
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            return False
        
        content = response.content
        content_type = response.headers.get('content-type', '')
        # 若回傳為 HTML 或內容不是有效圖片，視為失敗
        if 'text/html' in content_type.lower() or not is_valid_image_content(content, min_length=min_bytes):
            return False
        
        # 確保目錄存在
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with open(save_path, 'wb') as f:
            f.write(content)
        return True
    except Exception as e:
        if verbose:
            print(f"    ⚠️ {e}")
        return False

def convert_to_webp(input_path, output_path):
    """轉換圖片為 WebP 格式"""
    try:
        if not os.path.exists(input_path):
            return False
        if os.path.getsize(input_path) == 0:
            os.remove(input_path)
            return False
        
        with Image.open(input_path) as img:
            if img.mode in ('RGBA', 'LA'):
                img.save(output_path, "webp", lossless=True)
            else:
                img.save(output_path, "webp", quality=85)
        
        # 刪除原始檔案
        if input_path != output_path and os.path.exists(input_path):
            os.remove(input_path)
        return True
    except Exception as e:
        print(f"❌ 轉換失敗: {e}")
        if os.path.exists(input_path):
            os.remove(input_path)
        return False

def try_download_with_multiple_urls(urls_and_paths, download_folder, verbose=True, hakush_referer=None):
    """嘗試多個 URL 下載圖片。每項可為 (url, filename) 或 (url, filename, referer)。"""
    for item in urls_and_paths:
        if len(item) == 3:
            url, filename, referer = item
        else:
            url, filename = item
            if "honeyhunterworld" in url:
                referer = "https://starrail.honeyhunterworld.com/"
            elif "hakush" in url and hakush_referer:
                referer = hakush_referer
            else:
                referer = None
        temp_path = os.path.join(download_folder, filename)
        if download_image(url, temp_path, verbose=False, referer=referer):
            return temp_path, url
    return None, None

def build_hhw_skill_url(skill_name, suffix="skill_icon"):
    """構建 Honey Hunter World 技能圖標 URL"""
    slug = name_to_url_slug(skill_name)
    return f"https://starrail.honeyhunterworld.com/img/character/{slug}-{suffix}.webp"

def build_hhw_eidolon_url(eidolon_name):
    """構建 Honey Hunter World Eidolon 圖標 URL"""
    slug = name_to_url_slug(eidolon_name)
    return f"https://starrail.honeyhunterworld.com/img/character/{slug}-eidolon_icon.webp"

def build_hhw_trace_url(trace_name):
    """構建 Honey Hunter World Trace 圖標 URL"""
    slug = name_to_url_slug(trace_name)
    return f"https://starrail.honeyhunterworld.com/img/character/{slug}-trace_icon.webp"

STATIC_API_BASE = "https://vizualabstract.github.io/StarRailStaticAPI"
STATIC_API_ASSETS = f"{STATIC_API_BASE}/assets"

# Hakush.in 技能/行跡圖標前綴（由 Network 複製連結得知：skillicons/ 路徑）
# 範例：https://api.hakush.in/hsr/UI/skillicons/SkillIcon_1501_Ultra.webp
HAKUSH_SKILL_ICON_BASES = [
    "https://api.hakush.in/hsr/UI/skillicons/",
]

def get_hakush_skill_icon_filename(skill_trees, point_key):
    """從 SkillTrees 取得該 Point 的 Icon 檔名，改為 .webp"""
    point_data = skill_trees.get(point_key, {}).get('1', {})
    icon = point_data.get('Icon') or ''
    if icon and icon.endswith('.png'):
        return icon[:-4] + '.webp'
    return icon or None

def build_hakush_skill_urls(char_id, icon_webp_filename):
    """依 Network 看到的檔名 (SkillIcon_1501_xxx.webp) 建出多個候選 URL。
    若前綴含 {id} 會替換為角色 ID；否則直接接上檔名。"""
    if not icon_webp_filename:
        return []
    urls = []
    for base in HAKUSH_SKILL_ICON_BASES:
        prefix = base.format(id=char_id) if "{id}" in base else base
        urls.append(prefix + icon_webp_filename)
    return urls

def fetch_static_api_icons(char_id):
    """從 StarRailStaticAPI 取得該角色的技能/行跡 icon 路徑。若 API 尚無該角色則回傳空 dict。"""
    out = {}
    try:
        r_skills = requests.get(f"{STATIC_API_BASE}/db/en/character_skills.json", timeout=15)
        r_trees = requests.get(f"{STATIC_API_BASE}/db/en/character_skill_trees.json", timeout=15)
        if r_skills.status_code != 200 or r_trees.status_code != 200:
            return out
        skills_data = r_skills.json()
        trees_data = r_trees.json()
        prefix = str(char_id)
        for sid, info in skills_data.items():
            if not sid.startswith(prefix):
                continue
            icon = info.get("icon")
            if icon:
                out[f"skill_{sid}"] = f"{STATIC_API_ASSETS}/{icon}"
        for point_id, info in trees_data.items():
            if not point_id.startswith(prefix):
                continue
            icon = info.get("icon")
            if icon:
                out[f"tree_{point_id}"] = f"{STATIC_API_ASSETS}/{icon}"
        return out
    except Exception:
        return out

def run_download(char_id, char_name, download_folder=None, verbose=True):
    """
    依角色 ID 與名稱下載技能/行跡/星魂圖片，並下載目標頁 #char-material 內所有圖片。
    download_folder 若為 None 則使用統一目錄 DEFAULT_DOWNLOAD_ROOT。
    回傳 (downloaded_count, failed_images_list)，供 GUI 或其它呼叫端使用。
    所有下載記錄會寫入 DEFAULT_CSV_PATH。
    """
    ID, NAME = char_id, char_name
    if download_folder is None:
        download_folder = DEFAULT_DOWNLOAD_ROOT
    os.makedirs(download_folder, exist_ok=True)
    log_rows = []
    char_url = f"https://hsr20.hakush.in/char/{ID}"
    # 以 CSV 為主：已存在且 status=success 的 Filename 不再下載
    csv_downloaded = _load_csv_downloaded_set(DEFAULT_CSV_PATH)
    if verbose:
        print(f"📁 資料夾: {download_folder}")

    char_data = get_character_data(ID)

    if not char_data:
        if verbose:
            print("❌ 無法獲取角色資料，請檢查角色ID")
        return (0, [])

    # 提取技能名稱
    skills = char_data.get('Skills', {})
    skill_trees = char_data.get('SkillTrees', {})
    ranks = char_data.get('Ranks', {})
    
    # 定義 URL 來源
    starrail_res_base = f"https://raw.githubusercontent.com/Mar-7th/StarRailRes/master/icon/skill"
    hakush_rank_base = f"https://api.hakush.in/hsr/UI/rank/_dependencies/textures/{ID}"
    
    # 嘗試從 StarRailStaticAPI 取得 icon（若該角色已存在於 API）
    static_icons = fetch_static_api_icons(ID)
    
    # 構建要下載的圖片列表
    images_to_download = []
    
    # 1. 技能圖標（同時記錄 skill_id 供 StaticAPI 使用）
    basic_atk = None
    basic_atk_id = None
    skill_bp = None
    skill_bp_id = None
    ultimate = None
    ultimate_id = None
    talent = None
    talent_id = None
    technique = None
    technique_id = None
    elation_skill = None
    elation_skill_id = None
    
    for skill_id, skill_info in skills.items():
        skill_type = skill_info.get('Type')
        skill_name = skill_info.get('Name', '')
        
        if skill_type == 'Normal' and not basic_atk and 'Winner Takes All' not in skill_name:
            basic_atk, basic_atk_id = skill_name, skill_id
        elif skill_type == 'BPSkill' and not skill_bp:
            # 取第一個 BPSkill 作為戰技圖標（主戰技，如「Boom! Sparxicle's Poppin'」）
            skill_bp, skill_bp_id = skill_name, skill_id
        elif skill_type == 'Ultra':
            ultimate, ultimate_id = skill_name, skill_id
        elif skill_type is None and 'Certified Banger' in skill_info.get('Desc', ''):
            talent, talent_id = skill_name, skill_id
        elif skill_type == 'Maze' and skill_info.get('Tag') == 'Impair':
            technique, technique_id = skill_name, skill_id
        elif skill_type == 'ElationDamage':
            elation_skill, elation_skill_id = skill_name, skill_id
    
    hakush_referer = f"https://hsr20.hakush.in/char/{ID}"
    
    def _url_list(*pairs):
        """組出 (url, temp_filename) 列表，若有 StaticAPI 則插在最前。"""
        result = []
        for url, temp in pairs:
            if url:
                result.append((url, temp))
        return result
    
    def _prepend_static(result_list, static_key, temp_name):
        if static_key in static_icons:
            result_list.insert(0, (static_icons[static_key], temp_name))
    
    def _prepend_hakush_skill(result_list, point_key, temp_name):
        """依 API SkillTrees 的 Icon 檔名 (SkillIcon_1501_xxx.webp) 插入 Hakush 候選 URL。"""
        icon_webp = get_hakush_skill_icon_filename(skill_trees, point_key)
        if not icon_webp:
            return
        for url in reversed(build_hakush_skill_urls(ID, icon_webp)):
            result_list.insert(0, (url, temp_name, hakush_referer))
    
    # 添加技能圖標（優先 Hakush.in → StaticAPI → HHW → StarRailRes）
    if basic_atk:
        urls = _url_list(
            (build_hhw_skill_url(basic_atk), "temp_basic.webp"),
            (f"{starrail_res_base}/{ID}_basic_atk.png", "temp_basic.png"),
        )
        _prepend_hakush_skill(urls, 'Point01', "temp_basic_hakush.webp")
        _prepend_static(urls, f"skill_{basic_atk_id}", "temp_basic_static.png")
        images_to_download.append((f"{NAME}_base_atk", urls))
    
    if skill_bp:
        urls = _url_list(
            (build_hhw_skill_url(skill_bp), "temp_skill.webp"),
            (f"{starrail_res_base}/{ID}_skill.png", "temp_skill.png"),
        )
        # 戰技圖標：優先使用 hakush 命名 SkillIcon_{char_id}_BP.webp
        urls.insert(0, (f"https://api.hakush.in/hsr/UI/skillicons/SkillIcon_{ID}_BP.webp", "temp_skill_direct.webp", hakush_referer))
        _prepend_hakush_skill(urls, 'Point02', "temp_skill_hakush.webp")
        _prepend_static(urls, f"skill_{skill_bp_id}", "temp_skill_static.png")
        images_to_download.append((f"{NAME}_skill", urls))
    
    if ultimate:
        urls = _url_list(
            (build_hhw_skill_url(ultimate), "temp_ultimate.webp"),
            (f"{starrail_res_base}/{ID}_ultimate.png", "temp_ultimate.png"),
        )
        _prepend_hakush_skill(urls, 'Point03', "temp_ultimate_hakush.webp")
        _prepend_static(urls, f"skill_{ultimate_id}", "temp_ultimate_static.png")
        images_to_download.append((f"{NAME}_ultimate", urls))
    
    if talent:
        urls = _url_list(
            (build_hhw_skill_url(talent), "temp_talent.webp"),
            (f"{starrail_res_base}/{ID}_talent.png", "temp_talent.png"),
        )
        _prepend_hakush_skill(urls, 'Point04', "temp_talent_hakush.webp")
        _prepend_static(urls, f"skill_{talent_id}", "temp_talent_static.png")
        images_to_download.append((f"{NAME}_talent", urls))
    
    if technique:
        urls = _url_list(
            (build_hhw_skill_url(technique), "temp_technique.webp"),
            (f"{starrail_res_base}/{ID}_technique.png", "temp_technique.png"),
        )
        _prepend_hakush_skill(urls, 'Point05', "temp_technique_hakush.webp")
        _prepend_static(urls, f"skill_{technique_id}", "temp_technique_static.png")
        images_to_download.append((f"{NAME}_technique", urls))
    
    if elation_skill:
        urls = _url_list(
            (build_hhw_skill_url(elation_skill), "temp_elation.webp"),
            (f"{starrail_res_base}/{ID}_elation.png", "temp_elation.png"),
        )
        _prepend_hakush_skill(urls, 'Point22', "temp_elation_hakush.webp")
        _prepend_static(urls, f"skill_{elation_skill_id}", "temp_elation_static.png")
        images_to_download.append((f"{NAME}_elation_skill", urls))
    
    # 2. Trace 圖標 (Point06, Point07, Point08)
    trace_points = ['Point06', 'Point07', 'Point08']
    for i, point_key in enumerate(trace_points, 1):
        point_data = skill_trees.get(point_key, {}).get('1', {})
        trace_name = point_data.get('PointName', '')
        point_id = point_data.get('PointID')
        if trace_name:
            urls = _url_list(
                (build_hhw_trace_url(trace_name), f"temp_trace{i}.webp"),
                (f"{starrail_res_base}/{ID}_skilltree{i}.png", f"temp_trace{i}.png"),
            )
            _prepend_hakush_skill(urls, point_key, f"temp_trace{i}_hakush.webp")
            if point_id is not None and f"tree_{point_id}" in static_icons:
                urls.insert(0, (static_icons[f"tree_{point_id}"], f"temp_trace{i}_static.png"))
            images_to_download.append((f"{NAME}_trace{i}", urls))
    
    # 3. Eidolon 圖標（Hakush 路徑為 {ID}_Rank_1.webp～Rank_6.webp，優先使用並帶 Referer）
    for rank_num in ['1', '2', '3', '4', '5', '6']:
        rank_info = ranks.get(rank_num, {})
        rank_name = rank_info.get('Name', '')
        if rank_name:
            hakush_rank_url = f"{hakush_rank_base}/{ID}_Rank_{rank_num}.webp"
            images_to_download.append((f"{NAME}_eidolon{rank_num}", [
                (hakush_rank_url, f"temp_rank{rank_num}.webp", hakush_referer),
                (build_hhw_eidolon_url(rank_name), f"temp_eidolon{rank_num}.webp"),
                (f"{starrail_res_base}/{ID}_rank{rank_num}.png", f"temp_rank{rank_num}.png"),
            ]))
    
    # 顯示將要下載的圖片
    if verbose:
        print(f"\n📝 共找到 {len(images_to_download)} 張圖片需要下載")
        print("\n📥 開始下載圖片...")
        print("-" * 60)

    downloaded_count = 0
    failed_images = []
    
    for output_name, url_list in images_to_download:
        final_filename = f"{output_name}.webp"
        final_path = os.path.join(download_folder, final_filename)
        if final_filename in csv_downloaded and os.path.exists(final_path) and os.path.getsize(final_path) >= MIN_IMAGE_SIZE:
            downloaded_count += 1
            if verbose:
                print(f"⏭️ {final_filename}（CSV 已有，略過）")
            continue
        temp_path, success_url = try_download_with_multiple_urls(
            url_list, download_folder, hakush_referer=hakush_referer
        )

        if temp_path:
            # 轉換為 webp 並重命名
            final_path = os.path.join(download_folder, f"{output_name}.webp")
            
            if temp_path.endswith('.webp'):
                # 直接重命名（但先檢查內容有效性）
                try:
                    with Image.open(temp_path) as img:
                        img.verify()
                    if os.path.exists(final_path):
                        os.remove(final_path)
                    os.rename(temp_path, final_path)
                    if "honeyhunter" in success_url:
                        source = "HHW"
                    elif "vizualabstract" in success_url or "StarRailStaticAPI" in success_url:
                        source = "StaticAPI"
                    elif "hakush" in success_url:
                        source = "Hakush"
                    else:
                        source = "其他"
                    if verbose:
                        print(f"✅ {output_name}.webp ({source})")
                    downloaded_count += 1
                    try:
                        sz = os.path.getsize(final_path) / 1024.0
                    except Exception:
                        sz = None
                    _type = "eidolon" if "eidolon" in output_name else ("trace" if "trace" in output_name else "skill_icon")
                    log_rows.append(_log_row(final_path, success_url, "success", sz, ID, NAME, char_url, _type))
                except Exception:
                    # WebP 無效，嘗試轉換
                    if convert_to_webp(temp_path, final_path):
                        if verbose:
                            print(f"✅ {output_name}.webp (轉換)")
                        downloaded_count += 1
                        try:
                            sz = os.path.getsize(final_path) / 1024.0
                        except Exception:
                            sz = None
                        _type = "eidolon" if "eidolon" in output_name else ("trace" if "trace" in output_name else "skill_icon")
                        log_rows.append(_log_row(final_path, success_url, "success", sz, ID, NAME, char_url, _type))
                    else:
                        print(f"⚠️ {output_name} - 轉換失敗")
                        failed_images.append(output_name)
            else:
                # 需要轉換
                if convert_to_webp(temp_path, final_path):
                    source = "StarRailRes" if "github" in success_url else "其他"
                    if verbose:
                        print(f"✅ {output_name}.webp ({source})")
                    downloaded_count += 1
                    try:
                        sz = os.path.getsize(final_path) / 1024.0
                    except Exception:
                        sz = None
                    _type = "eidolon" if "eidolon" in output_name else ("trace" if "trace" in output_name else "skill_icon")
                    log_rows.append(_log_row(final_path, success_url, "success", sz, ID, NAME, char_url, _type))
                else:
                    if verbose:
                        print(f"⚠️ {output_name} - 轉換失敗")
                    failed_images.append(output_name)
        else:
            if verbose:
                print(f"❌ {output_name} - 找不到圖片")
            failed_images.append(output_name)

    # 下載 #char-material 內所有素材圖（頁面無內容時改從 API MaterialList，itemfigures URL；CSV 已有則略過）
    material_count = fetch_char_material_images(
        ID, download_folder, hakush_referer, log_rows, verbose=verbose, char_data=char_data, csv_downloaded=csv_downloaded
    )
    downloaded_count += material_count
    if verbose and material_count > 0:
        print(f"✅ [char-material] 共下載 {material_count} 張素材圖")
    # 寫入 CSV 記錄
    try:
        _append_csv_log(log_rows, DEFAULT_CSV_PATH)
    except Exception as e:
        if verbose:
            print(f"⚠️ 寫入 CSV 失敗: {e}")

    if verbose:
        print("-" * 60)
        print(f"\n📊 下載統計:")
        print(f"   ✅ 成功: {downloaded_count} 張")
        print(f"   ❌ 失敗: {len(failed_images)} 張")
        if failed_images:
            print(f"\n⚠️ 找不到的圖片:")
            for img in failed_images:
                print(f"   - {img}")
            print("\n💡 提示: 這些圖片可能需要手動下載")
            print(f"   Honey Hunter: https://starrail.honeyhunterworld.com/{NAME.lower()}-character/")
            print(f"   Hakush.in: https://hsr20.hakush.in/char/{ID}")
        print("\n✅ 處理完成！")

    return (downloaded_count, failed_images)


def main():
    print("🚀 開始下載角色圖片...")
    print("=" * 60)
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(script_dir, "link.txt")
        with open(config_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        print(f"❌ 讀取 link.txt 失敗: {e}")
        return
    if len(lines) < 3:
        print("❌ link.txt 至少需要三行：URL、ID、NAME")
        return
    first_line = lines[0].strip()
    ID = lines[1].strip()
    NAME = lines[2].strip()

    if "gachabase.net" in first_line.lower():
        print(f"📋 Gachabase 網址: {first_line}")
        print(f"📋 角色名稱（檔名前綴）: {NAME}")
        print("\n📡 從 Gachabase 頁面解析並下載圖片…")
        run_download_gachabase(first_line, NAME, verbose=True)
        return

    if not ID or not NAME:
        print("❌ 缺少角色 ID 或名稱")
        return
    print(f"📋 角色ID: {ID}")
    print(f"📋 角色名稱: {NAME}")
    print("\n📡 獲取角色資料...")
    run_download(ID, NAME, verbose=True)


if __name__ == "__main__":
    main()
