# 技能資料提取指南（多來源版）

> 目標：從遊戲資料網站手動提取角色技能資料，  
> 產出三個檔案：`all_skill_silder.txt`、`all_json.csv`、`skill_slider_script.js`

---

## 〇、資料來源一覽

| 來源 | URL 格式 | 優點 | 缺點 |
|------|----------|------|------|
| **Honey Hunter World (HH)** | `https://starrail.honeyhunterworld.com/{slug}-character/?lang=EN` | 有完整等級數值表（1~15 級一覽） | 描述中數值顯示為**空白**（JS 動態填入）；欄位順序可能與描述不同 |
| **Gachabase** | `https://hsr.gachabase.net/characters/{id}/{slug}/beta?lang=en` | 描述中數值**直接顯示**；有等級滑條可即時切換 | 一次只顯示一個等級，無法一覽全部等級 |

### 推薦工作流程

1. **先用 Gachabase** 取得完整技能描述文字（數值可見，方便建立模板）
2. **再用 HH** 取得所有等級的完整數值表（一次看齊 1~15 級）
3. **用 Gachabase 交叉驗證**：切換到特定等級，確認數值正確

---

## 一、三個輸出檔案的用途

| 檔案 | 用途 | 格式特徵 |
|------|------|----------|
| `all_skill_silder.txt` | HTML 模板，數值位置用 `<span id="aX">` 佔位 | 純文字 + HTML span，**不含**實際數字 |
| `all_json.csv` | 每個技能的完整描述（15 等級），數值已填入 | CSV，含 `desc_lv1`~`desc_lv15` 和 `raw_html_lv1`~`raw_html_lv15` |
| `skill_slider_script.js` | 驅動滑條的 JavaScript，每個 `aX` 對應一組陣列 | JS，`sliderValues` 物件 |

---

## 二、網站頁面結構分析

### Gachabase 頁面

以 Yao Guang 為例：`https://hsr.gachabase.net/characters/1502/yao-guang/beta?lang=en`

頁面直接顯示各技能描述（數值可見），包含：
- **Skills 區段**：Basic ATK / Skill / Ultimate / Talent / Technique / Elation Skill
- **Traces 區段**：Amaze-In Grace (A2) / Poised and Sated (A4) / Felicity Ensemble (A6) + 小型數值加成
- **Eidolons 區段**：星魂 1~6 的效果描述

每個技能有等級標示（如 `Lv. 10`），描述中的**高亮數字**就是該等級的實際數值。

### Honey Hunter World 頁面

以 Yao Guang 為例：`https://starrail.honeyhunterworld.com/yao-guang-character/?lang=EN`

頁面 **Skill** 區段包含以下技能，每個技能下方都有一個**等級數值表**：

| 技能類型 | 技能名稱 | 表格欄位 | 等級數 |
|----------|----------|----------|--------|
| Basic ATK | Whistlebolt Sings Joy | A, B | Lv.1~10 |
| Skill | Decalight Unveils All | A, B, C | Lv.1~15 |
| Ultimate | Hexagram of Feathered Fortune | A, B, C, D, E | Lv.1~15 |
| Talent | Behold Wherever Light Unfolds | A | Lv.1~15 |
| Technique | Untethered Glimmer Sails Far | A | Lv.1（僅一級） |
| Elation Skill | Let Thy Fortune Burst in Flames | A, B, C, D, E, F | Lv.1~15 |

此外，**Traces** 區段包含三個被動 Trace（對應 Adesc、Bdesc、Cdesc），各只有一個等級。

---

## 三、關鍵概念：欄位 (A/B/C...) 與模板變數 (aX) 的對應

### 核心原則

HH 網站的表格欄位（A, B, C...）對應技能描述中**按順序出現的變數位置**，但**欄位順序不一定等於描述中變數出現的順序**！

你必須透過以下方式手動比對：

