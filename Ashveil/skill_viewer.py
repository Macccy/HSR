import sys
import json
import os
import requests
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLabel, QComboBox, QTableWidget, QTableWidgetItem, QPushButton,
                            QMessageBox, QTextEdit, QSplitter, QLineEdit, QSizePolicy, QProgressDialog,
                            QTabWidget, QGroupBox, QCheckBox, QProgressBar)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
import re
import time
import csv
import html
from bs4 import BeautifulSoup

GACHABASE_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,zh-TW;q=0.8",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
}

# all_json.csv：行跡小屬性（對應 Atier1～3 / B～ / C～ / D～），Gachabase 只會更新 tier1，tier2/3 可手動填寫後持久化
CSV_TRACE_TIER_FIELDS = ["tier1", "tier2", "tier3"]

# 整合下載圖片與 WordPress 上傳
try:
    from download_img import run_download as download_img_run_download
    from download_img import run_download_gachabase as download_img_run_gachabase
    from download_img import DEFAULT_CSV_PATH as IMG_CSV_PATH, DEFAULT_DOWNLOAD_ROOT as IMG_FOLDER
except ImportError:
    download_img_run_download = None
    download_img_run_gachabase = None
    IMG_CSV_PATH = ""
    IMG_FOLDER = ""


class DownloadImagesWorker(QThread):
    """在背景執行 run_download，避免凍結 GUI。"""
    finished = pyqtSignal(int, list)  # (downloaded_count, failed_images)

    def __init__(self, char_id, char_name, page_url=""):
        super().__init__()
        self.char_id = char_id
        self.char_name = char_name
        self.page_url = (page_url or "").strip()

    def run(self):
        try:
            if self.page_url and "gachabase.net" in self.page_url.lower():
                if download_img_run_gachabase is None:
                    self.finished.emit(0, ["找不到 run_download_gachabase"])
                    return
                count, failed = download_img_run_gachabase(
                    self.page_url,
                    self.char_name,
                    download_folder=None,
                    verbose=False,
                )
                self.finished.emit(count, failed)
                return
            if download_img_run_download is None:
                self.finished.emit(0, [])
                return
            count, failed = download_img_run_download(
                self.char_id, self.char_name,
                download_folder=None,
                verbose=False
            )
            self.finished.emit(count, failed)
        except Exception as e:
            self.finished.emit(0, [str(e)])


