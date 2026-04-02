# Ashveil（1504）角色資料夾

對應 Gachabase：`https://hsr.gachabase.net/characters/1504/ashveil/beta?lang=en`

流程對齊 `HH_extraction_guide.md`（同資料夾內，由 `yao guang` 複製）。

## 檔案說明

| 檔案 | 說明 |
|------|------|
| `link.txt` | 第 1 行：Gachabase URL；第 2 行：角色 ID；第 3 行：顯示名稱（下載檔名前綴） |
| `last_url.txt` | 上次載入的網址（程式會寫入） |
| `all_json.csv` | 技能／行跡敘述各等級（已依 HH／遊戲資料填好） |
| `all_skill_silder.txt` | 含 `<span id="aX">` 的 HTML 模板 |
| `skill_slider_script.js` | `sliderValues` 與滑條對應 |
| `skill_viewer.py` / `download_img.py` | 與 `yao guang` 同步的工具 |
| `trace_tiers_supplement.json`（選用） | 覆寫任意 tier 格（非空才寫入）；檔名必須是此名，**不要**只留 `.example.json` |
| `all_json.csv` 尾端 **`tier1` / `tier2` / `tier3`** | 與 **Atier1～3** 對應；Gachabase 只會更新 **tier1**，**tier2、tier3 請在此欄手填**後存檔再載入 |

**注意：** `Ddesc`（Extra Attributes）在 CSV 中本來無長敘述；在 **skill_viewer** 按「載入角色資料」從 Gachabase 解析後，會把 **Traces 小屬性加成** 寫入記憶體中的 `Ddesc.attrs`（與 Yao Guang 流程相同）。

### 為什麼 Atier2/3、Btier2/3… 會是空的？

Gachabase **靜態 HTML** 裡，每條行跡樹通常只有 **一個** `trace-stat-*` 區塊（對應 **tier1**）。其餘小節點**網頁沒有獨立區塊**，無法自動抓取。

**請這樣做（推薦）：** 用 Excel／記事本打開 **`all_json.csv`**，找到 **`Adesc` / `Bdesc` / `Cdesc` / `Ddesc`** 那一列（載入過 Gachabase 後檔案尾端會有 **`tier1`,`tier2`,`tier3`** 三欄），在 **`tier2`、`tier3`** 填入遊戲內小行跡數值，存檔後再在 skill_viewer **載入角色資料**。

**或** 複製 `trace_tiers_supplement.example.json` → **`trace_tiers_supplement.json`**（檔名要對），第一格留 `""` 以保留 Gachabase 的 tier1。

此角色 **無 Elation Skill**，故 CSV 與 `all_skill_silder.txt` 皆不含該區塊 — 與 Gachabase 頁面一致。

## 建議操作順序

1. **驗證 Gachabase 與檔案是否對齊**（不需開 GUI）  
   ```text
   py verify_ashveil_gachabase.py
   ```

2. **下載技能／行跡／星魂／升級素材圖**（輸出到專案共用 `hsr\img`，並寫入 `materials_download_log.csv`）  
   ```text
   py download_img.py
   ```
   若終端機編碼報錯，可先：`$env:PYTHONIOENCODING='utf-8'`（PowerShell）

3. **開啟技能檢視**  
   ```text
   py skill_viewer.py
   ```  
   網址列應為 `link.txt` 第一行；按「載入角色資料」→ 面板應顯示基礎數值、星魂、並補上 Ddesc 小屬性列。

## 是否達成指南要求（檢核）

- ✅ 三件套：`all_skill_silder.txt`、`all_json.csv`、`skill_slider_script.js` 齊備且互相對應（a1～a17）。
- ✅ Gachabase 可補：**基礎屬性、星魂、Traces 加成列、圖片下載**。
- ⚠️ 全等級數值表仍以 **CSV／JS 內容為準**（通常來自 HH 或手動對表）；Gachabase 單頁僅能對照某一等級，請仍依 `HH_extraction_guide.md` 交叉驗證。
