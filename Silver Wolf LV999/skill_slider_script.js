document.addEventListener("DOMContentLoaded", function() {
const sliderValues = {
a1: ["45%", "54%", "63%", "72%", "81%", "90%", "99%", "108%", "117%", "126%"],
a2: ["15%", "18%", "21%", "24%", "27%", "30%", "33%", "36%", "39%", "42%"],
a3: ["3", "3", "3", "3", "3", "3", "3", "3", "3", "3", "3", "3", "3", "3", "3"],
a4: ["10.0%", "11.0%", "12.0%", "13.0%", "14.0%", "15.0%", "16.2%", "17.5%", "18.8%", "20.0%", "21.0%", "22.0%", "23.0%", "24.0%", "25.0%"],
a5: ["3", "3", "3", "3", "3", "3", "3", "3", "3", "3", "3", "3", "3", "3", "3"],
a6: ["5", "5", "5", "5", "5", "5", "5", "5", "5", "5", "5", "5", "5", "5", "5"],
a7: ["20", "20", "20", "20", "20", "20", "20", "20", "20", "20", "20", "20", "20", "20", "20"],
a8: ["10.0%", "11.0%", "12.0%", "13.0%", "14.0%", "15.0%", "16.2%", "17.5%", "18.8%", "20.0%", "21.0%", "22.0%", "23.0%", "24.0%", "25.0%"],
a9: ["3", "3", "3", "3", "3", "3", "3", "3", "3", "3", "3", "3", "3", "3", "3"],
a10: ["10.0%", "11.0%", "12.0%", "13.0%", "14.0%", "15.0%", "16.2%", "17.5%", "18.8%", "20.0%", "21.0%", "22.0%", "23.0%", "24.0%", "25.0%"],
a11: ["3", "3", "3", "3", "3", "3", "3", "3", "3", "3", "3", "3", "3", "3", "3"],
a12: ["16.0%", "16.0%", "16.0%", "16.0%", "16.0%", "16.0%", "16.0%", "16.0%", "16.0%", "16.0%", "16.0%", "16.0%", "16.0%", "16.0%", "16.0%"],
a13: ["50%", "55%", "60%", "65%", "70%", "75%", "81%", "88%", "94%", "100%", "105%", "110%", "115%", "120%", "125%"],
a14: ["5", "5", "5", "5", "5", "5", "5", "5", "5", "5", "5", "5", "5", "5", "5"],
a15: ["10%", "11%", "12%", "13%", "14%", "15%", "16%", "18%", "19%", "20%", "21%", "22%", "23%", "24%", "25%"]
};

// 每個滑條的設定：sliderId、顯示等級的 element id、該技能區塊的 scope（在此區塊內動態找 a1, a2, ...）
const sliderConfigs = [
  { sliderId: "base-level-slider", valueElementId: "normalatk-value", scope: "#normalatk" },
  { sliderId: "skill-level-slider", valueElementId: "skill-value", scope: "#skill-level" },
  { sliderId: "ultimate-level-slider", valueElementId: "ultimate-value", scope: "#ultimate-level" },
  { sliderId: "talent-level-slider", valueElementId: "talent-value", scope: "#talent-level" },
  { sliderId: "elation-level-slider", valueElementId: "elation-value", scope: "#elation-level" }
];

/** 依 scope 在 DOM 內找出該區塊所有 [id^="a"] 的 id，依數字排序回傳（例如 ["a1","a2","a10"]） */
function getAXIdsInScope(scopeSelector) {
  const scope = document.querySelector(scopeSelector);
  if (!scope) return [];
  const nodes = scope.querySelectorAll("[id^='a']");
  const ids = [];
  nodes.forEach(function (el) {
    const id = el.id;
    if (/^a\d+$/.test(id)) ids.push(id);
  });
  ids.sort(function (a, b) {
    return parseInt(a.slice(1), 10) - parseInt(b.slice(1), 10);
  });
  return ids;
}

/** 依 DOM 動態建立 sliderId -> { values, scope }，每個技能區塊內有幾個 aX 就對應幾個 */
function buildSliderIdToAXMap() {
  const map = {};
  sliderConfigs.forEach(function (cfg) {
    const scope = document.querySelector(cfg.scope);
    if (!scope) return;
    const values = getAXIdsInScope(cfg.scope);
    if (values.length === 0) return;
    map[cfg.sliderId] = { values: values, scope: cfg.scope };
  });
  return map;
}

let sliderIdToAXMap = {};

function updateValueDisplay(slider, valueElement) {
  const config = sliderIdToAXMap[slider.id];
  if (!config) return;
  const { values, scope } = config;

  valueElement.textContent = slider.value;

  values.forEach(function (attribute) {
    const valueDisplay = document.querySelector(scope + " #" + attribute);
    if (valueDisplay && sliderValues[attribute]) {
      const value = sliderValues[attribute][slider.value - 1] || sliderValues[attribute][0];
      valueDisplay.innerHTML = "<b><em style=\"color:#ffffff\">" + value + "</em></b>";
    }
  });
}

function initSliders() {
  sliderIdToAXMap = buildSliderIdToAXMap();

  sliderConfigs.forEach(function (cfg) {
    const slider = document.getElementById(cfg.sliderId);
    const valueEl = document.getElementById(cfg.valueElementId);
    if (!slider || !valueEl || !sliderIdToAXMap[cfg.sliderId]) return;

    slider.addEventListener("input", function () {
      updateValueDisplay(slider, valueEl);
    });
    updateValueDisplay(slider, valueEl);
  });
}

initSliders();
});