class WpUploadWorker(QThread):
    """背景執行 WordPress JWT 上傳：掃描 img、讀 CSV、跳過已有 Featured ID、上傳並寫回 CSV。"""
    log_msg = pyqtSignal(str)  # 單行日誌
    progress = pyqtSignal(int, int, int, int, int)  # total, current, uploaded, skipped, failed
    finished = pyqtSignal()

    def __init__(self, wp_url, username, password, csv_path, materials_dir):
        super().__init__()
        self.wp_url = (wp_url or "").strip().rstrip("/")
        self.username = (username or "").strip()
        self.password = password or ""
        self.csv_path = (csv_path or "").strip()
        self.materials_dir = (materials_dir or "").strip()
        self._abort = False

    def abort(self):
        self._abort = True

    def run(self):
        from pathlib import Path
        from datetime import datetime

        def log(msg, level="INFO"):
            ts = datetime.now().strftime("%H:%M:%S")
            prefix = {"INFO": "ℹ️", "OK": "✓", "WARN": "⚠️", "ERR": "❌", "SKIP": "⏭️"}.get(level, "ℹ️")
            self.log_msg.emit(f"[{ts}] {prefix} {msg}")

        session = requests.Session()
        jwt_token = None

        # 1) JWT 登入
        if not self.wp_url or not self.username or not self.password:
            log("請填好 WordPress URL / Username / Password", "ERR")
            self.finished.emit()
            return
        token_url = f"{self.wp_url}/wp-json/jwt-auth/v1/token"
        try:
            log("JWT 登入中...")
            resp = session.post(token_url, data={"username": self.username, "password": self.password}, timeout=20)
            if resp.status_code != 200:
                log(f"JWT 登入失敗 {resp.status_code}: {resp.text[:200]}", "ERR")
                self.finished.emit()
                return
            data = resp.json()
            jwt_token = data.get("token")
            if not jwt_token:
                log("JWT 回應缺少 token", "ERR")
                self.finished.emit()
                return
            log("JWT 登入成功，已取得 token", "OK")
        except Exception as e:
            log(f"JWT 登入錯誤: {e}", "ERR")
            self.finished.emit()
            return

        # 2) 掃描資料夾（.png 與 .webp）
        d = Path(self.materials_dir)
        if not d.exists():
            log(f"素材資料夾不存在: {d}", "ERR")
            self.finished.emit()
            return
        files = sorted(list(d.glob("*.png")) + list(d.glob("*.webp")), key=lambda p: p.name.lower())
        total = len(files)
        log(f"找到圖片：{total} 個 (.png / .webp)")
        if total == 0:
            log("資料夾內沒有 .png 或 .webp", "WARN")
            self.finished.emit()
            return

        # 3) 讀取 CSV
        csv_file = Path(self.csv_path)
        if not csv_file.exists():
            log(f"CSV 不存在: {csv_file}", "ERR")
            self.finished.emit()
            return
        with open(csv_file, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            fieldnames = list(reader.fieldnames or [])
            rows = list(reader)
        for c in ["Featured ID", "Upload Date", "Filename"]:
            if c not in fieldnames:
                fieldnames.append(c)
        featured_by_fn = {}
        idx_by_fn = {}
        for i, r in enumerate(rows):
            fn = (r.get("Filename") or "").strip()
            if not fn:
                continue
            idx_by_fn[fn] = i
            fid = (r.get("Featured ID") or "").strip()
            if fid:
                featured_by_fn[fn] = fid

        # 4) 上傳迴圈
        done_up, done_skip, done_fail = 0, 0, 0
        media_url = f"{self.wp_url}/wp-json/wp/v2/media"
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for i, fp in enumerate(files, start=1):
            if self._abort:
                log("已停止", "WARN")
                break
            filename = fp.name
            if filename in featured_by_fn:
                done_skip += 1
                self.progress.emit(total, i, done_up, done_skip, done_fail)
                log(f"[{i}/{total}] 跳過: {filename} (已有 Featured ID)", "SKIP")
                time.sleep(0.1)
                continue
            # 上傳
            mime = "image/webp" if fp.suffix.lower() == ".webp" else "image/png"
            try:
                with open(fp, "rb") as f:
                    files_payload = {"file": (filename, f, mime)}
                    resp = session.post(media_url, headers={"Authorization": f"Bearer {jwt_token}"}, files=files_payload, timeout=60)
                if resp.status_code == 201:
                    media_id = resp.json().get("id")
                    done_up += 1
                    self.progress.emit(total, i, done_up, done_skip, done_fail)
                    log(f"[{i}/{total}] 成功: {filename} (Featured ID: {media_id})", "OK")
                    # 寫回 CSV
                    if filename in idx_by_fn:
                        rows[idx_by_fn[filename]]["Featured ID"] = str(media_id)
                        rows[idx_by_fn[filename]]["Upload Date"] = now_str
                    else:
                        new_row = {k: "" for k in fieldnames}
                        new_row["Filename"] = filename
                        new_row["Featured ID"] = str(media_id)
                        new_row["Upload Date"] = now_str
                        rows.append(new_row)
                    with open(csv_file, "w", encoding="utf-8-sig", newline="") as f:
                        w = csv.DictWriter(f, fieldnames=fieldnames)
                        w.writeheader()
                        for r in rows:
                            w.writerow({k: r.get(k, "") for k in fieldnames})
                else:
                    done_fail += 1
                    self.progress.emit(total, i, done_up, done_skip, done_fail)
                    try:
                        j = resp.json()
                        msg = j.get("message") or j.get("code") or resp.text
                    except Exception:
                        msg = resp.text
                    log(f"上傳失敗 {filename} -> HTTP {resp.status_code} - {str(msg)[:200]}", "ERR")
            except Exception as e:
                done_fail += 1
                self.progress.emit(total, i, done_up, done_skip, done_fail)
                log(f"上傳例外 {filename}: {e}", "ERR")
            time.sleep(0.25)

        log("=" * 50)
        log(f"上傳完成｜已上傳 {done_up}｜已跳過 {done_skip}｜失敗 {done_fail}")
        log("=" * 50)
        self.finished.emit()


class SkillViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("崩壞：星穹鐵道 技能查看器")
        self.setMinimumSize(1200, 800)
        
        # 主佈局
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        self.setCentralWidget(main_widget)

        # URL 輸入區（單獨一行）
        url_layout = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("請輸入角色網址")
        # 啟動時預設 URL：優先 link.txt 第一行（專案設定），否則 last_url.txt（上次操作）
        _script_dir = os.path.dirname(os.path.abspath(__file__))
        _default_url = ""
        _link_path = os.path.join(_script_dir, "link.txt")
        if os.path.exists(_link_path):
            try:
                with open(_link_path, "r", encoding="utf-8") as f:
                    _first = f.readline().strip()
                    if _first:
                        _default_url = _first
            except Exception as e:
                print(f"讀取 link.txt 失敗: {e}")
        if not _default_url:
            _last_url_path = os.path.join(_script_dir, "last_url.txt")
            if os.path.exists(_last_url_path):
                try:
                    with open(_last_url_path, "r", encoding="utf-8") as f:
                        _default_url = f.read().strip()
                except Exception as e:
                    print(f"讀取 last_url.txt 失敗: {e}")
        if _default_url:
            self.url_input.setText(_default_url)
        self.load_button = QPushButton('載入角色資料')
        self.load_button.clicked.connect(self.load_character_stats)
        self.download_img_button = QPushButton('下載角色圖片')
        self.download_img_button.clicked.connect(self.on_download_images)
        url_layout.addWidget(QLabel('URL:'))
        url_layout.addWidget(self.url_input)
        url_layout.addWidget(self.load_button)
        url_layout.addWidget(self.download_img_button)
        main_layout.addLayout(url_layout)

        # 分頁：Tab1 提取角色數據，Tab2 角色圖片與上傳
        self.tab_widget = QTabWidget()

        # ========== Tab1：提取角色數據 ==========
        tab1_widget = QWidget()
        content_layout = QHBoxLayout(tab1_widget)
        # 左側：技能顯示、JSON 預覽
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # 技能選擇與等級選擇（原本在 main_layout，現在移到 left_layout 最上方）
        control_layout = QHBoxLayout()
        self.skill_combo = QComboBox()
        self.skill_combo.addItems(["Basic ATK", "Skill", "Ultimate", "Talent", "Technique", "Elation Skill", "Adesc", "Bdesc", "Cdesc", "Ddesc"])
        self.skill_combo.currentTextChanged.connect(self.update_skill_display)
        control_layout.addWidget(QLabel("選擇技能："))
        control_layout.addWidget(self.skill_combo)
        self.level_combo = QComboBox()
        self.level_combo.addItems([str(i) for i in range(1, 16)])
        self.level_combo.currentTextChanged.connect(self.update_skill_display)
        control_layout.addWidget(QLabel("選擇等級："))
        control_layout.addWidget(self.level_combo)
        export_button = QPushButton("導出數據")
        export_button.clicked.connect(self.export_data)
        control_layout.addWidget(export_button)
        left_layout.addLayout(control_layout)

        # 技能顯示
        self.skill_info = QLabel()
        self.skill_info.setWordWrap(True)
        self.skill_info.setStyleSheet("QLabel { padding: 10px; background-color: #f0f0f0; border-radius: 5px; }")
        left_layout.addWidget(self.skill_info)
        self.attribute_table = QTableWidget()
        self.attribute_table.setColumnCount(2)
        self.attribute_table.setHorizontalHeaderLabels(["屬性", "數值"])
        self.attribute_table.horizontalHeader().setStretchLastSection(True)
        left_layout.addWidget(self.attribute_table)
        # 屬性數值以整段文字顯示，與下方描述區一樣可整段選取複製（含 <b><em> HTML）
        self.attribute_values_text = QTextEdit()
        self.attribute_values_text.setReadOnly(True)
        self.attribute_values_text.setStyleSheet("QTextEdit { background-color: #f0f0f0; border: 2px solid #000; font-size: 14px; }")
        self.attribute_values_text.setPlaceholderText("選擇技能後，若有屬性數值會顯示於此，可整段選取複製。")
        self.attribute_values_text.hide()
        left_layout.addWidget(self.attribute_values_text)
        # 黑框：技能效果區，顯示 <span id="aX"> 替換後的描述
        self.silder_preview = QTextEdit()
        self.silder_preview.setReadOnly(True)
        self.silder_preview.setStyleSheet("QTextEdit { background-color: #f0f0f0; border: 2px solid #000; font-size: 14px; }")
        left_layout.addWidget(self.silder_preview)
        left_layout.addWidget(QLabel("JSON 預覽："))
        self.json_preview = QTextEdit()
        self.json_preview.setReadOnly(False)
        self.json_preview.setStyleSheet("QTextEdit { font-family: monospace; }")
        left_layout.addWidget(self.json_preview)
        content_layout.addWidget(left_widget, 2)  # 左側收窄

        # 右側：角色屬性顯示（灰框區）
        self.stats_display = QTextEdit()
        self.stats_display.setReadOnly(False)
        self.stats_display.setStyleSheet("QTextEdit { background-color: #f8f8f8; border: 1px solid rgb(139, 129, 129); }")
        content_layout.addWidget(self.stats_display, 3)  # 右側寬敞

        self.tab_widget.addTab(tab1_widget, "提取角色數據")

        # ========== Tab2：角色圖片與上傳 ==========
        tab2_widget = QWidget()
        tab2_layout = QVBoxLayout(tab2_widget)
        tab2_layout.addWidget(QLabel("角色圖片會下載到統一 img 資料夾（上方 URL 載入後可按「下載角色圖片」）；下方可將該資料夾與 CSV 內的圖片上傳至 WordPress。"))
        # WordPress 設定
        wp_group = QGroupBox("WordPress 設定（JWT）")
        wp_layout = QVBoxLayout(wp_group)
        wp_row1 = QHBoxLayout()
        wp_row1.addWidget(QLabel("WordPress URL:"))
        self.wp_url_edit = QLineEdit()
        self.wp_url_edit.setPlaceholderText("https://yoursite.com")
        self.wp_url_edit.setText("https://arknightsendfield.gg")
        wp_row1.addWidget(self.wp_url_edit)
        wp_layout.addLayout(wp_row1)
        wp_row2 = QHBoxLayout()
        wp_row2.addWidget(QLabel("Username:"))
        self.wp_username_edit = QLineEdit()
        wp_row2.addWidget(self.wp_username_edit)
        wp_layout.addLayout(wp_row2)
        wp_row3 = QHBoxLayout()
        wp_row3.addWidget(QLabel("Password:"))
        self.wp_password_edit = QLineEdit()
        self.wp_password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        wp_row3.addWidget(self.wp_password_edit)
        self.wp_show_pw = QCheckBox("顯示密碼")
        self.wp_show_pw.stateChanged.connect(lambda s: self.wp_password_edit.setEchoMode(QLineEdit.EchoMode.Normal if s else QLineEdit.EchoMode.Password))
        wp_row3.addWidget(self.wp_show_pw)
        wp_layout.addLayout(wp_row3)
        wp_btn_layout = QHBoxLayout()
        wp_save_btn = QPushButton("保存設定")
        wp_save_btn.clicked.connect(self._wp_save_config)
        wp_test_btn = QPushButton("測試連接")
        wp_test_btn.clicked.connect(self._wp_test_connection)
        wp_btn_layout.addWidget(wp_save_btn)
        wp_btn_layout.addWidget(wp_test_btn)
        wp_layout.addLayout(wp_btn_layout)
        tab2_layout.addWidget(wp_group)
        # 路徑
        path_group = QGroupBox("路徑")
        path_layout = QVBoxLayout(path_group)
        path_layout.addWidget(QLabel("素材資料夾（img）:"))
        self.wp_materials_dir_edit = QLineEdit()
        self.wp_materials_dir_edit.setText(IMG_FOLDER if IMG_FOLDER else "")
        path_layout.addWidget(self.wp_materials_dir_edit)
        path_layout.addWidget(QLabel("materials_download_log.csv:"))
        self.wp_csv_edit = QLineEdit()
        self.wp_csv_edit.setText(IMG_CSV_PATH if IMG_CSV_PATH else "")
        path_layout.addWidget(self.wp_csv_edit)
        tab2_layout.addWidget(path_group)
        # 狀態與進度
        status_group = QGroupBox("狀態")
        status_layout = QVBoxLayout(status_group)
        self.wp_lbl_total = QLabel("總檔案: 0")
        self.wp_lbl_up = QLabel("已上傳: 0")
        self.wp_lbl_skip = QLabel("已跳過: 0")
        self.wp_lbl_fail = QLabel("失敗: 0")
        status_layout.addWidget(self.wp_lbl_total)
        status_layout.addWidget(self.wp_lbl_up)
        status_layout.addWidget(self.wp_lbl_skip)
        status_layout.addWidget(self.wp_lbl_fail)
        self.wp_progress = QProgressBar()
        self.wp_progress.setMaximum(100)
        status_layout.addWidget(self.wp_progress)
        wp_control = QHBoxLayout()
        self.wp_start_btn = QPushButton("開始上傳")
        self.wp_start_btn.clicked.connect(self._wp_start_upload)
        self.wp_stop_btn = QPushButton("停止")
        self.wp_stop_btn.clicked.connect(self._wp_stop_upload)
        self.wp_stop_btn.setEnabled(False)
        wp_control.addWidget(self.wp_start_btn)
        wp_control.addWidget(self.wp_stop_btn)
        status_layout.addLayout(wp_control)
        tab2_layout.addWidget(status_group)
        # 日誌
        tab2_layout.addWidget(QLabel("日誌:"))
        self.wp_log_text = QTextEdit()
        self.wp_log_text.setReadOnly(True)
        tab2_layout.addWidget(self.wp_log_text)
        self.tab_widget.addTab(tab2_widget, "角色圖片與上傳")

        main_layout.addWidget(self.tab_widget)

        # 初始化數據（供下載圖片使用：載入後會更新）
        self.skill_data = {}
        self.silder_text_map = {}  # 存放已替換 <span id="aX"> 的描述
        self.current_char_id = None
        self.current_char_name = None
        self._download_worker = None
        self._download_progress = None
        # WordPress 上傳
        self._wp_upload_worker = None
        self._wp_config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wp_uploader_config.txt")
        self._wp_load_config()
        self.update_skill_display()
        self.update_json_preview()
    
    # ==================== Gachabase 解析方法 ====================

    def _fetch_gachabase(self, url):
        resp = requests.get(url, headers=GACHABASE_HEADERS, timeout=30)
        resp.raise_for_status()
        return resp.text

    def _parse_gachabase_stats(self, page_text):
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

    def _parse_gachabase_eidolons(self, page_text):
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
            if low in (
                "materials calculator",
                "materials required",
                "level calculator",
            ):
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
            block = [l.strip() for l in section[start_i + 1:end_i] if l.strip()]
            block = [l for l in block if l.lower() != "effects"]
            name = block[0] if block else ""
            desc = " ".join(block[1:]) if len(block) > 1 else ""
            desc = re.sub(r"\s+", " ", desc).strip()
            eidolons[num] = {"name": name, "desc": desc}
        for num in range(1, 7):
            if num not in eidolons:
                eidolons[num] = {"name": "", "desc": ""}
        return eidolons

    def _parse_gachabase_trace_tiers(self, page_text):
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
        boost_pattern = r"((?:HP|ATK|DEF|SPD|CRIT Rate|CRIT DMG|Elation|Effect Hit Rate|Effect RES|Break Effect|Energy Regeneration Rate)\s+Boost)\s*\n\s*(.+?)(?=Breakdown|$)"
        for m in re.finditer(boost_pattern, section, re.IGNORECASE | re.DOTALL):
            label = m.group(1).strip().replace(" Boost", "")
            value_text = m.group(2).strip()
            v = re.search(r"increases?\s+by\s+([\d.]+%?)", value_text, re.I)
            if v:
                tiers.append(f"{label} + {v.group(1)}")
        return tiers

    def _format_gachabase_trace_stat_line(self, block_text):
        """
        解析單一 trace-stat-* 區塊純文字（Gachabase），產出與舊版 Dtier 相近的字串。
        例：ATK + 10%、Lightning DMG + 14%。
        """
        if not block_text:
            return ""
        m = re.search(
            r"DMG Boost:\s*(\w+)\s+.*?increases\s+by\s+([\d.]+%)",
            block_text,
            re.I | re.DOTALL,
        )
        if m:
            return f"{m.group(1)} DMG + {m.group(2)}"
        m = re.search(
            r"(HP|ATK|DEF|SPD|CRIT DMG|CRIT Rate|Elation|Effect Hit Rate|Effect RES|"
            r"Break Effect|Energy Regeneration Rate)\s+Boost\s+.*?increases\s+by\s+([\d.]+%)",
            block_text,
            re.I | re.DOTALL,
        )
        if m:
            return f"{m.group(1)} + {m.group(2)}"
        return ""

    def _parse_gachabase_trace_stat_boosts(self, soup):
        """
        自 section#traces 內的 trace-stat-{id} 小節點取得加成敘述，依 id 數字排序。
        通常第 1～3 個對應行跡樹 A/B/C 的第一個小屬性格（Atier1 / Btier1 / Ctier1）。
        """
        root = soup.find("section", id="traces")
        if not root:
            return []
        secs = root.find_all("section", id=re.compile(r"^trace-stat-\d+$"))

        def _sid(tag):
            m = re.search(r"trace-stat-(\d+)$", tag.get("id") or "")
            return int(m.group(1)) if m else 0

        secs = sorted(secs, key=_sid)
        out = []
        for sec in secs:
            tx = sec.get_text("\n", strip=True)
            line = self._format_gachabase_trace_stat_line(tx)
            if line:
                out.append(line)
        return out

    def _parse_gachabase_story_overview(self, soup):
        """
        角色簡介（對應 Hakush 的 overview1）：Gachabase 在 section#story 的 Description 下方。
        回傳含 <br> 的 HTML 片段；若無則空字串。
        """
        sec = soup.find("section", id="story")
        if not sec:
            return ""
        tx = sec.get_text("\n", strip=True)
        if "Description" not in tx:
            return ""
        rest = tx.split("Description", 1)[1].strip()
        for marker in (
            "\nDetailed Version",
            "\nVoicelines",
            "\nTrial",
            "\nPromotion",
            "\nAvailability",
        ):
            if marker in rest:
                rest = rest.split(marker)[0].strip()
        rest = re.sub(r"^Story\s*\n?", "", rest, count=1).strip()
        if not rest:
            return ""
        return rest.replace("\n", "<br>")

    def _escape_stats_export_value(self, s):
        """供 format_stats 包進雙引號欄位時跳脫。"""
        if not s:
            return ""
        return s.replace("\\", "\\\\").replace('"', '\\"')

    def _merge_trace_tiers_supplement(self, script_dir):
        """
        合併選用檔 trace_tiers_supplement.json 到 Adesc/Bdesc/Cdesc/Ddesc 的 attrs（各 3 格）。

        Gachabase 靜態頁通常只有每條行跡樹 1 個 trace-stat 區塊 → 只夠填 Atier1/Btier1/Ctier1。
        Atier2/3 等需對照遊戲內行跡小節點或 HH 等來源，手動寫入 JSON；僅「非空字串」會覆寫對應格
        （第一格可留空以保留 Gachabase 已填入的 tier1）。

        範例 trace_tiers_supplement.json：
        {
          "Adesc": ["", "HP + 4.0%", "DEF + 27.0%"],
          "Bdesc": ["", "ATK + 4.0%", "SPD + 2.0"],
          "Cdesc": ["", "CRIT DMG + 6.5%", ""],
          "Ddesc": ["", "", ""]
        }
        """
        path = os.path.join(script_dir, "trace_tiers_supplement.json")
        if not os.path.isfile(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                sup = json.load(f)
        except Exception as e:
            print(f"讀取 trace_tiers_supplement.json 失敗: {e}")
            return
        if not isinstance(sup, dict):
            return
        for key in ("Adesc", "Bdesc", "Cdesc", "Ddesc"):
            if key not in sup or key not in self.skill_data:
                continue
            extra = sup[key]
            if not isinstance(extra, list):
                continue
            skill = self.skill_data[key]
            cur = skill.get("attrs")
            if not isinstance(cur, list):
                cur = []
            cur = (list(cur) + ["", "", ""])[:3]
            for i in range(min(3, len(extra))):
                v = extra[i]
                if v is None:
                    continue
                v = str(v).strip()
                if v:
                    cur[i] = v
            skill["attrs"] = cur

    def _load_from_gachabase(self, url, export_after=False):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        match = re.search(r"/characters/(\d+)", url)
        if not match:
            QMessageBox.warning(self, "錯誤", "無法從 URL 提取角色 ID")
            return
        char_id = match.group(1)
        char_name = ""
        link_path = os.path.join(script_dir, "link.txt")
        if os.path.exists(link_path):
            try:
                with open(link_path, "r", encoding="utf-8") as f:
                    ll = f.readlines()
                    if len(ll) >= 3:
                        char_name = ll[2].strip()
                    if len(ll) >= 2 and not char_id:
                        char_id = ll[1].strip()
            except Exception:
                pass

        progress = QProgressDialog("正在載入角色資料…", None, 0, 100, self)
        progress.setWindowTitle("進度")
        progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        progress.show()

        data = {}
        trace_tiers_all = []
        minor_trace_boosts = []

        # ---------- Step 1: 從 Gachabase 抓取 stats / eidolons ----------
        progress.setLabelText("從 Gachabase 獲取角色數值…")
        progress.setValue(5)
        try:
            raw_html = self._fetch_gachabase(url)
            soup = BeautifulSoup(raw_html, "html.parser")
            page_text = soup.get_text(separator="\n")
            if not char_name:
                h1 = soup.find("h1")
                if h1:
                    char_name = h1.get_text(strip=True)
            stats = self._parse_gachabase_stats(page_text)
            data["1"] = str(stats.get("hp", ""))
            data["2"] = str(stats.get("atk", ""))
            data["3"] = str(stats.get("def", ""))
            data["4"] = str(stats.get("spd", ""))
            data["5"] = str(stats.get("taunt", ""))
            data["6"] = str(stats.get("energy_cost", ""))
            ov = self._parse_gachabase_story_overview(soup)
            data["overview1"] = self._escape_stats_export_value(ov)
            eidolons = self._parse_gachabase_eidolons(page_text)
            for i in range(1, 7):
                eid = eidolons.get(i, {})
                data[f"Eidolons{i}name"] = eid.get("name", "")
                data[f"Eidolons{i}desc"] = eid.get("desc", "")
            minor_trace_boosts = self._parse_gachabase_trace_stat_boosts(soup)
            if minor_trace_boosts:
                trace_tiers_all = minor_trace_boosts[3:]
            else:
                trace_tiers_all = self._parse_gachabase_trace_tiers(page_text)
        except Exception as e:
            print(f"Gachabase 獲取失敗: {e}")
            import traceback; traceback.print_exc()
            for k in ["1", "2", "3", "4", "5", "6", "overview1"]:
                data.setdefault(k, "")
            for i in range(1, 7):
                data.setdefault(f"Eidolons{i}name", "")
                data.setdefault(f"Eidolons{i}desc", "")
        progress.setValue(40)

        # ---------- Step 2: 讀取本地 all_json.csv ----------
        progress.setLabelText("讀取本地 all_json.csv…")
        csv_path = os.path.join(script_dir, "all_json.csv")
        if os.path.exists(csv_path):
            self.skill_data = self.read_skills_from_csv(csv_path)
            for key, skill in self.skill_data.items():
                skill.setdefault("skill_attrs", [])
                skill.setdefault("attrs", [])
                skill.setdefault("htmls", skill.get("descs", []))
        else:
            QMessageBox.warning(self, "警告", "找不到 all_json.csv，技能資料將為空")
            self.skill_data = {}
        progress.setValue(60)

        # ---------- Step 3: 填入 trace 名稱 / 描述 ----------
        for prefix, key in [("A", "Adesc"), ("B", "Bdesc"), ("C", "Cdesc")]:
            if key in self.skill_data:
                data[f"{prefix}name"] = self.skill_data[key].get("name", "")
                descs = self.skill_data[key].get("descs", [])
                data[f"{prefix}desc"] = descs[0] if descs else ""
            else:
                data[f"{prefix}name"] = ""
                data[f"{prefix}desc"] = ""

        # Gachabase：trace-stat-* → A/B/C 的 tier1；tier2/3 保留 CSV（all_json.csv 的 tier2/tier3 欄）
        if minor_trace_boosts:
            abc_keys = ["Adesc", "Bdesc", "Cdesc"]
            for idx, key in enumerate(abc_keys):
                if key not in self.skill_data:
                    continue
                prev = self.skill_data[key].get("attrs")
                if not isinstance(prev, list):
                    prev = ["", "", ""]
                prev = (list(prev) + ["", "", ""])[:3]
                if idx < len(minor_trace_boosts):
                    prev[0] = minor_trace_boosts[idx]
                self.skill_data[key]["attrs"] = prev

        # Ddesc：Gachabase 溢出的小屬性與 CSV 合併（避免無溢出時清空已手填的 Dtier）
        prev_d = ["", "", ""]
        if "Ddesc" in self.skill_data:
            pd = self.skill_data["Ddesc"].get("attrs")
            if isinstance(pd, list):
                prev_d = (pd + ["", "", ""])[:3]
        merged_d = ["", "", ""]
        for i in range(3):
            tv = trace_tiers_all[i] if i < len(trace_tiers_all) else ""
            tv = (tv or "").strip()
            pv = prev_d[i] if i < len(prev_d) else ""
            merged_d[i] = tv if tv else pv
        if "Ddesc" not in self.skill_data:
            self.skill_data["Ddesc"] = {
                "name": "Extra Attributes",
                "title": "ASCEND CALCULATOR D",
                "descs": [""],
                "htmls": [""],
                "attrs": merged_d,
                "skill_attrs": [],
            }
        else:
            self.skill_data["Ddesc"]["attrs"] = merged_d

        # 補齊 Atier2/3 等：Gachabase 網頁通常沒有足夠區塊，由 trace_tiers_supplement.json 手動補
        self._merge_trace_tiers_supplement(script_dir)

        progress.setValue(70)

        # ---------- Step 4: 建立 silder_raw / 更新 UI ----------
        self.current_char_id = char_id
        self.current_char_name = char_name or f"char_{char_id}"
        self.silder_raw = {}
        for stype, skill in self.skill_data.items():
            if stype not in ("Adesc", "Bdesc", "Cdesc", "Ddesc"):
                descs = skill.get("descs", [])
                if descs:
                    self.silder_raw[stype] = descs
        self.silder_text_map = {}
        self.update_skill_display()
        self.update_json_preview()
        self.stats_display.setText(self.format_stats(data))

        # 自動寫出 CSV 和 slider txt（與 hakush 流程一致）
        self.write_skills_to_csv(self.skill_data, csv_path)
        silder_path = os.path.join(script_dir, "all_skill_silder.txt")
        with open(silder_path, "w", encoding="utf-8") as f:
            f.write(self.get_all_skill_silder_html())

        progress.setValue(100)
        progress.close()

        if export_after:
            self._do_export()

    # ==================== End Gachabase ====================

    def update_skill_display(self):
        skill_name = self.skill_combo.currentText()
        
        # 處理 Ascend Calculator 選項
        if skill_name in ['Adesc', 'Bdesc', 'Cdesc', 'Ddesc']:
            skill = self.skill_data.get(skill_name, {})
            descs = skill.get('descs', [])
            attrs = skill.get('attrs', [])
            if descs:
                html_desc = descs[0]
                self.silder_preview.setPlainText(f"{skill_name}\n\n{html_desc}\n\n")
                # 更新技能信息
                info_text = f"""
                <h2>{skill_name}</h2>
                <h3>{skill.get('name', '')}</h3>
                <p><b>類型：</b>{skill.get('title', '')}</p>
                <p><b>描述：</b>{html_desc}</p>
                """
                self.skill_info.setText(info_text)
                # 顯示屬性表格（Adesc/Bdesc 等）
                self.attribute_values_text.hide()
                self.attribute_table.show()
                self.attribute_table.setRowCount(len(attrs))
                for i, attr in enumerate(attrs):
                    self.attribute_table.setItem(i, 0, QTableWidgetItem("屬性"))
                    self.attribute_table.setItem(i, 1, QTableWidgetItem(attr))
            else:
                self.silder_preview.setPlainText("")
                self.skill_info.setText("")
            return

        # 原有的技能顯示邏輯
        level = int(self.level_combo.currentText())
        if skill_name in self.skill_data:
            skill = self.skill_data[skill_name]
            descs = skill.get('descs', [])
            html_desc = descs[level-1] if level-1 < len(descs) else ''
            # 與 all_skill_silder.txt 一致：全域 a1,a2.. 編號，內容與 txt 相同
            span_desc = self._get_silder_content_for_skill(skill_name)
            self.silder_preview.setPlainText(span_desc if span_desc else html_desc)
            # 更新技能信息
            info_text = f"""
            <h2>{skill_name}</h2>
            <h3>{skill.get('name', '')}</h3>
            <p><b>類型：</b>{skill.get('title', '')}</p>
            <p><b>描述：</b>{html_desc}</p>
            """
            self.skill_info.setText(info_text)
            # 顯示該技能的屬性數值：用文字區塊顯示（與下方描述區一樣），整段選取即可複製含 <b><em> 的 HTML
            skill_attrs = skill.get('skill_attrs', [])
            if skill_attrs:
                lines = [f"<b><em>{attr_text}</em></b>" for attr_text in skill_attrs]
                self.attribute_values_text.setPlainText("\n".join(lines))
                self.attribute_table.hide()
                self.attribute_values_text.show()
            else:
                self.attribute_table.setRowCount(0)
                self.attribute_values_text.hide()
                self.attribute_table.show()
    
    def update_json_preview(self):
        if not self.skill_data:
            self.json_preview.setText("")
            return

        # 收集所有技能的 aX 數值
        ax_values = {}  # {aX: [lv1_value, lv2_value, ...]}
        skill_order = ["Basic ATK", "Skill", "Ultimate", "Talent", "Elation Skill"]
        
        # 先找出所有 aX 的位置
        all_ax_positions = []
        for skill_name in skill_order:
            if skill_name not in self.skill_data:
                continue
            descs = self.skill_data[skill_name].get('descs', [])
            if not descs:
                continue
            # 使用等級1的描述來找出所有 aX
            html_desc = descs[0]
            colored_pattern = r'<span style="color: #f29e38ff;">(?:<strong>)?([\d\.]+%?)(?:</strong>)?</span>'
            colored_values = re.findall(colored_pattern, html_desc)
            all_ax_positions.extend([(skill_name, i) for i in range(len(colored_values))])

        # 為每個位置分配 aX
        ax_map = {}  # (skill_name, idx_in_skill) -> aX
        for idx, (skill_name, i) in enumerate(all_ax_positions):
            ax_map[(skill_name, i)] = f'a{idx+1}'
            ax_values[f'a{idx+1}'] = []

        # 收集每個 aX 的所有等級數值
        for skill_name in skill_order:
            if skill_name not in self.skill_data:
                continue
            descs = self.skill_data[skill_name].get('descs', [])
            if not descs:
                continue
            
            # 找出這個技能的所有 aX 位置
            skill_positions = [(s, i) for s, i in all_ax_positions if s == skill_name]
            
            # 對每個等級的描述
            for level_desc in descs:
                # 移除 <u> 標籤
                level_desc = re.sub(r'</?u>', '', level_desc)
                # 找出所有紫色數值
                colored_values = re.findall(r'<span style="color: #f29e38ff;">(?:<strong>)?([\d\.]+%?)(?:</strong>)?</span>', level_desc)
                
                # 將數值加入對應的 aX 列表
                for i, value in enumerate(colored_values):
                    if (skill_name, i) in ax_map:
                        ax = ax_map[(skill_name, i)]
                        ax_values[ax].append(value)

        # 格式化輸出
        lines = []
        for ax, values in ax_values.items():
            if values:  # 只輸出有值的 aX
                arr = ', '.join([f'"{x}"' for x in values])
                lines.append(f'{ax}: [{arr}],')
        
        self.json_preview.setPlainText('\n'.join(lines))

    def write_skills_to_csv(self, skills_dict, csv_path):
        # skills_dict: {type: {name, title, descs, htmls, attrs?: [t1,t2,t3]}}
        fieldnames = (
            ["type", "name", "title"]
            + [f"desc_lv{i}" for i in range(1, 16)]
            + [f"raw_html_lv{i}" for i in range(1, 16)]
            + CSV_TRACE_TIER_FIELDS
        )
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for skill_type, skill in skills_dict.items():
                row = {
                    "type": skill_type,
                    "name": skill.get("name", ""),
                    "title": skill.get("title", ""),
                }
                for i in range(15):
                    row[f"desc_lv{i+1}"] = (
                        skill.get("descs", [""] * 15)[i]
                        if i < len(skill.get("descs", []))
                        else ""
                    )
                    row[f"raw_html_lv{i+1}"] = (
                        skill.get("htmls", [""] * 15)[i]
                        if i < len(skill.get("htmls", []))
                        else ""
                    )
                attrs = skill.get("attrs")
                if not isinstance(attrs, list):
                    attrs = []
                attrs = (list(attrs) + ["", "", ""])[:3]
                row["tier1"] = attrs[0] or ""
                row["tier2"] = attrs[1] or ""
                row["tier3"] = attrs[2] or ""
                writer.writerow(row)

    def read_skills_from_csv(self, csv_path):
        skills = {}
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                skill_type = row["type"]
                attrs = [
                    (row.get("tier1") or "").strip(),
                    (row.get("tier2") or "").strip(),
                    (row.get("tier3") or "").strip(),
                ]
                skills[skill_type] = {
                    "name": row["name"],
                    "title": row["title"],
                    "descs": [
                        row[f"desc_lv{i+1}"]
                        for i in range(15)
                        if row.get(f"desc_lv{i+1}", "")
                    ],
                    "htmls": [
                        row[f"raw_html_lv{i+1}"]
                        for i in range(15)
                        if row.get(f"raw_html_lv{i+1}", "")
                    ],
                    "attrs": attrs,
                }
        return skills

    def export_data(self):
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            # 1. character_stat.txt
            with open(os.path.join(script_dir, "character_stat.txt"), "w", encoding="utf-8") as f:
                f.write(self.stats_display.toPlainText())
            # 2. all_skill_silder.txt
            with open(os.path.join(script_dir, "all_skill_silder.txt"), "w", encoding="utf-8") as f:
                f.write(self.get_all_skill_silder_html())
            # 3. skill_silder_json.txt
            slider_data = {}
            skill_name = self.skill_combo.currentText()
            skill = self.skill_data.get(skill_name, {})
            descs = skill.get('descs', [])
            value_matrix = []
            for html_desc in descs:
                _, values = self.strip_html_and_get_values(html_desc)
                value_matrix.append(values)
            if value_matrix and any(value_matrix):
                max_len = max(len(row) for row in value_matrix)
                for idx in range(max_len):
                    slider_data[f'a{idx+1}'] = [row[idx] if idx < len(row) else "" for row in value_matrix]
            with open(os.path.join(script_dir, "skill_silder_json.txt"), "w", encoding="utf-8") as f:
                json.dump(slider_data, f, ensure_ascii=False, indent=2)
            QMessageBox.information(self, "成功", "數據已成功導出到指定文件！")
        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"導出數據時發生錯誤：{str(e)}")

    def load_character_stats(self, export_after=False):
        url = self.url_input.text().strip()
        if not url:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            link_path = os.path.join(script_dir, "link.txt")
            if os.path.exists(link_path):
                try:
                    with open(link_path, "r", encoding="utf-8") as f:
                        first_line = f.readline().strip()
                        if first_line:
                            url = first_line
                            self.url_input.setText(url)
                except Exception:
                    pass
            if not url:
                QMessageBox.warning(self, '提示', '請輸入角色網址（或確認 link.txt 存在）')
                return
        last_url_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "last_url.txt")
        try:
            with open(last_url_path, "w", encoding="utf-8") as f:
                f.write(url)
        except Exception as e:
            print(f"寫入 last_url.txt 失敗: {e}")
        self.stats_display.setText('載入中...')

        if "gachabase.net" in url:
            self._load_from_gachabase(url, export_after)
        elif "hakush.in" in url:
            self._load_from_hakush(url, export_after)
        else:
            QMessageBox.warning(self, "提示",
                "無法識別的網址格式。\n支援：\n• Gachabase: hsr.gachabase.net/characters/...\n• Hakush: hsr20.hakush.in/char/...")

    def _load_from_hakush(self, url, export_after=False):
        data, skill_data, silder_raw, char_id, char_name = self.selenium_extract_character_stats(url, return_skill_data=True)
        self.skill_data = skill_data
        self.silder_raw = silder_raw
        self.current_char_id = char_id
        self.current_char_name = char_name or ""
        self.silder_text_map = self.generate_silder_text_map_from_silder_raw()
        self.update_skill_display()
        self.update_json_preview()
        self.stats_display.setText(self.format_stats(data))
        script_dir = os.path.dirname(os.path.abspath(__file__))
        csv_path = os.path.join(script_dir, 'all_json.csv')
        self.write_skills_to_csv(self.skill_data, csv_path)
        with open(os.path.join(script_dir, "all_skill_silder.txt"), "w", encoding="utf-8") as f:
            f.write(self.get_all_skill_silder_html())
        if export_after:
            self._do_export()

    def on_download_images(self):
        """整合 download_img：依目前 URL 或已載入的角色下載技能/行跡/星魂圖片。"""
        if download_img_run_download is None:
            QMessageBox.warning(
                self, "無法下載",
                "找不到 download_img 模組，無法執行下載。請確認 download_img.py 與 skill_viewer.py 在同一目錄。"
            )
            return
        url = self.url_input.text().strip()
        char_id = self.current_char_id
        char_name = self.current_char_name or ""
        if not char_id and url:
            match = re.search(r"/char/(\d+)", url) or re.search(r"/characters/(\d+)", url)
            if match:
                char_id = match.group(1)
        if not char_id:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            link_path = os.path.join(script_dir, "link.txt")
            if os.path.exists(link_path):
                try:
                    with open(link_path, "r", encoding="utf-8") as f:
                        ll = f.readlines()
                        if len(ll) >= 2:
                            char_id = ll[1].strip()
                        if len(ll) >= 3 and not char_name:
                            char_name = ll[2].strip()
                except Exception:
                    pass
        if not char_id:
            QMessageBox.warning(
                self, "無法下載",
                "請先輸入角色網址並按「載入角色資料」，或確認 link.txt 存在。"
            )
            return
        if not char_name:
            char_name = f"char_{char_id}"
        self.download_img_button.setEnabled(False)
        self._download_progress = QProgressDialog("正在下載角色圖片…", None, 0, 0, self)
        self._download_progress.setWindowTitle("下載圖片")
        self._download_progress.setMinimumDuration(0)
        self._download_progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        self._download_progress.show()
        self._download_worker = DownloadImagesWorker(char_id, char_name, page_url=url)
        self._download_worker.finished.connect(self._on_download_images_finished)
        self._download_worker.start()

    def _on_download_images_finished(self, downloaded_count, failed_images):
        if self._download_progress:
            self._download_progress.close()
            self._download_progress = None
        self.download_img_button.setEnabled(True)
        if self._download_worker:
            self._download_worker = None
        msg = f"下載完成：成功 {downloaded_count} 張"
        if failed_images:
            msg += f"，失敗 {len(failed_images)} 張"
        QMessageBox.information(self, "下載角色圖片", msg)

    # ---------- WordPress 上傳 (Tab2) ----------
    def _wp_log(self, msg):
        self.wp_log_text.append(msg)
        sb = self.wp_log_text.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _wp_load_config(self):
        if not getattr(self, "wp_url_edit", None):
            return
        path = getattr(self, "_wp_config_path", None)
        if not path or not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("URL="):
                        self.wp_url_edit.setText(line.replace("URL=", "", 1))
                    elif line.startswith("USERNAME="):
                        self.wp_username_edit.setText(line.replace("USERNAME=", "", 1))
                    elif line.startswith("CSV="):
                        self.wp_csv_edit.setText(line.replace("CSV=", "", 1))
                    elif line.startswith("DIR="):
                        self.wp_materials_dir_edit.setText(line.replace("DIR=", "", 1))
        except Exception:
            pass

    def _wp_save_config(self):
        path = getattr(self, "_wp_config_path", None)
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"URL={self.wp_url_edit.text().strip()}\n")
                f.write(f"USERNAME={self.wp_username_edit.text().strip()}\n")
                f.write(f"CSV={self.wp_csv_edit.text().strip()}\n")
                f.write(f"DIR={self.wp_materials_dir_edit.text().strip()}\n")
            self._wp_log("[OK] 設定已保存（密碼不會保存）")
            QMessageBox.information(self, "成功", "設定已保存！(密碼不會保存)")
        except Exception as e:
            self._wp_log(f"[ERR] 保存設定失敗: {e}")
            QMessageBox.critical(self, "錯誤", str(e))

    def _wp_test_connection(self):
        wp_url = self.wp_url_edit.text().strip().rstrip("/")
        user = self.wp_username_edit.text().strip()
        pw = self.wp_password_edit.text()
        if not wp_url or not user or not pw:
            QMessageBox.warning(self, "失敗", "請填寫 WordPress URL、Username、Password。")
            return
        token_url = f"{wp_url}/wp-json/jwt-auth/v1/token"
        try:
            resp = requests.post(token_url, data={"username": user, "password": pw}, timeout=20)
            if resp.status_code != 200:
                self._wp_log(f"[ERR] JWT 登入失敗 {resp.status_code}: {resp.text[:200]}")
                QMessageBox.critical(self, "失敗", "JWT 登入失敗，請檢查帳密或插件設定。")
                return
            token = resp.json().get("token")
            if not token:
                QMessageBox.critical(self, "失敗", "JWT 回應缺少 token。")
                return
            validate_url = f"{wp_url}/wp-json/jwt-auth/v1/token/validate"
            r2 = requests.post(validate_url, headers={"Authorization": f"Bearer {token}"}, timeout=20)
            if r2.status_code == 200:
                self._wp_log("[OK] Token validate OK")
                QMessageBox.information(self, "成功", "JWT 連接成功（token validate OK）")
            else:
                self._wp_log(f"[WARN] Token validate 失敗 {r2.status_code}")
                QMessageBox.warning(self, "警告", "登入成功但 validate 失敗；通常仍可嘗試上傳。")
        except Exception as e:
            self._wp_log(f"[ERR] 測試連接: {e}")
            QMessageBox.critical(self, "失敗", str(e))

    def _wp_start_upload(self):
        if self._wp_upload_worker and self._wp_upload_worker.isRunning():
            return
        wp_url = self.wp_url_edit.text().strip().rstrip("/")
        user = self.wp_username_edit.text().strip()
        pw = self.wp_password_edit.text()
        csv_path = self.wp_csv_edit.text().strip()
        materials_dir = self.wp_materials_dir_edit.text().strip()
        if not wp_url or not user or not pw:
            QMessageBox.warning(self, "錯誤", "請輸入 WordPress URL / Username / Password。")
            return
        if not os.path.exists(csv_path):
            QMessageBox.critical(self, "錯誤", f"CSV 不存在：\n{csv_path}")
            return
        if not os.path.isdir(materials_dir):
            QMessageBox.critical(self, "錯誤", f"素材資料夾不存在：\n{materials_dir}")
            return
        self.wp_start_btn.setEnabled(False)
        self.wp_stop_btn.setEnabled(True)
        self.wp_lbl_total.setText("總檔案: ...")
        self.wp_lbl_up.setText("已上傳: 0")
        self.wp_lbl_skip.setText("已跳過: 0")
        self.wp_lbl_fail.setText("失敗: 0")
        self.wp_progress.setValue(0)
        self._wp_upload_worker = WpUploadWorker(wp_url, user, pw, csv_path, materials_dir)
        self._wp_upload_worker.log_msg.connect(self._wp_log)
        self._wp_upload_worker.progress.connect(self._wp_on_progress)
        self._wp_upload_worker.finished.connect(self._wp_upload_finished)
        self._wp_upload_worker.start()

    def _wp_on_progress(self, total, current, uploaded, skipped, failed):
        self.wp_lbl_total.setText(f"總檔案: {total}")
        self.wp_lbl_up.setText(f"已上傳: {uploaded}")
        self.wp_lbl_skip.setText(f"已跳過: {skipped}")
        self.wp_lbl_fail.setText(f"失敗: {failed}")
        self.wp_progress.setValue(int((current / total) * 100) if total else 0)

    def _wp_stop_upload(self):
        if self._wp_upload_worker and self._wp_upload_worker.isRunning():
            self._wp_upload_worker.abort()

    def _wp_upload_finished(self):
        self.wp_start_btn.setEnabled(True)
        self.wp_stop_btn.setEnabled(False)
        self._wp_upload_worker = None

    def selenium_extract_character_stats(self, url, return_skill_data=False):
        """使用 API 直接獲取角色資料"""
        
        def process_text(text):
            if not text:
                return ""
            text = text.replace('\n', '<br>')
            text = text.replace('"', '\\"')
            return text
        
        def format_param(value, format_type, is_percent=False):
            """格式化參數值
            is_percent: 如果後面有 % 符號，說明這是百分比值，需要乘以 100
            """
            if format_type == 'i':
                # 整數
                if is_percent:
                    # 百分比值，乘以 100
                    result = str(int(round(value * 100)))
                else:
                    result = str(int(value)) if isinstance(value, float) and value == int(value) else str(value)
                return result
            elif format_type.startswith('f'):
                # 浮點數
                decimals = int(format_type[1]) if len(format_type) > 1 else 1
                if is_percent:
                    # 百分比值，乘以 100
                    result = f"{value * 100:.{decimals}f}"
                else:
                    result = f"{value:.{decimals}f}"
                return result
            return str(value)
        
        def replace_params_in_desc(desc, param_list):
            """將描述中的 #N[格式] 替換為實際參數值，並添加顏色"""
            if not desc:
                return desc
            
            # 先移除 <unbreak> 和 </unbreak> 標籤
            result = re.sub(r'</?unbreak>', '', desc)
            # 移除 <u> 和 </u> 標籤
            result = re.sub(r'</?u>', '', result)
            # 移除 <color=...> 和 </color> 標籤（保留內容）
            result = re.sub(r'<color=[^>]*>', '', result)
            result = re.sub(r'</color>', '', result)
            
            if not param_list:
                return result
            
            def replace_match(match):
                idx = int(match.group(1)) - 1  # 參數索引從1開始
                fmt = match.group(2)
                has_percent = match.group(3) == '%'  # 檢查是否捕獲到 %
                
                if idx < len(param_list):
                    value = format_param(param_list[idx], fmt, has_percent)
                    # 如果有 %，需要保留原始的 % 符號
                    if has_percent:
                        return f'<span style="color: #f29e38ff;">{value}%</span>'
                    else:
                        return f'<span style="color: #f29e38ff;">{value}</span>'
                return match.group(0)
            
            # 替換 #N[格式] 模式，同時捕獲後面可能的 % 符號
            result = re.sub(r'#(\d+)\[([^\]]+)\](%?)', replace_match, result)
            return result

        data = {}
        skill_data = {}
        silder_raw = {}

        # 從 URL 提取角色 ID
        match = re.search(r'/char/(\d+)', url)
        if not match:
            print(f"無法從 URL 提取角色 ID: {url}")
            if return_skill_data:
                return data, skill_data, silder_raw, None, ""
            return data

        char_id = match.group(1)
        char_name = ""
        api_url = f"https://api.hakush.in/hsr/data/en/character/{char_id}.json"

        progress = QProgressDialog("正在從 API 獲取角色資料...", None, 0, 100, self)
        progress.setWindowTitle("進度")
        progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        progress.show()
        
        try:
            print(f"正在獲取 API: {api_url}")
            response = requests.get(api_url, timeout=30)
            response.raise_for_status()
            api_data = response.json()
            char_name = api_data.get("Name", "") or ""
            progress.setValue(20)

            # 提取基本屬性 (Stats)
            stats = api_data.get('Stats', {}).get('6', {})  # 取最高突破等級的數據
            data['1'] = str(int(stats.get('HPBase', 0) + stats.get('HPAdd', 0) * 80))  # HP at Lv80
            data['2'] = str(int(stats.get('AttackBase', 0) + stats.get('AttackAdd', 0) * 80))  # ATK
            data['3'] = str(int(stats.get('DefenceBase', 0) + stats.get('DefenceAdd', 0) * 80))  # DEF
            data['4'] = str(int(stats.get('SpeedBase', 107)))  # Speed
            data['5'] = str(int(stats.get('BaseAggro', 100)))  # Taunt
            data['6'] = str(api_data.get('SPNeed', 0))  # Max Energy
            data['overview1'] = api_data.get('Desc', '').replace('\\n', '<br>')
            progress.setValue(30)
            
            # 技能類型映射
            skill_type_map = {
                'Normal': 'Basic ATK',
                'BPSkill': 'Skill', 
                'Ultra': 'Ultimate',
                'Maze': 'Technique',
                'ElationDamage': 'Elation Skill'
            }
            
            # 找出主要技能 ID（基於類型）
            skills_api = api_data.get('Skills', {})
            main_skills = {}  # type -> skill_id
            
            for skill_id, skill_info in skills_api.items():
                skill_type = skill_info.get('Type')
                if skill_type in skill_type_map and skill_type not in ['MazeNormal']:
                    mapped_type = skill_type_map[skill_type]
                    # 優先選擇有 Desc 的技能
                    if mapped_type not in main_skills or skill_info.get('Desc'):
                        main_skills[mapped_type] = skill_id
            
            # 找 Talent (被動技能) - 通常沒有 Type 或 Type 為 null
            for skill_id, skill_info in skills_api.items():
                if skill_info.get('Type') is None and skill_info.get('Desc'):
                    if 'Talent' not in main_skills:
                        main_skills['Talent'] = skill_id
            
            progress.setValue(40)
            
            # 處理技能資料
            for skill_type, skill_id in main_skills.items():
                skill_info = skills_api.get(skill_id, {})
                skill_name = skill_info.get('Name', '')
                skill_desc_template = skill_info.get('Desc', '')
                skill_tag = skill_info.get('Tag', '')
                levels = skill_info.get('Level', {})
                
                # 生成每個等級的描述
                descs = []
                max_level = 10 if skill_type == 'Basic ATK' else 15
                
                for lv in range(1, max_level + 1):
                    lv_key = str(lv)
                    if lv_key in levels:
                        param_list = levels[lv_key].get('ParamList', [])
                        desc = replace_params_in_desc(skill_desc_template, param_list)
                        descs.append(desc)
                    elif descs:
                        # 如果沒有這個等級的資料，使用最後一個
                        descs.append(descs[-1])
                    else:
                        descs.append(skill_desc_template)
                
                # 如果只有一個等級（如 Technique），只保留一個描述
                if len(levels) == 1:
                    param_list = list(levels.values())[0].get('ParamList', [])
                    descs = [replace_params_in_desc(skill_desc_template, param_list)]
                
                # 從 API 組裝技能屬性數值（Energy Regeneration、Weakness Break、Skill Points）
                skill_attrs = []
                sp_base = skill_info.get('SPBase')
                if sp_base is not None:
                    skill_attrs.append(f"Energy Regeneration {sp_base}")
                stance_list = skill_info.get('ShowStanceList') or []
                stance_labels = ["Weakness Break Single Target", "Weakness Break Blast", "Weakness Break AoE"]
                for i, val in enumerate(stance_list):
                    if val is not None and val != 0 and i < len(stance_labels):
                        skill_attrs.append(f"{stance_labels[i]}: {val}")
                bp_add = skill_info.get('BPAdd')
                if bp_add is not None and bp_add != 0:
                    skill_attrs.append(f"Skill Points +{bp_add}")
                bp_need = skill_info.get('BPNeed')
                if bp_need is not None and bp_need > 0:
                    skill_attrs.append(f"Skill Points -{bp_need}")
                
                skill_data[skill_type] = {
                    'name': skill_name,
                    'title': skill_tag if skill_tag else skill_type,
                    'descs': descs,
                    'htmls': descs,
                    'skill_attrs': skill_attrs
                }
                
                if descs:
                    silder_raw[skill_type] = descs
            
            progress.setValue(60)
            
            # 處理 Eidolons (星魂)
            ranks = api_data.get('Ranks', {})
            for rank_num, rank_info in ranks.items():
                if rank_num.isdigit() and int(rank_num) <= 6:
                    name = rank_info.get('Name', '')
                    desc = rank_info.get('Desc', '')
                    param_list = rank_info.get('ParamList', [])
                    desc = replace_params_in_desc(desc, param_list)
                    data[f'Eidolons{rank_num}name'] = process_text(name)
                    data[f'Eidolons{rank_num}desc'] = process_text(desc.replace('\\n', '<br>'))
            
            progress.setValue(70)
            
            # 處理 Traces (行跡能力)
            skill_trees = api_data.get('SkillTrees', {})
            trace_mapping = {
                'Point06': ('A', 1),  # 第一個額外能力
                'Point07': ('B', 2),  # 第二個額外能力
                'Point08': ('C', 3),  # 第三個額外能力
            }
            
            attrs_map = {"A": [], "B": [], "C": [], "D": []}
            
            # 建立 PointID -> letter 和 PointID -> PrePoint 的映射
            trace_point_ids = {}  # 主 trace 的 PointID -> letter (A/B/C)
            all_point_ids = {}    # 所有節點的 PointID -> PrePoint 列表
            point_id_to_key = {}  # PointID -> Point key (如 'Point06')
            
            for point_key, point_levels in skill_trees.items():
                if point_key.startswith('Point'):
                    point_data = point_levels.get('1', {})
                    point_id = point_data.get('PointID')
                    pre_points = point_data.get('PrePoint', [])
                    if point_id:
                        all_point_ids[point_id] = pre_points
                        point_id_to_key[point_id] = point_key
            
            # 先獲取 A/B/C 的 PointID
            for point_key, (trace_letter, trace_num) in trace_mapping.items():
                if point_key in skill_trees:
                    point_data = skill_trees[point_key].get('1', {})
                    point_id = point_data.get('PointID')
                    if point_id:
                        trace_point_ids[point_id] = trace_letter
                    
                    name = point_data.get('PointName', '')
                    desc = point_data.get('PointDesc', '')
                    param_list = point_data.get('ParamList', [])
                    
                    if name and desc:
                        desc = replace_params_in_desc(desc, param_list)
                        data[f'{trace_letter}name'] = process_text(name)
                        data[f'{trace_letter}desc'] = process_text(desc)
                        
                        skill_data[f'{trace_letter}desc'] = {
                            'name': name,
                            'title': f"ASCEND CALCULATOR {trace_letter}",
                            'descs': [desc],
                            'htmls': [desc],
                            'attrs': []
                        }
            
            # 遞歸查找節點所屬的主 trace
            def find_trace_letter(point_id, visited=None):
                if visited is None:
                    visited = set()
                if point_id in visited:
                    return None
                visited.add(point_id)
                
                # 如果是主 trace 節點，直接返回
                if point_id in trace_point_ids:
                    return trace_point_ids[point_id]
                
                # 否則遞歸查找 PrePoint
                pre_points = all_point_ids.get(point_id, [])
                for pre_id in pre_points:
                    result = find_trace_letter(pre_id, visited)
                    if result:
                        return result
                return None
            
            # 處理小屬性節點，根據 PrePoint 遞歸分配到對應的 trace
            for point_key, point_levels in skill_trees.items():
                if point_key.startswith('Point') and point_key not in trace_mapping:
                    point_data = point_levels.get('1', {})
                    status_add_list = point_data.get('StatusAddList', [])
                    point_id = point_data.get('PointID')
                    
                    # 遞歸判斷這個節點屬於哪個 trace
                    target_letter = find_trace_letter(point_id) if point_id else None
                    
                    for status in status_add_list:
                        prop_name = status.get('Name', '')
                        prop_value = status.get('Value', 0)
                        
                        if prop_name and prop_value:
                            # 格式化屬性值
                            if prop_value < 1:
                                formatted_value = f"{prop_value * 100:.1f}%"
                            else:
                                formatted_value = str(prop_value)
                            
                            attr_text = f"{prop_name} + {formatted_value}"
                            
                            if target_letter:
                                attrs_map[target_letter].append(attr_text)
                            else:
                                attrs_map["D"].append(attr_text)
            
            # 將屬性添加到對應的 trace
            for key in ["A", "B", "C"]:
                if f'{key}desc' in skill_data:
                    skill_data[f'{key}desc']['attrs'] = attrs_map.get(key, [])
            
            if attrs_map["D"]:
                skill_data["Ddesc"] = {
                    "name": "Extra Attributes",
                    "title": "ASCEND CALCULATOR D",
                    "descs": [""],
                    "htmls": [""],
                    "attrs": attrs_map["D"]
                }
            
            progress.setValue(100)
            print("API 資料獲取完畢")
            
        except requests.exceptions.RequestException as e:
            print(f"API 請求失敗: {e}")
            err_low = str(e).lower()
            hint = ""
            if isinstance(e, requests.exceptions.ConnectionError) or (
                "getaddrinfo" in err_low
                or "name resolution" in err_low
                or "failed to resolve" in err_low
            ):
                hint = (
                    "\n\n【常見原因】無法連上 api.hakush.in（DNS 解析失敗、無網路、防火牆或需 VPN）。\n"
                    "【建議】改在上方 URL 貼 Gachabase 角色頁並重新載入，例如：\n"
                    "https://hsr.gachabase.net/characters/1502/yao-guang/beta?lang=en\n"
                    "（請依角色替換路徑；並將該網址寫入 link.txt 第一行可每次自動帶入。）"
                )
            QMessageBox.warning(self, "無法連線 Hakush API", f"{e}{hint}")
        except json.JSONDecodeError as e:
            print(f"JSON 解析失敗: {e}")
            QMessageBox.warning(self, "錯誤", f"API 返回的資料格式錯誤: {e}")
        except Exception as e:
            print(f"處理資料時發生錯誤: {e}")
            import traceback
            traceback.print_exc()
        finally:
            progress.setValue(100)
            progress.close()
        
        if return_skill_data:
            return data, skill_data, silder_raw, char_id, char_name
        return data

    def format_stats(self, data):
        def strip_html_tags(text):
            return re.sub('<[^<]+?>', '', text)
        def escape_js_value(v):
            s = str(v or "")
            return s.replace("\\", "\\\\").replace('"', '\\"')
        lines = []
        lines.append(f"'1': \"{data.get('1', '')}\",")
        lines.append(f"'2': \"{data.get('2', '')}\",")
        lines.append(f"'3': \"{data.get('3', '')}\",")
        lines.append(f"'4': \"{data.get('4', '')}\",")
        lines.append(f"'5': \"{data.get('5', '')}\",")
        lines.append(f"'6': \"{data.get('6', '')}\",")
        lines.append(f"'overview1': \"{data.get('overview1', '')}\",")
        # 技能名稱直接取動態 skill_data
        lines.append(f"'normalatkname': \"{self.skill_data.get('Basic ATK', {}).get('name', '')}\",")
        lines.append(f"'skillname': \"{self.skill_data.get('Skill', {}).get('name', '')}\",")
        lines.append(f"'ultimatename': \"{self.skill_data.get('Ultimate', {}).get('name', '')}\",")
        lines.append(f"'talentname': \"{self.skill_data.get('Talent', {}).get('name', '')}\",")
        lines.append(f"'Techniquename': \"{self.skill_data.get('Technique', {}).get('name', '')}\",")
        # title
        lines.append(f"'normalatktitle': \"{self.skill_data.get('Basic ATK', {}).get('title', '')}\",")
        lines.append(f"'skilltitle': \"{self.skill_data.get('Skill', {}).get('title', '')}\",")
        lines.append(f"'ultimatetitle': \"{self.skill_data.get('Ultimate', {}).get('title', '')}\",")
        lines.append(f"'talenttitle': \"{self.skill_data.get('Talent', {}).get('title', '')}\",")
        lines.append(f"'Techniquetitle': \"{self.skill_data.get('Technique', {}).get('title', '')}\",")
        technique_desc = ""
        if "Technique" in self.skill_data:
            descs = self.skill_data["Technique"].get("descs", [])
            if descs:
                technique_desc = strip_html_tags(descs[0])
                # 與 process_text 一致：\n 換成 <br>，雙引號轉義避免 JS 格式錯誤
                technique_desc = technique_desc.replace("\\n", "<br>").replace("\n", "<br>").replace('"', '\\"')
        lines.append(f"'Techniquedesc': \"{technique_desc}\",")
        lines.append(f"'Eidolons1name': \"{data.get('Eidolons1name', '')}\",")
        lines.append(f"'Eidolons1desc': \"{data.get('Eidolons1desc', '')}\",")
        lines.append(f"'Eidolons2name': \"{data.get('Eidolons2name', '')}\",")
        lines.append(f"'Eidolons2desc': \"{data.get('Eidolons2desc', '')}\",")
        lines.append(f"'Eidolons3name': \"{data.get('Eidolons3name', '')}\",")
        lines.append(f"'Eidolons3desc': \"{data.get('Eidolons3desc', '')}\",")
        lines.append(f"'Eidolons4name': \"{data.get('Eidolons4name', '')}\",")
        lines.append(f"'Eidolons4desc': \"{data.get('Eidolons4desc', '')}\",")
        lines.append(f"'Eidolons5name': \"{data.get('Eidolons5name', '')}\",")
        lines.append(f"'Eidolons5desc': \"{data.get('Eidolons5desc', '')}\",")
        lines.append(f"'Eidolons6name': \"{data.get('Eidolons6name', '')}\",")
        lines.append(f"'Eidolons6desc': \"{data.get('Eidolons6desc', '')}\",")
        lines.append(f"'Aname': \"{data.get('Aname', '')}\",")
        lines.append(f"'Adesc': \"{data.get('Adesc', '')}\",")
        lines.append(f"'Bname': \"{data.get('Bname', '')}\",")
        lines.append(f"'Bdesc': \"{data.get('Bdesc', '')}\",")
        lines.append(f"'Cname': \"{data.get('Cname', '')}\",")
        lines.append(f"'Cdesc': \"{data.get('Cdesc', '')}\",")
        # 新增 Atier1~3, Btier1~3, Ctier1~3, Dtier1~3
        def get_tiers(key):
            attrs = self.skill_data.get(key, {}).get('attrs', [])
            return [attrs[i] if i < len(attrs) else '' for i in range(3)]
        for prefix, key in zip(['A', 'B', 'C', 'D'], ['Adesc', 'Bdesc', 'Cdesc', 'Ddesc']):
            tiers = get_tiers(key)
            for i in range(3):
                lines.append(f"'{prefix}tier{i+1}': \"{tiers[i]}\",")
        # 保底：統一把每行 value 做跳脫，避免手動補 \" 才能讀取
        escaped_lines = []
        line_re = re.compile(r"^('.*?': \")(.*)(\",)$")
        for line in lines:
            m = line_re.match(line)
            if not m:
                escaped_lines.append(line)
                continue
            escaped_lines.append(f"{m.group(1)}{escape_js_value(m.group(2))}{m.group(3)}")
        return "\n".join(escaped_lines)

    def generate_silder_text_map(self):
        silder_map = {}
        key_map = []  # [(aX, skill_name, effect_key)]
        key_counter = 1
        skill_order = ["Basic ATK", "Skill", "Ultimate", "Talent", "Elation Skill"]
        # 先建立 aX 對應表，根據描述中實際出現的 value
        for skill_name in skill_order:
            if skill_name in self.skill_data:
                skill = self.skill_data[skill_name]
                all_levels = skill['levels']
                effect_keys = set()
                for lv in all_levels.values():
                    effect_keys.update(lv.keys())
                first_level = next(iter(all_levels.values()), {})
                for effect_key in sorted(effect_keys):
                    value = first_level.get(effect_key, "")
                    # 檢查描述中是否有這個 value
                    if value == "":
                        continue
                    desc = skill['description']
                    found = False
                    patterns = []
                    try:
                        fval = float(value)
                        patterns = [
                            re.escape(str(value)),
                            f"{fval*100:.0f}%",
                            f"{fval*100:.2f}%",
                            f"{fval:.2f}",
                            f"{fval:.1f}",
                            f"{fval:.0f}"
                        ]
                    except Exception:
                        patterns = [re.escape(str(value))]
                    for pat in patterns:
                        regex = re.compile(rf"(?<![\d.]){pat}(?![\d.])")
                        if regex.search(desc):
                            found = True
                            break
                    if found:
                        key_map.append((f"a{key_counter}", skill_name, effect_key))
                        key_counter += 1
        # 2. 替換描述（精確定位法）
        for skill_name in skill_order + ["Technique"]:
            if skill_name not in self.skill_data:
                continue
            skill = self.skill_data[skill_name]
            desc = skill['description']
            if skill_name == "Technique":
                silder_map[skill_name] = desc
                continue
            skill_keys = [(a, k) for a, s, k in key_map if s == skill_name]
            first_level = next(iter(skill['levels'].values()), {})
            replaced = desc
            for idx, (a_key, effect_key) in enumerate(skill_keys):
                value = first_level.get(effect_key, "")
                if value == "":
                    continue
                patterns = []
                try:
                    fval = float(value)
                    patterns = [
                        re.escape(str(value)),
                        f"{fval*100:.0f}%",
                        f"{fval*100:.2f}%",
                        f"{fval:.2f}",
                        f"{fval:.1f}",
                        f"{fval:.0f}"
                    ]
                except Exception:
                    patterns = [re.escape(str(value))]
                found = False
                for pat in patterns:
                    regex = re.compile(rf"(?<![\d.]){pat}(?![\d.])")
                    match = regex.search(replaced)
                    if match:
                        start, end = match.span()
                        replaced = replaced[:start] + f'<span id="{a_key}">&nbsp;</span>' + replaced[end:]
                        found = True
                        break
                if not found:
                    pass
            silder_map[skill_name] = replaced
        self.key_map = key_map  # 存下 key_map 供 json 用
        return silder_map

    def generate_silder_text_map_from_silder_raw(self):
        # TODO: 根據 self.silder_raw 產生 silder_text_map、aX 對應、json
        # 這裡僅為結構，實際邏輯需根據描述變化自動分配 aX
        # 返回 silder_text_map
        return {}

    def strip_html_and_get_values(self, html_desc):
        # 去除 HTML 標籤，並提取所有數值（如 50%、60%...）
        text = re.sub('<[^<]+?>', '', html_desc)
        text = html.unescape(text)
        # 提取所有百分比或數值
        values = re.findall(r'[\d\.]+%?', text)
        return text, values

    def replace_values_with_span(self, html_desc):
        # 將描述中的數值依序替換為 <span id="aX">&nbsp;</span>
        text = html_desc
        values = re.findall(r'<strong>([\d\.]+%?)</strong>', html_desc)
        replaced = text
        for idx, val in enumerate(values):
            replaced = replaced.replace(f'<strong>{val}</strong>', f'<span id="a{idx+1}">&nbsp;</span>', 1)
        # 若有未包 <strong> 的數值，也處理
        plain_values = re.findall(r'>([\d\.]+%?)<', html_desc)
        for val in plain_values:
            if f'<span id="' not in replaced:
                replaced = replaced.replace(f'>{val}<', f'><span id="a{len(values)+1}">&nbsp;</span><', 1)
        return replaced, values

    def get_ax_map(self, html_desc):
        # 只針對等級1描述，依序找出所有數值，分配 a1, a2, ...
        text = re.sub('<[^<]+?>', '', html_desc)
        text = html.unescape(text)
        # 只抓數值（百分比或純數字）
        values = re.findall(r'[\d\.]+%?', text)
        ax_map = {}
        for idx, val in enumerate(values):
            ax_map[val] = f'a{idx+1}'
        return ax_map

    def replace_values_with_ax(self, html_desc, ax_map):
        # 依據 ax_map 依序替換
        text = html_desc
        for val, ax in ax_map.items():
            # 只替換一次，避免重複
            text = re.sub(rf'(<strong>)?{re.escape(val)}(</strong>)?', f'<span id="{ax}">&nbsp;</span>', text, count=1)
        return text

    def replace_colored_values_with_ax(self, html_desc):
        # 1. 找出所有紫色數值（依序）
        colored_pattern = r'<span style="color: #f29e38ff;">([\d\.]+%?)</span>'
        colored_values = re.findall(colored_pattern, html_desc)
        # 2. 依序分配 a1, a2, ...
        replaced = html_desc
        for idx, val in enumerate(colored_values):
            # 只替換第一個出現的該值（避免重複）
            replaced = re.sub(
                rf'<span style="color: #f29e38ff;">{re.escape(val)}</span>',
                f'<span style="color: #f29e38ff;"><span id="a{idx+1}">&nbsp;</span></span>',
                replaced,
                count=1
            )
        return replaced

    def _get_silder_content_for_skill(self, skill_name):
        """回傳與 all_skill_silder.txt 一致的單一技能 silder 內容（全域 a1,a2.. 編號、與 txt 同格式）。"""
        skill_order = ["Basic ATK", "Skill", "Ultimate", "Talent", "Elation Skill"]
        colored_pattern = r'<span style="color: #f29e38ff;">(?:<strong>)?([\d\.]+%?)(?:</strong>)?</span>'
        all_colored_positions = []
        skill_blocks = []
        for sname in skill_order:
            if sname not in self.skill_data:
                continue
            descs = self.skill_data[sname].get('descs', [])
            if not descs:
                continue
            html_desc = re.sub(r'</?u>', '', descs[0])
            colored_values = re.findall(colored_pattern, html_desc)
            skill_blocks.append((sname, html_desc, colored_values))
            all_colored_positions.extend([(sname, i) for i in range(len(colored_values))])
        ax_map = {}
        for idx, (sname, i) in enumerate(all_colored_positions):
            ax_map[(sname, i)] = f'a{idx+1}'
        for sname, html_desc, colored_values in skill_blocks:
            if sname != skill_name:
                continue
            cnt = 0
            def replace_once(match):
                nonlocal cnt
                ax = ax_map[(skill_name, cnt)]
                cnt += 1
                return f'<span style="color: #f29e38ff;"><span id="{ax}">&nbsp;</span></span>'
            replaced = re.sub(
                colored_pattern,
                replace_once,
                html_desc
            )
            return replaced
        return ""

    def get_all_skill_silder_html(self):
        import re
        skill_order = ["Basic ATK", "Skill", "Ultimate", "Talent", "Elation Skill"]
        all_colored_positions = []
        skill_descs = []
        for skill_name in skill_order:
            if skill_name in self.skill_data:
                descs = self.skill_data[skill_name].get('descs', [])
                if not descs:
                    continue
                html_desc = descs[0]
                # 移除 <u> 標籤
                html_desc = re.sub(r'</?u>', '', html_desc)
                colored_pattern = r'<span style="color: #f29e38ff;">(?:<strong>)?([\d\.]+%?)(?:</strong>)?</span>'
                colored_values = re.findall(colored_pattern, html_desc)
                skill_descs.append((skill_name, html_desc, colored_values))
                all_colored_positions.extend([(skill_name, i) for i in range(len(colored_values))])
        ax_map = {}  # (skill_name, idx_in_skill) -> aX
        for idx, (skill_name, i) in enumerate(all_colored_positions):
            ax_map[(skill_name, i)] = f'a{idx+1}'
        result = []
        for skill_name, html_desc, colored_values in skill_descs:
            replaced = html_desc
            cnt = 0
            def replace_once(match):
                nonlocal cnt
                ax = ax_map[(skill_name, cnt)]
                cnt += 1
                return f'<span style="color: #f29e38ff;"><span id="{ax}">&nbsp;</span></span>'
            replaced = re.sub(
                r'<span style="color: #f29e38ff;">(?:<strong>)?([\d\.]+%?)(?:</strong>)?</span>',
                replace_once,
                replaced
            )
            result.append(f"{skill_name}\n\n{replaced}\n\n")
        return "\n".join(result)

def main():
    app = QApplication(sys.argv)
    viewer = SkillViewer()
    viewer.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 