1. 閱讀 HH 的技能描述文字（會有空白處，代表數值被省略）
2. 查看等級表的第一行數值（Lv.1）
3. 將每個數值代入描述的空白處，確認對應關係

### Yao Guang 完整對應表

#### Basic ATK（a1~a2，10 等級）

| HH 欄位 | 模板變數 | 說明 | Lv.1 值 | Lv.10 值 |
|----------|----------|------|---------|----------|
| A | a1 | 主目標 ATK 傷害% | 45% | 126% |
| B | a2 | 鄰接目標 ATK 傷害% | 15% | 42% |

#### Skill（a3~a5，15 等級）

| HH 欄位 | 模板變數 | 說明 | Lv.1 值 | Lv.15 值 |
|----------|----------|------|---------|----------|
| A | a3 | Zone 持續回合數 | 3 | 3（固定） |
| B | a4 | Elation 增加% | 10% | 25% |
| C | a5 | Punchline 獲得數 | 3 | 3（固定） |

#### Ultimate（a6~a9，15 等級）

| HH 欄位 | 模板變數 | 說明 | Lv.1 值 | Lv.15 值 |
|----------|----------|------|---------|----------|
| A | a6 | 獲得 Punchline 數 | 5 | 5（固定） |
| B | a8 | All-Type RES PEN% | 10% | 25% |
| C | a9 | RES PEN 持續回合 | 3 | 3（固定） |
| D | a7 | 固定 Punchline 結算量 | 20 | 20（固定） |
| E | *(無對應)* | 額外回合數（固定 1，已硬編碼在模板中） | 1 | 1 |

> **注意**：HH 欄位 B/C/D 的順序與模板變數 a7/a8/a9 的順序**不同**！  
> 必須根據描述文字中的語境來配對，而非盲目按順序。

#### Talent（a10，15 等級）

| HH 欄位 | 模板變數 | 說明 | Lv.1 值 | Lv.15 值 |
|----------|----------|------|---------|----------|
| A | a10 | Elation DMG% | 10% | 25% |

#### Elation Skill（a11~a15，15 等級）

| HH 欄位 | 模板變數 | 說明 | Lv.1 值 | Lv.15 值 |
|----------|----------|------|---------|----------|
| A | *(無對應)* | HH 內部用（常數 1） | 1 | 1 |
| B | a13 | 全體 Physical Elation DMG% | 50% | 125% |
| C | a12 | Woe's Whisper 受傷增加% | 16% | 16%（固定） |
| D | a11 | Woe's Whisper 持續回合 | 3 | 3（固定） |
| E | a14 | 隨機單體傷害次數 | 5 | 5（固定） |
| F | a15 | 每次隨機傷害 DMG% | 10% | 25% |

> **注意**：HH 欄位 A 不對應任何模板變數。欄位 B~F 的順序也與 a11~a15 不同。

---

## 四、逐步提取流程

### Step 1：提取技能描述模板 → `all_skill_silder.txt`

1. 前往 HH 角色頁面的 **Skill** 區段
2. 對每個技能，複製其描述文字
3. 找出描述中所有**被高亮/變數化的數值**位置
4. 將這些數值替換為 `<span style="color: #f29e38ff;"><span id="aX">&nbsp;</span></span>`
5. **aX 的編號是連續的**，從 a1 開始，按照技能出現順序和描述中變數出現順序遞增

範例（Basic ATK）：
```
原文：Deals Physical DMG equal to 45% of Yao Guang's ATK to one designated enemy...
模板：Deals Physical DMG equal to <span style="color: #f29e38ff;"><span id="a1">&nbsp;</span></span> of Yao Guang's ATK to one designated enemy...
```

技能排列順序與 aX 分配：
```
Basic ATK  → a1, a2
Skill      → a3, a4, a5
Ultimate   → a6, a7, a8, a9
Talent     → a10
Elation Skill → a11, a12, a13, a14, a15
```

