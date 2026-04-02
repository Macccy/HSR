# hsr — 星穹鐵道技能／素材工具（多角色資料夾）

本 repo 以 **角色專用資料夾** 為單位（例如 `Ashveil`、`Stelle Elation`、`Evanescia`、`Silver Wolf LV999`、`yao guang`）。每個資料夾內的 **`README.md`** 說明該角的 **資料來源** 與建議操作；**`HH_extraction_guide.md`**（若有）說明從 HH／手動整理 CSV 的流程。

第二台電腦／第二個 Cursor 工作區請依下列順序還原，再開啟對應角色資料夾閱讀其 README。

## 1. 取得程式碼

```bash
git clone https://github.com/Macccy/HSR.git
cd HSR
```

## 2. Python 環境與依賴

需 **Python 3.10+**（建議 3.11／3.12）。在 repo 根目錄：

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

依套件見根目錄 **`requirements.txt`**（PyQt6、requests、BeautifulSoup4、Pillow）。

## 3. 在「角色資料夾」內操作

進入你要维护的角色目錄（範例）：

```powershell
cd "Ashveil"
# 或 cd "Stelle Elation"
# 或 cd "Evanescia"
# 或 cd "Silver Wolf LV999"
# 或 cd "yao guang"
```

常見指令（細節以該資料夾 **README.md** 為準）：

| 用途 | 指令 |
|------|------|
| 檢查 Gachabase 與檔案 | `py verify_*_gachabase.py` 或 `py verify_gachabase.py` |
| 從 Gachabase 重產 Lv1 CSV 骨架 | `py bootstrap_gachabase_csv.py`（有提供的資料夾） |
| 依 CSV 重產 silder 範本 | `py regen_all_skill_silder.py`（有提供的資料夾） |
| 圖形介面 | `py skill_viewer.py` |
| 下載圖片 | `py download_img.py` |

- **無 Elation** 的角色（如 Ashveil）驗證腳本檔名可能為 `verify_ashveil_gachabase.py`。  
- **有 Elation** 且與 Stelle 範本一致者，多為 **`verify_gachabase.py`**。

## 4. 第二台裝置特別注意

- **`download_img.py`** 內預設本機圖片根目錄／CSV 路徑可能為作者電腦路徑；請在該檔或設定中改為**你電腦**的路徑，否則圖片會寫到錯誤位置。  
- Windows 終端若中文／emoji 亂碼，可設定：`$env:PYTHONIOENCODING='utf-8'`（PowerShell）。  
- **Git** 作者資訊僅在 commit 時需要：`git config user.name`、`git config user.email`（或 `--global`）。

## 5. 各 README 能不能「讓 Cursor 獨力做完」？

- **角色資料夾 `README.md`**：已寫 **資料來源**（Gachabase／HH／手填／腳本產物），適合 Cursor 理解「該相信哪份檔、該跑哪支程式」。  
- **不足以** 自動推出全域環境：若**沒有**本檔與 **`requirements.txt`**，第二台機器無法唯讀 MD 就得知 pip 套件與 Python 版本。  
- **`HH_extraction_guide.md`**：偏重人工／對表流程，Cursor 可協助編修 CSV，但無法取代遊戲內或 HH 的數值查證。

若你新增角色資料夾，請複製既有範本並更新 **`link.txt`**、**README.md（含資料來源表）**，必要時補 **`bootstrap_gachabase_csv.py`**／**`verify_gachabase.py`** 與本節對應說明。
