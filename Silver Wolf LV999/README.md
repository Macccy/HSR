# Silver Wolf LV.999（1506）

Gachabase：`https://hsr.gachabase.net/characters/1506/silver-wolf-lvunbreak999unbreak/beta?lang=en`

頁面標題為 **Silver Wolf LV.999**；本資料夾名 **`Silver Wolf LV999`**，與 repo 內舊有 **`silver wolf`**（不同版本／路徑）請勿混淆。

流程與 `Stelle Elation` 相同（含 **Elation Skill**、`elation-level-slider`）。

## 目前資料的來源（截至本頁所描述之流程）

| 資料／檔案 | 主要來源 | 補充 |
|------------|----------|------|
| 角色頁 URL、`link.txt` | [Gachabase](https://hsr.gachabase.net) 本角色頁 | 非官方 |
| **`bootstrap_gachabase_csv.py`** → **`all_json.csv`（Lv1）** | 同上 **HTML**（`skill-type-*`、`trace-1506xxx`） | 自動解析 ID **1506** |
| **`skill_viewer`**「載入角色資料」 | **Gachabase HTML** | 可能寫回 CSV |
| **`all_skill_silder.txt`** | **`regen_all_skill_silder.py`** | |
| **`skill_slider_script.js`** | 自 **`yao guang`** 複製之範本 | 請依本角色再調 |
| **全等等級、tier2／3** | **手動**或 **HH** | |
| **驗證** | **`py verify_gachabase.py`** | |

**第三方非官方；以遊戲內與你維護的 CSV／JS 為準。**

## 建議操作順序

1. `py verify_gachabase.py`
2. `py download_img.py`
3. `py skill_viewer.py` → **載入角色資料**
4. 需重跑骨架：`py bootstrap_gachabase_csv.py`

其餘見 `HH_extraction_guide.md`、`trace_tiers_supplement.example.json`。