### Step 2：提取等級數值表 → `skill_slider_script.js`

1. 對每個技能的等級表，逐欄抄錄所有等級的數值
2. 確定每個 HH 欄位對應的 `aX` 變數（參照第三節的對應表）
3. 將數值寫入 `sliderValues` 物件

提取方式：

```
以 Basic ATK 為例，HH 表格顯示：

Lv | A    | B
1  | 45%  | 15%
2  | 54%  | 18%
...
10 | 126% | 42%

對應到 JS：
a1: ["45%", "54%", "63%", "72%", "81%", "90%", "99%", "108%", "117%", "126%"]
a2: ["15%", "18%", "21%", "24%", "27%", "30%", "33%", "36%", "39%", "42%"]
```

**注意事項**：
- Basic ATK 有 **10** 個等級，陣列長度 10
- Skill / Ultimate / Talent / Elation Skill 有 **15** 個等級，陣列長度 15
- Technique 只有 1 個等級，**不需要**放入 sliderValues
- 固定不變的數值（如 Zone 持續 3 回合）也要放入陣列，只是每個元素都一樣

### Step 3：組合完整描述 → `all_json.csv`

CSV 欄位結構：
```
type,name,title,desc_lv1,...,desc_lv15,raw_html_lv1,...,raw_html_lv15
```

| 欄位 | 說明 |
|------|------|
| type | 技能類型：Basic ATK / Skill / Ultimate / Technique / Elation Skill / Talent / Adesc / Bdesc / Cdesc / Ddesc |
| name | 技能英文名稱（從 HH 頁面取得） |
| title | 技能分類標籤：Blast / Support / AoEAttack / ASCEND CALCULATOR A~D 等 |
| desc_lv1~15 | 將模板中的 `<span id="aX">` 替換為**該等級的實際數值**（帶 span style 色彩標記） |
| raw_html_lv1~15 | 與 desc 相同內容（目前兩組欄位填入一樣的值） |

組合方式：
```
取模板：Deals Physical DMG equal to <span style="color: #f29e38ff;"><span id="a1">&nbsp;</span></span>...

Lv.1 → 將 <span id="a1">&nbsp;</span> 替換為 45%：
  Deals Physical DMG equal to <span style=""color: #f29e38ff;"">45%</span>...

Lv.2 → 替換為 54%：
  Deals Physical DMG equal to <span style=""color: #f29e38ff;"">54%</span>...
```

**CSV 特殊處理**：
- 描述中的雙引號 `"` 在 CSV 中需要轉義為 `""`
- 每個描述欄位用雙引號包裹
- 換行符 `\n` 保持為字面字串（如 Talent 描述中的多段文字）

### Step 4：提取被動 Trace → CSV 的 Adesc/Bdesc/Cdesc/Ddesc

從 HH 頁面的 **Traces** 區段取得三個被動 Trace：

| CSV type | 對應 HH Trace | 說明 |
|----------|--------------|------|
| Adesc | Ascension 2 被動 | 第一個主要被動技能 |
| Bdesc | Ascension 4 被動 | 第二個主要被動技能 |
| Cdesc | Ascension 6 被動 | 第三個主要被動技能 |
| Ddesc | Extra Attributes | 額外屬性（可能為空） |

這些被動只有 1 級，填入 `desc_lv1` 和 `raw_html_lv1`，其餘 lv2~15 留空。

---

## 五、HH 網頁上的資料定位（快速定位法）

### 技能描述文字
- 在每個技能名稱下方，有一段描述文字
- 其中的數值位置會**顯示為空白**（因為 HH 用 JavaScript 動態填入）
- 這就是模板文字的來源

### 等級數值表
- 每個技能下方有一個表格，標題欄為 `A | B | C... | Character Materials`
- 第一欄是等級數字（1~10 或 1~15）
- 後續欄位是該等級的各項數值
- 最後一欄是升級材料（**忽略不用**）

