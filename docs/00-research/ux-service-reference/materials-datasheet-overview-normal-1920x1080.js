(() => {
  const navigatorPane = document.querySelector("[data-region='navigator']");
  const navigatorDivider = document.querySelector("[data-region='navigator-divider']");
  if (!navigatorPane || !navigatorDivider) return;
  navigatorDivider.setAttribute("aria-valuemin", "200");
  navigatorDivider.setAttribute("aria-valuemax", "360");
  navigatorDivider.setAttribute("aria-valuenow", String(Math.round(navigatorPane.getBoundingClientRect().width)));
})();
