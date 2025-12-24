(() => {
  const form = document.querySelector("[data-venta-form]");
  if (!form) {
    return;
  }

  const medioSelect = form.querySelector('[name="medio_pago"]');
  const deudaFields = form.querySelector("[data-deuda-fields]");
  const nuevoToggle = form.querySelector("[data-nuevo-deudor-toggle]");
  const nuevoPanel = form.querySelector("[data-nuevo-deudor-panel]");

  const toggleDeuda = () => {
    if (!medioSelect || !deudaFields) {
      return;
    }
    const isDeuda = medioSelect.value === "DEUDA";
    deudaFields.hidden = !isDeuda;
    deudaFields.setAttribute("aria-hidden", isDeuda ? "false" : "true");
  };

  const setNuevoPanelState = (open) => {
    if (!nuevoPanel || !nuevoToggle) {
      return;
    }
    nuevoPanel.classList.toggle("is-open", open);
    nuevoPanel.setAttribute("aria-hidden", open ? "false" : "true");
    nuevoToggle.setAttribute("aria-expanded", open ? "true" : "false");
    if (open) {
      nuevoPanel.style.maxHeight = `${nuevoPanel.scrollHeight}px`;
    } else {
      nuevoPanel.style.maxHeight = "0px";
    }
  };

  const shouldOpenNuevoPanel = () => {
    if (!nuevoPanel) {
      return false;
    }
    if (nuevoPanel.dataset.defaultOpen === "true") {
      return true;
    }
    const hasValue = Array.from(
      nuevoPanel.querySelectorAll("input, textarea, select")
    ).some((input) => input.value && input.value.trim() !== "");
    return hasValue;
  };

  if (medioSelect) {
    medioSelect.addEventListener("change", toggleDeuda);
  }

  if (nuevoToggle) {
    nuevoToggle.addEventListener("click", () => {
      const isOpen = nuevoPanel && nuevoPanel.classList.contains("is-open");
      setNuevoPanelState(!isOpen);
    });
  }

  if (nuevoPanel) {
    setNuevoPanelState(shouldOpenNuevoPanel());
    window.addEventListener("resize", () => {
      if (nuevoPanel.classList.contains("is-open")) {
        nuevoPanel.style.maxHeight = `${nuevoPanel.scrollHeight}px`;
      }
    });
  }

  toggleDeuda();
})();