### 技能名稱和類型
- 格式：`[技能名稱] - 技能類型 | 攻擊模式`
- 例如：`Whistlebolt Sings Joy - Basic ATK | Blast`
- 技能名稱 → CSV 的 `name` 欄位
- 攻擊模式 → CSV 的 `title` 欄位

---

## 六、常見陷阱與注意事項

### 1. HH 欄位順序 ≠ 描述變數順序
最大的坑！HH 表格的 A/B/C 欄位順序可能與技能描述中變數出現的順序不同。  
**必須**通過 Lv.1 的具體數值手動比對描述來確認對應關係。  
**解決方法**：先在 Gachabase 查看 Lv.1 的描述（數值可見），再與 HH 表格 Lv.1 的 A/B/C 值逐一比對。

### 2. HH 可能有多餘欄位
例如 Elation Skill 的 A 欄（常數 1）在描述模板中沒有對應的佔位符。  
這些多餘欄位可以**忽略**，不需要放入 sliderValues。

### 3. HH 可能有額外欄位不在模板中
例如 Ultimate 的 E 欄（固定 1，代表額外回合數）在模板中已被硬編碼為字面文字。

### 4. 數值精度差異
HH 和 Gachabase 可能對同一數值有不同精度（如 `16.25%` vs `16.2%`）。  
以 HH 頁面顯示的精確數值為準，因為 HH 通常較精確。

### 5. Technique 只有 1 級
Technique 不需要滑條，只需放入 CSV 的 `desc_lv1`，不需加入 JS 的 `sliderValues`。

### 6. 被動 Trace（Adesc/Bdesc/Cdesc）中的數值
雖然只有 1 級，但描述中可能含有高亮數值（如 `120`、`30%`）。  
這些數值在 CSV 中直接以 `<span style=""color: #f29e38ff;"">120</span>` 格式寫入。  
不需要在 JS 中為它們建立 sliderValues（因為沒有滑條）。

### 7. Gachabase 的 Beta 標記
URL 中帶 `beta` 的頁面可能是未正式上線的角色資料。  
資料大致可靠但可能隨版本更新而微調，正式上線後建議再驗證一次。

### 8. Gachabase 的等級上限
Gachabase 預設顯示的最大等級：Basic ATK = Lv.6，其他技能 = Lv.10。  
Eidolon E3/E5 提供 +2 等級加成，最高可達 Lv.10/Lv.15。  
完整 15 級數值仍需從 HH 表格取得。

### 9. Gachabase 的額外元資料
Gachabase 還提供以下資訊（目前不需放入三個檔案，但可作參考）：

| 元資料 | 範例 | 位置 |
|--------|------|------|
| Energy Gen | Basic ATK: 30, Skill: 30, Ultimate: 5 | 每個技能下方 |
| Break (In-Game) | 10 (Single) / 5 (Blast) | 每個技能下方 |
| Skill Points | +1 / -1 / +0 | 每個技能下方 |
| Participant ID | Elation Skill: 116 | 部分技能下方 |
| 技能攻擊類型 | Blast / Support / AoE | 技能標題旁 |

---

## 七、驗證清單

- [ ] `all_skill_silder.txt` 中的 aX 編號連續且唯一
- [ ] `skill_slider_script.js` 中每個 aX 陣列長度正確（10 或 15）
- [ ] JS 中的 aX 值與 HH 表格完全一致
- [ ] CSV 中 lv1 描述代入 aX 的 lv1 值後，與 HH 描述一致
- [ ] CSV 中 lv15（或 lv10）描述代入最大等級值後，與 HH 描述一致
- [ ] HH 欄位到 aX 的對應關係經過手動驗證
- [ ] 被動 Trace 資料正確填入 Adesc/Bdesc/Cdesc
- [ ] CSV 的雙引號正確轉義

---

## 八、Yao Guang 完整 sliderValues 參考（從 HH 提取）

