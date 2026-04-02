# Stelle Elation（8010，開拓者・記憶）— 歡愉命途

Gachabase：`https://hsr.gachabase.net/characters/8010/stelle-elation/beta?lang=en`

此資料夾與 `yao guang`／`Ashveil` 流程對齊；角色具 **Elation Skill** 欄位，HTML 滑條腳本含 `elation-level-slider`。

## 目前資料的來源（截至本頁所描述之流程）

| 資料／檔案 | 主要來源 | 補充 |
|------------|----------|------|
| 角色頁 URL、`link.txt` | [Gachabase](https://hsr.gachabase.net) 公開角色頁 `…/8010/stelle-elation/beta?lang=en` | 與官方不一定同步 |
| **`bootstrap_gachabase_csv.py` 產生的 `all_json.csv`**（各技能／行跡 **Lv1** 的 `desc_lv1`／`raw_html_lv1`） | **同一 Gachabase 頁** 的 **HTML 區塊**（`skill-type-*`、`trace-8010*`）經腳本正規化 | **非** Hakush；**不含** Lv2～Lv15 自動展開 |
| **`skill_viewer` 按「載入角色資料」** | 與 Ashveil 相同：**Gachabase HTML** 補 **基礎屬性、星魂、trace-stat tier1、Ddesc 合併** 等 | 會**寫回**／更新本資料夾 `all_json.csv`（與 yao guang 版 viewer 行為一致時） |
| **`all_skill_silder.txt`** | **`regen_all_skill_silder.py`** 依**當時** `all_json.csv` 內 Lv1 HTML 產生 a 編號 | 改 CSV 後應重跑腳本或在 viewer 儲存流程中覆寫 |
| **`skill_slider_script.js`** | **目前自 `yao guang/skill_slider_script.js` 複製**（歡愉開拓者參考用矩陣） | **數值未必等同** 8010 Stelle 最終倍率；請以 **HH／遊戲內** 或自算表為準再改 |
| **desc_lv2～15、tier2、tier3** | **手動**或 **HH**／其他資料管道補齊 | Gachabase 單頁通常不足以還原全套等級表 |
| **圖片** | `download_img.py`＋Gachabase／專案既有規則 | 同其他角色資料夾 |
| **`verify_stelle_gachabase.py`** | 即時 **GET** `link.txt` 第一行並解析，對照**本機** CSV／js／txt | 僅驗證結構與連線能抓到頁面，不保證遊戲數值最新 |

**第三方網站聲明：** Gachabase 等非米哈遊官方；**以遊戲內實測與你維護的 CSV／JS 為準**。

## 專用腳本

| 檔案 | 說明 |
|------|------|
| `bootstrap_gachabase_csv.py` | 依 `link.txt` 從 Gachabase 產生 **Lv1**；**自動**從 URL 取角色 ID、`trace-{ID}xxx`、有無 **Elation**（`skill-type-14`） |
| `regen_all_skill_silder.py` | 依目前 `all_json.csv` 無頭產生 `all_skill_silder.txt` |
| `verify_stelle_gachabase.py` | 對照 Gachabase 與 CSV／slider／silder 是否齊備 |

## 建議操作順序

1. `py verify_stelle_gachabase.py`
2. `py download_img.py`（圖檔寫入專案共用 `img` 等，與其他角色相同）
3. `py skill_viewer.py` → **載入角色資料** → 確認面板與總表
4. 若 Gachabase 改版後要重跑 CSV 骨架：`py bootstrap_gachabase_csv.py`，再視需要手動補 `desc_lv2`～`15` 與 `tier2`／`tier3`

其餘說明見同資料夾 `HH_extraction_guide.md`、`trace_tiers_supplement.example.json`（用檔名 `trace_tiers_supplement.json` 才會合併）。
