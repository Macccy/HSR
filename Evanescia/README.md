# Evanescia（1505）

Gachabase：`https://hsr.gachabase.net/characters/1505/evanescia/beta?lang=en`

流程與 `Stelle Elation` 資料夾相同（含 **Elation Skill**、`elation-level-slider`）。

## 目前資料的來源（截至本頁所描述之流程）

| 資料／檔案 | 主要來源 | 補充 |
|------------|----------|------|
| 角色頁 URL、`link.txt` | [Gachabase](https://hsr.gachabase.net) 本角色頁 | 非官方；與正式服可能有落差 |
| **`bootstrap_gachabase_csv.py`** 產生的 **`all_json.csv`（Lv1）** | 同上頁 **HTML**（`skill-type-*`、`trace-1505xxx`） | 自動依 URL 解析角色 ID **1505**；不含 Lv2～15 |
| **`skill_viewer`**「載入角色資料」 | **Gachabase HTML**（基礎值、星魂、tier1、Ddesc 等） | 可能寫回 `all_json.csv` |
| **`all_skill_silder.txt`** | **`regen_all_skill_silder.py`** 依當時 CSV | 改 CSV 後請重跑 |
| **`skill_slider_script.js`** | 自 **`yao guang`** 複製之歡愉／多區塊範本 | 數值務必再以 **遊戲／HH** 核對 |
| **全等等級、tier2／3** | **手動**或 **HH** 等 | |
| **驗證** | **`py verify_gachabase.py`**（即時抓 `link.txt` URL） | |

**第三方非官方；以遊戲內與你維護的 CSV／JS 為準。**

## 建議操作順序

1. `py verify_gachabase.py`
2. `py download_img.py`
3. `py skill_viewer.py` → **載入角色資料**
4. 需重跑骨架：`py bootstrap_gachabase_csv.py`，再補齊多級與 tier

其餘見 `HH_extraction_guide.md`、`trace_tiers_supplement.example.json`。