以下是從 HH 表格直接提取的正確數值：

```javascript
const sliderValues = {
  // Basic ATK (10 levels) - Whistlebolt Sings Joy
  a1: ["45%", "54%", "63%", "72%", "81%", "90%", "99%", "108%", "117%", "126%"],
  a2: ["15%", "18%", "21%", "24%", "27%", "30%", "33%", "36%", "39%", "42%"],

  // Skill (15 levels) - Decalight Unveils All
  a3: ["3", "3", "3", "3", "3", "3", "3", "3", "3", "3", "3", "3", "3", "3", "3"],
  a4: ["10%", "11%", "12%", "13%", "14%", "15%", "16.25%", "17.5%", "18.75%", "20%", "21%", "22%", "23%", "24%", "25%"],
  a5: ["3", "3", "3", "3", "3", "3", "3", "3", "3", "3", "3", "3", "3", "3", "3"],

  // Ultimate (15 levels) - Hexagram of Feathered Fortune
  // 注意：HH 欄位 A→a6, D→a7, B→a8, C→a9
  a6: ["5", "5", "5", "5", "5", "5", "5", "5", "5", "5", "5", "5", "5", "5", "5"],
  a7: ["20", "20", "20", "20", "20", "20", "20", "20", "20", "20", "20", "20", "20", "20", "20"],
  a8: ["10%", "11%", "12%", "13%", "14%", "15%", "16.25%", "17.5%", "18.75%", "20%", "21%", "22%", "23%", "24%", "25%"],
  a9: ["3", "3", "3", "3", "3", "3", "3", "3", "3", "3", "3", "3", "3", "3", "3"],

  // Talent (15 levels) - Behold Wherever Light Unfolds
  a10: ["10%", "11%", "12%", "13%", "14%", "15%", "16.25%", "17.5%", "18.75%", "20%", "21%", "22%", "23%", "24%", "25%"],

  // Elation Skill (15 levels) - Let Thy Fortune Burst in Flames
  // 注意：HH 欄位 A 忽略, D→a11, C→a12, B→a13, E→a14, F→a15
  a11: ["3", "3", "3", "3", "3", "3", "3", "3", "3", "3", "3", "3", "3", "3", "3"],
  a12: ["16%", "16%", "16%", "16%", "16%", "16%", "16%", "16%", "16%", "16%", "16%", "16%", "16%", "16%", "16%"],
  a13: ["50%", "55%", "60%", "65%", "70%", "75%", "81.25%", "87.5%", "93.75%", "100%", "105%", "110%", "115%", "120%", "125%"],
  a14: ["5", "5", "5", "5", "5", "5", "5", "5", "5", "5", "5", "5", "5", "5", "5"],
  a15: ["10%", "11%", "12%", "13%", "14%", "15%", "16.25%", "17.5%", "18.75%", "20%", "21%", "22%", "23%", "24%", "25%"]
};
```

> **已更新**：`skill_slider_script.js` 的 sliderValues 已修正為上方的正確數值（a1~a15）。  
> 舊的錯誤版本有 a1~a18，數值來自其他角色，已全部替換。

---

## 九、應用到新角色的通用步驟

1. **打開 Gachabase** `https://hsr.gachabase.net/characters/{id}/{slug}/beta?lang=en`
2. **複製** 每個技能的描述文字（Gachabase 數值直接顯示，不需猜測）
3. **識別** 描述中所有高亮數值的位置，建立 aX 編號
4. **打開 HH** `https://starrail.honeyhunterworld.com/{角色slug}-character/?lang=EN`
5. **從 HH 等級表**提取所有等級（1~15）的完整數值
6. **建立對應** HH 欄位 → 模板 aX 變數（用 Gachabase 的可見數值比對）
7. **編寫** `all_skill_silder.txt`（模板 + span 佔位符）
8. **編寫** `skill_slider_script.js`（填入 sliderValues）
9. **組合** `all_json.csv`（將每個等級的值代入模板生成完整描述）
10. **用 Gachabase 驗證**：切換到 Lv.1、Lv.6、Lv.10 等常見等級，確認數值吻合

