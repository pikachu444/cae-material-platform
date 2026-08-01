(() => {
  const workspace = document.querySelector("[data-region='workspace']");
  const navigatorPane = document.querySelector("[data-region='navigator']");
  const navigatorDivider = document.querySelector("[data-region='navigator-divider']");
  const overviewAside = document.querySelector('.overview-aside');
  const root = document.documentElement;

  if (!workspace || !navigatorPane || !navigatorDivider || !overviewAside) return;

  const readWidth = (element) => Math.round(element.getBoundingClientRect().width);
  const workspaceWidth = readWidth(workspace);
  const dividerWidth = readWidth(navigatorDivider);
  const asideWidth = readWidth(overviewAside);
  const compactMax = Math.min(360, Math.floor(workspaceWidth - dividerWidth - asideWidth - 720));

  navigatorDivider.setAttribute('aria-valuemin', '200');
  navigatorDivider.setAttribute('aria-valuemax', String(compactMax));
  root.style.setProperty('--navigator-width', '244px');
  navigatorDivider.setAttribute('aria-valuenow', String(readWidth(navigatorPane)));
})();
