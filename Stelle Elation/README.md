# Stelle Elation（8010，開拓者・記憶）— 歡愉命途

Gachabase：`https://hsr.gachabase.net/characters/8010/stelle-elation/beta?lang=en`

此資料夾與 `yao guang`／`Ashveil` 流程對齊；角色具 **Elation Skill** 欄位，HTML 滑條腳本含 `elation-level-slider`（可先沿用 `yao guang/skill_slider_script.js` 的結構，再依遊戲／HH 微調數值）。

## 專用腳本

| 檔案 | 說明 |
|------|------|
| `bootstrap_gachabase_csv.py` | 依 `link.txt` 從 Gachabase 產生 **Lv1** 技能／行跡 HTML 至 `all_json.csv`（全等等級請再用 HH 或手動補） |
| `regen_all_skill_silder.py` | 依目前 `all_json.csv` 無頭產生 `all_skill_silder.txt` |
| `verify_stelle_gachabase.py` | 對照 Gachabase 與 CSV／slider／silder 是否齊備 |

## 建議操作順序

1. `py verify_stelle_gachabase.py`
2. `py download_img.py`（圖檔寫入專案共用 `img` 等，與其他角色相同）
3. `py skill_viewer.py` → **載入角色資料** → 確認面板與總表
4. 若 Gachabase 改版後要重跑 CSV 骨架：`py bootstrap_gachabase_csv.py`，再視需要手動補 `desc_lv2`～`15` 與 `tier2`／`tier3`

其餘說明見同資料夾 `HH_extraction_guide.md`、`trace_tiers_supplement.example.json`（用檔名 `trace_tiers_supplement.json` 才會合併）。