---

## 十、Gachabase 詳細使用說明

### 頁面結構

Gachabase 的角色頁面分為以下區段：
- **Stats**：基礎數值（HP/ATK/DEF/SPD 等）
- **Skills**：所有技能描述，含等級滑條
- **Traces**：被動技能（含 Ascension 2/4/6 主要被動 + 小數值加成）
- **Eidolons**：星魂效果
- **Materials Calculator**：升級材料計算器

### 技能數值提取方法

每個技能標題旁有等級顯示（如 `Lv. 10`），下方描述中的**高亮數字**就是該等級的數值。

```
範例（Gachabase Skill Lv.10 顯示）：
Deploys a Zone for 3 turn(s)...
increases all allies' Elation by an amount equal to 20.0% of Yao Guang's Elation.
After Yao Guang uses Basic ATK or Skill, gains 3 Punchline.
```

高亮的 `3`、`20.0%`、`3` 就是 Lv.10 的三個變數值。

### Gachabase 優勢：直接讀取描述

相比 HH（數值為空白），Gachabase **直接顯示數值**，這解決了兩個問題：
1. 不需猜測哪些位置是變數（高亮的就是）
2. 描述文字可以直接複製作為模板基礎

### Gachabase 的限制

- **無完整等級表**：必須手動調整滑條才能看到不同等級的值
- **Beta 頁面**：URL 中的 `beta` 標記表示資料可能為測試版
- **等級範圍**：Basic ATK 預設最高 Lv.6（+E3 可到 Lv.10），其他技能預設最高 Lv.10（+E5 可到 Lv.15）

### 與 HH 搭配的最佳策略

| 步驟 | 用 Gachabase | 用 HH |
|------|-------------|-------|
| 取得描述模板文字 | ✅（數值可見） | ❌（數值為空白） |
| 識別高亮變數位置 | ✅（直觀） | ❌（需對比表格猜測） |
| 取得所有等級數值 | ❌（一次一級太慢） | ✅（完整表格一覽） |
| HH 欄位 → aX 對應 | ✅（用已知數值比對） | ❌（欄位順序可能不同） |
| 最終驗證 | ✅（切換等級確認） | ✅（看表格首尾行） |

---

## 十一、Yao Guang 交叉驗證結果（Gachabase vs HH vs CSV）

以下為從 Gachabase（Lv.10 / Lv.6）驗證現有資料的結果：

| 技能 | 變數 | Gachabase 值 | CSV 值 | 結果 |
|------|------|-------------|--------|------|
| Basic ATK Lv.6 | a1 | 90% | 90% | ✅ |
| Basic ATK Lv.6 | a2 | 30% | 30% | ✅ |
| Skill Lv.10 | a4 | 20.0% | 20.0% | ✅ |
| Ultimate Lv.10 | a6 | 5 | 5 | ✅ |
| Ultimate Lv.10 | a7 | 20 | 20 | ✅ |
| Ultimate Lv.10 | a8 | 20.0% | 20.0% | ✅ |
| Talent Lv.10 | a10 | 20.0% | 20.0% | ✅ |
| Elation Skill Lv.10 | a13 | 100% | 100% | ✅ |
| Elation Skill Lv.10 | a15 | 20% | 20% | ✅ |
| Trace Adesc | — | 120, 30%, 1, 1%, 200 | 120, 30%, 1, 1%, 200 | ✅ |
| Trace Bdesc | — | 60%, 1 | 60%, 1 | ✅ |
| Trace Cdesc | — | 1 | 1 | ✅ |

> **結論**：`all_json.csv` 的資料完全正確。`skill_slider_script.js` 的 sliderValues 已修正完畢。
