(() => {
  const navigatorPane = document.querySelector("[data-region='navigator']");
  const contextPane = document.querySelector("[data-region='selected-context']");
  const navigatorSplitter = document.querySelector("[data-region='navigator-divider']");
  const contextSplitter = document.querySelector("[data-region='context-divider']");

  if (!navigatorPane || !contextPane || !navigatorSplitter || !contextSplitter) return;

  const readWidth = (element) => Math.round(element.getBoundingClientRect().width);
  navigatorSplitter.setAttribute("aria-valuenow", String(readWidth(navigatorPane)));
  contextSplitter.setAttribute("aria-valuenow", String(readWidth(contextPane)));
})();
