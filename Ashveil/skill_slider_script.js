document.addEventListener("DOMContentLoaded", function() {
const sliderValues = {
a1: ["50%", "60%", "70%", "80%", "90%", "100%", "110%", "120%", "130%", "140%"],
a2: ["100%", "110%", "120%", "130%", "140%", "150%", "162.5%", "175%", "187.5%", "200%", "210%", "220%", "230%", "240%", "250%"],
a3: ["50%", "55%", "60%", "65%", "70%", "75%", "81.25%", "87.5%", "93.75%", "100%", "105%", "110%", "115%", "120%", "125%"],
a4: ["1", "1", "1", "1", "1", "1", "1", "1", "1", "1", "1", "1", "1", "1", "1"],
a5: ["20%", "22%", "24%", "26%", "28%", "30%", "32.5%", "35%", "37.5%", "40%", "42%", "44%", "46%", "48%", "50%"],
a6: ["200%", "220%", "240%", "260%", "280%", "300%", "325%", "350%", "375%", "400%", "420%", "440%", "460%", "480%", "500%"],
a7: ["4", "4", "4", "4", "4", "4", "4", "4", "4", "4", "4", "4", "4", "4", "4"],
a8: ["3", "3", "3", "3", "3", "3", "3", "3", "3", "3", "3", "3", "3", "3", "3"],
a9: ["100%", "110%", "120%", "130%", "140%", "150%", "162.5%", "175%", "187.5%", "200%", "210%", "220%", "230%", "240%", "250%"],
a10: ["3", "3", "3", "3", "3", "3", "3", "3", "3", "3", "3", "3", "3", "3", "3"],
a11: ["2", "2", "2", "2", "2", "2", "2", "2", "2", "2", "2", "2", "2", "2", "2"],
a12: ["3", "3", "3", "3", "3", "3", "3", "3", "3", "3", "3", "3", "3", "3", "3"],
a13: ["8", "8", "8", "8", "8", "8", "8", "8", "8", "8", "8", "8", "8", "8", "8"],
a14: ["1", "1", "1", "1", "1", "1", "1", "1", "1", "1", "1", "1", "1", "1", "1"],
a15: ["100%", "110%", "120%", "130%", "140%", "150%", "162.5%", "175%", "187.5%", "200%", "210%", "220%", "230%", "240%", "250%"],
a16: ["2", "2", "2", "2", "2", "2", "2", "2", "2", "2", "2", "2", "2", "2", "2"],
a17: ["12", "12", "12", "12", "12", "12", "12", "12", "12", "12", "12", "12", "12", "12", "12"]
};

const sliderConfigs = [
  { sliderId: "base-level-slider", valueElementId: "normalatk-value", scope: "#normalatk" },
  { sliderId: "skill-level-slider", valueElementId: "skill-value", scope: "#skill-level" },
  { sliderId: "ultimate-level-slider", valueElementId: "ultimate-value", scope: "#ultimate-level" },
  { sliderId: "talent-level-slider", valueElementId: "talent-value", scope: "#talent-level" }
];

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
