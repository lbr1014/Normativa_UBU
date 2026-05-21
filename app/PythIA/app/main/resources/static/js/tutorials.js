(() => {
  const startButtonId = "pythia-tour-start";
  const floatingButtonId = "pythia-tour-fab";

  function t(key, params) {
    try {
      return window.pythiaTranslate ? window.pythiaTranslate(key, params) : key;
    } catch {
      return key;
    }
  }

  function getEndpoint() {
    return document.body?.dataset?.endpoint || "";
  }

  function elementExists(selector) {
    try {
      return Boolean(document.querySelector(selector));
    } catch {
      return false;
    }
  }

  function showToast(message, variant = "warning") {
    const container = document.getElementById("pythia-toast-container");
    if (!container) return;

    const toastEl = document.createElement("div");
    toastEl.className = `toast align-items-center text-bg-${variant} border-0`;
    toastEl.setAttribute("role", "alert");
    toastEl.setAttribute("aria-live", "assertive");
    toastEl.setAttribute("aria-atomic", "true");

    toastEl.innerHTML = `
      <div class="d-flex">
        <div class="toast-body">${String(message)}</div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="${t("common.close")}"></button>
      </div>
    `;

    container.appendChild(toastEl);
    const toast = window.bootstrap?.Toast ? window.bootstrap.Toast.getOrCreateInstance(toastEl, { delay: 5000 }) : null;
    toast?.show();
    if (!toast) {
      toastEl.classList.add("show");
      setTimeout(() => toastEl.remove(), 5500);
    }
  }

  function buildMenuSteps() {
    const steps = [
      {
        element: `#${startButtonId}`,
        popover: { title: t("tutorial.start.title"), description: t("tutorial.start.desc"), side: "left", align: "start" },
      },
      {
        element: "#nav-home",
        popover: { title: t("tutorial.nav.home.title"), description: t("tutorial.nav.home.desc"), side: "left", align: "start" },
      },
      {
        element: "#nav-history",
        popover: { title: t("tutorial.nav.history.title"), description: t("tutorial.nav.history.desc"), side: "left", align: "start" },
      },
      {
        element: "#nav-profile",
        popover: { title: t("tutorial.nav.profile.title"), description: t("tutorial.nav.profile.desc"), side: "left", align: "start" },
      },
      {
        element: "#nav-stats",
        popover: { title: t("tutorial.nav.stats.title"), description: t("tutorial.nav.stats.desc"), side: "left", align: "start" },
      },
      {
        element: "#nav-docs",
        popover: { title: t("tutorial.nav.docs.title"), description: t("tutorial.nav.docs.desc"), side: "left", align: "start" },
      },
      {
        element: "#nav-users",
        popover: { title: t("tutorial.nav.users.title"), description: t("tutorial.nav.users.desc"), side: "left", align: "start" },
      },
      {
        element: "#nav-theme",
        popover: { title: t("tutorial.nav.theme.title"), description: t("tutorial.nav.theme.desc"), side: "left", align: "start" },
      },
      {
        element: "#nav-i18n",
        popover: { title: t("tutorial.nav.i18n.title"), description: t("tutorial.nav.i18n.desc"), side: "left", align: "start" },
      },
      {
        element: "#nav-logout",
        popover: { title: t("tutorial.nav.logout.title"), description: t("tutorial.nav.logout.desc"), side: "left", align: "start" },
      },
    ];

    return steps.filter((step) => elementExists(step.element));
  }

  function buildPageSteps(endpoint) {
    const perPage = {};

    const steps = perPage[endpoint] ? [...perPage[endpoint]] : [];

    if (endpoint === "main.pag_principal") {
      const homeSteps = [
        {
          element: "#nav-logo-home",
          popover: { title: t("tutorial.home.logo.title"), description: t("tutorial.home.logo.desc"), side: "bottom", align: "start" },
        },
        {
          element: "#nav-open-menu",
          popover: { title: t("tutorial.home.menu.title"), description: t("tutorial.home.menu.desc"), side: "bottom", align: "start" },
        },
        {
          element: "#home-rag-card",
          popover: { title: t("tutorial.home.rag.title"), description: t("tutorial.home.rag.desc"), side: "bottom", align: "start" },
        },
      ];

      return homeSteps.filter((step) => elementExists(step.element));
    }

    steps.push({
      element: "main.app-main-shell",
      popover: { title: t("tutorial.screen_overview.title"), description: t("tutorial.screen_overview.desc"), side: "bottom", align: "start" },
    });

    return steps.filter((step) => elementExists(step.element));
  }

  function startTour(options = {}) {
    const { includeMenu = true } = options;
    const createDriver =
      (window.driver && window.driver.js && typeof window.driver.js.driver === "function" && window.driver.js.driver) ||
      (window.driverjs && typeof window.driverjs.driver === "function" && window.driverjs.driver) ||
      (typeof window.driver === "function" && window.driver) ||
      (typeof window.Driver === "function" && window.Driver) ||
      null;
    if (!createDriver) {
      console.warn(t("tutorial.error.no_driver"));
      showToast(t("tutorial.error.no_driver"), "danger");
      return;
    }

    const endpoint = getEndpoint();
    const steps = includeMenu ? buildMenuSteps() : buildPageSteps(endpoint);
    if (!steps.length) {
      showToast(t("tutorial.error.no_steps"), "warning");
      return;
    }

    const driver = createDriver({
      showProgress: true,
      allowClose: true,
      animate: true,
      steps,
      nextBtnText: t("tutorial.next"),
      prevBtnText: t("tutorial.prev"),
      doneBtnText: t("tutorial.done"),
      progressText: t("tutorial.progress"),
    });

    driver.drive();
  }

  function wireButton() {
    const btn = document.getElementById(startButtonId);
    if (!btn) return;
    btn.addEventListener("click", () => {
      startTour({ includeMenu: true });
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    wireButton();
    const fab = document.getElementById(floatingButtonId);
    if (fab) {
      try {
        window.bootstrap?.Tooltip?.getOrCreateInstance(fab);
      } catch {
        // noop
      }
      fab.addEventListener("click", () => startTour({ includeMenu: false }));
    }
  });
})();
