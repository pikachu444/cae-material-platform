(() => {
  const workspace = document.querySelector("[data-region='materials-workspace']");
  const navigatorPane = document.querySelector("[data-region='navigator']");
  const contextPane = document.querySelector("[data-region='selected-context']");
  const navigatorSplitter = document.querySelector("[data-region='navigator-divider']");
  const contextSplitter = document.querySelector("[data-region='context-divider']");
  const root = document.documentElement;
  const resultMinimum = 720;

  if (
    !workspace ||
    !navigatorPane ||
    !contextPane ||
    !navigatorSplitter ||
    !contextSplitter
  ) {
    return;
  }

  const minimum = {
    navigator: Number(navigatorSplitter.getAttribute("aria-valuemin")),
    context: Number(contextSplitter.getAttribute("aria-valuemin")),
  };
  const hardMaximum = { navigator: 360, context: 480 };
  const readWidth = (element) => Math.round(element.getBoundingClientRect().width);
  const clamp = (value, lower, upper) => Math.max(lower, Math.min(upper, value));
  const combinedPaneBudget = () =>
    Math.round(
      workspace.getBoundingClientRect().width -
        readWidth(navigatorSplitter) -
        readWidth(contextSplitter) -
        resultMinimum
    );
  const maxima = (navigatorWidth, contextWidth) => {
    const budget = combinedPaneBudget();
    return {
      navigator: Math.min(hardMaximum.navigator, budget - contextWidth),
      context: Math.min(hardMaximum.context, budget - navigatorWidth),
    };
  };

  const synchronizeAria = () => {
    const navigatorWidth = readWidth(navigatorPane);
    const contextWidth = readWidth(contextPane);
    const maximum = maxima(navigatorWidth, contextWidth);

    navigatorSplitter.setAttribute("aria-valuemin", String(minimum.navigator));
    navigatorSplitter.setAttribute("aria-valuemax", String(maximum.navigator));
    navigatorSplitter.setAttribute("aria-valuenow", String(navigatorWidth));
    contextSplitter.setAttribute("aria-valuemin", String(minimum.context));
    contextSplitter.setAttribute("aria-valuemax", String(maximum.context));
    contextSplitter.setAttribute("aria-valuenow", String(contextWidth));
  };

  const resize = (pane, key) => {
    const navigatorWidth = readWidth(navigatorPane);
    const contextWidth = readWidth(contextPane);
    const maximum = maxima(navigatorWidth, contextWidth);
    const splitter = pane === "navigator" ? navigatorSplitter : contextSplitter;
    const current = pane === "navigator" ? navigatorWidth : contextWidth;
    let next = current;

    if (key === "Home") {
      next = minimum[pane];
    } else if (key === "End") {
      next = maximum[pane];
    } else {
      const increase =
        (pane === "navigator" && key === "ArrowRight") ||
        (pane === "context" && key === "ArrowLeft");
      next = current + (increase ? 8 : -8);
    }

    root.style.setProperty(
      pane === "navigator" ? "--navigator-width" : "--context-width",
      `${clamp(next, minimum[pane], maximum[pane])}px`
    );
    synchronizeAria();
    splitter.focus();
  };

  document.addEventListener(
    "keydown",
    (event) => {
      if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
      const splitter = event.target.closest?.(".splitter");
      if (splitter !== navigatorSplitter && splitter !== contextSplitter) return;

      event.preventDefault();
      event.stopImmediatePropagation();
      resize(splitter === navigatorSplitter ? "navigator" : "context", event.key);
    },
    true
  );

  synchronizeAria();
})();
