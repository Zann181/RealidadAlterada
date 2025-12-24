(() => {
  const STORAGE_KEY = "theme";
  const SIDEBAR_KEY = "sidebar";
  const body = document.body;
  const toggle = document.getElementById("theme-toggle");
  const sidebarToggle = document.getElementById("sidebar-toggle");
  const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");

  const getInitialTheme = () => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "dark" || stored === "light") {
      return stored;
    }
    return "dark";
  };

  const applyTheme = (theme) => {
    body.classList.remove("theme-dark", "theme-light");
    body.classList.add(`theme-${theme}`);
    if (toggle) {
      toggle.setAttribute("aria-pressed", theme === "dark" ? "true" : "false");
      toggle.setAttribute(
        "aria-label",
        theme === "dark" ? "Cambiar a modo claro" : "Cambiar a modo oscuro"
      );
      toggle.title = theme === "dark" ? "Cambiar a modo claro" : "Cambiar a modo oscuro";
    }
  };

  const setTheme = (theme) => {
    localStorage.setItem(STORAGE_KEY, theme);
    applyTheme(theme);
  };

  const initialTheme = getInitialTheme();
  applyTheme(initialTheme);
  if (!localStorage.getItem(STORAGE_KEY)) {
    localStorage.setItem(STORAGE_KEY, initialTheme);
  }

  if (toggle) {
    toggle.addEventListener("click", () => {
      const isDark = body.classList.contains("theme-dark");
      setTheme(isDark ? "light" : "dark");
    });
  }

  if (!localStorage.getItem(STORAGE_KEY)) {
    mediaQuery.addEventListener("change", (event) => {
      const nextTheme = event.matches ? "dark" : "light";
      localStorage.setItem(STORAGE_KEY, nextTheme);
      applyTheme(nextTheme);
    });
  }

  const applySidebar = (collapsed) => {
    body.classList.toggle("sidebar-collapsed", collapsed);
    if (sidebarToggle) {
      sidebarToggle.setAttribute("aria-expanded", collapsed ? "false" : "true");
      sidebarToggle.setAttribute("aria-label", collapsed ? "Mostrar menu" : "Ocultar menu");
    }
  };

  const storedSidebar = localStorage.getItem(SIDEBAR_KEY);
  applySidebar(storedSidebar === "collapsed");

  if (sidebarToggle) {
    sidebarToggle.addEventListener("click", () => {
      const collapsed = !body.classList.contains("sidebar-collapsed");
      localStorage.setItem(SIDEBAR_KEY, collapsed ? "collapsed" : "expanded");
      applySidebar(collapsed);
    });
  }

  const toastContainer = document.querySelector("[data-toast-container]");

  const ensureToastContainer = () => {
    if (toastContainer) {
      return toastContainer;
    }
    const container = document.createElement("div");
    container.className = "messages messages-floating";
    container.setAttribute("data-toast-container", "");
    container.setAttribute("aria-live", "polite");
    container.setAttribute("aria-atomic", "true");
    document.body.appendChild(container);
    return container;
  };

  const dismissToast = (toast) => {
    toast.classList.add("is-hiding");
    toast.addEventListener(
      "transitionend",
      () => {
        toast.remove();
      },
      { once: true }
    );
  };

  const scheduleDismiss = (toast, delay) => {
    if (!delay) {
      return;
    }
    window.setTimeout(() => dismissToast(toast), delay);
  };

  const showToast = ({ message, variant = "info", actions = [], duration = 7000 }) => {
    const container = ensureToastContainer();
    const toast = document.createElement("div");
    toast.className = `alert ${variant}`;
    toast.setAttribute("role", "alert");
    toast.textContent = message;

    if (actions.length) {
      const actionsWrap = document.createElement("div");
      actionsWrap.className = "toast-actions";
      actions.forEach((action) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = action.className || "btn btn-outline btn-sm";
        button.textContent = action.label;
        button.addEventListener("click", () => {
          action.onClick();
          dismissToast(toast);
        });
        actionsWrap.appendChild(button);
      });
      toast.appendChild(actionsWrap);
    }

    container.appendChild(toast);
    scheduleDismiss(toast, duration);
    return toast;
  };

  document.querySelectorAll("[data-toast]").forEach((toast) => {
    scheduleDismiss(toast, 7000);
  });

  document.addEventListener("submit", (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement)) {
      return;
    }
    if (form.dataset.confirmed === "true") {
      return;
    }
    const message = form.dataset.confirm;
    if (!message) {
      return;
    }
    event.preventDefault();
    showToast({
      message,
      variant: "warning",
      actions: [
        { label: "Cancelar", className: "btn btn-outline btn-sm", onClick: () => {} },
        {
          label: "Confirmar",
          className: "btn btn-primary btn-sm",
          onClick: () => {
            form.dataset.confirmed = "true";
            form.submit();
          },
        },
      ],
      duration: 7000,
    });
  });

  let lastActiveElement = null;

  const openModal = (modal) => {
    if (!modal) {
      return;
    }
    lastActiveElement =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    modal.removeAttribute("hidden");
    modal.classList.add("is-open");
    modal.setAttribute("aria-hidden", "false");
    body.classList.add("modal-open");
    const focusTarget = modal.querySelector("input, select, textarea, button");
    if (focusTarget) {
      focusTarget.focus();
    }
  };

  const closeModal = (modal) => {
    if (!modal) {
      return;
    }
    modal.classList.remove("is-open");
    modal.setAttribute("aria-hidden", "true");
    modal.setAttribute("hidden", "");
    if (!document.querySelector(".modal.is-open")) {
      body.classList.remove("modal-open");
    }
    if (lastActiveElement && document.body.contains(lastActiveElement)) {
      lastActiveElement.focus();
    }
  };

  document.querySelectorAll("[data-modal-open]").forEach((trigger) => {
    trigger.addEventListener("click", () => {
      const selector = trigger.getAttribute("data-modal-open");
      const modal = selector ? document.querySelector(selector) : null;
      openModal(modal);
    });
  });

  document.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) {
      return;
    }
    const closeTrigger = target.closest("[data-modal-close]");
    if (closeTrigger) {
      const modal = closeTrigger.closest(".modal");
      closeModal(modal);
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") {
      return;
    }
    const modal = document.querySelector(".modal.is-open");
    if (modal) {
      closeModal(modal);
    }
  });

  if (document.querySelector(".modal.is-open")) {
    document.querySelectorAll(".modal.is-open").forEach((modal) => {
      modal.removeAttribute("hidden");
    });
    body.classList.add("modal-open");
  }

  const shouldFormatMiles = (input) => {
    if (!input || input.dataset.noMiles !== undefined) {
      return false;
    }
    const type = input.type;
    if (["date", "datetime-local", "time", "email", "password", "search", "url"].includes(type)) {
      return false;
    }
    if (type === "number") {
      return false;
    }
    const inputMode = input.getAttribute("inputmode");
    const pattern = input.getAttribute("pattern") || "";
    return inputMode === "numeric" || pattern.includes("[0-9");
  };

  const formatMilesValue = (value) => {
    if (!value) {
      return "";
    }
    const isNegative = String(value).trim().startsWith("-");
    const digits = String(value).replace(/\D/g, "");
    if (!digits) {
      return isNegative ? "-" : "";
    }
    const parts = [];
    let current = digits;
    while (current.length > 3) {
      parts.unshift(current.slice(-3));
      current = current.slice(0, -3);
    }
    parts.unshift(current);
    return `${isNegative ? "-" : ""}${parts.join(".")}`;
  };

  const formatMilesInput = (input) => {
    if (!shouldFormatMiles(input)) {
      return;
    }
    const raw = input.value;
    if (!raw) {
      return;
    }
    const selectionStart = input.selectionStart ?? raw.length;
    const cleaned = raw.replace(/\D/g, "");
    const formatted = formatMilesValue(raw);
    if (formatted === raw) {
      return;
    }
    input.value = formatted;
    const diff = formatted.length - cleaned.length;
    const nextPos = Math.min(formatted.length, Math.max(0, selectionStart + diff));
    input.setSelectionRange(nextPos, nextPos);
  };

  document.querySelectorAll("input").forEach((input) => {
    if (shouldFormatMiles(input)) {
      formatMilesInput(input);
    }
  });

  document.addEventListener("input", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLInputElement)) {
      return;
    }
    formatMilesInput(target);
  });
})();
