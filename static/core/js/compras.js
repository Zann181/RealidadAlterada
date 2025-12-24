(() => {
  const parseNumber = (value) => {
    if (value === null || value === undefined) {
      return 0;
    }
    const normalized = String(value).replace(/\./g, "").replace(",", ".");
    const numberValue = Number(normalized);
    return Number.isFinite(numberValue) ? numberValue : 0;
  };

  const formatMiles = (value) => {
    const rounded = Math.max(0, Math.round(Number(value) || 0));
    const parts = [];
    let current = rounded;
    while (current >= 1000) {
      const rest = current % 1000;
      parts.unshift(String(rest).padStart(3, "0"));
      current = Math.floor(current / 1000);
    }
    parts.unshift(String(current));
    return parts.join(".");
  };

  const deudaForm = document.querySelector("[data-deuda-form]");
  if (deudaForm) {
    const input = deudaForm.querySelector("#sena");
    const saldoEl = deudaForm.querySelector("[data-saldo]");
    const total = parseNumber(deudaForm.dataset.total || 0);

    const updateSaldo = () => {
      if (!saldoEl) {
        return;
      }
      const sena = parseNumber(input ? input.value : 0);
      const saldo = Math.max(0, total - sena);
      saldoEl.textContent = formatMiles(saldo);
    };

    if (input) {
      input.addEventListener("input", updateSaldo);
    }

    updateSaldo();
  }

  const itemForm = document.querySelector("#agregar-item form");
  if (itemForm) {
    const qtyInput = itemForm.querySelector('[name="cantidad"]');
    const costInput = itemForm.querySelector('[name="costo_unitario"]');
    const ivaInput = itemForm.querySelector('[name="iva"]');
    const totalInput = itemForm.querySelector('[name="total_linea"]');

    const updateTotalLinea = () => {
      if (!totalInput) {
        return;
      }
      const cantidad = parseNumber(qtyInput ? qtyInput.value : 0);
      const costo = parseNumber(costInput ? costInput.value : 0);
      const ivaPct = parseNumber(ivaInput ? ivaInput.value : 0);
      const base = cantidad * costo;
      const total = base + base * (ivaPct / 100);
      totalInput.value = total ? formatMiles(total) : "";
    };

    if (qtyInput) {
      qtyInput.addEventListener("input", updateTotalLinea);
    }
    if (costInput) {
      costInput.addEventListener("input", updateTotalLinea);
    }
    if (ivaInput) {
      ivaInput.addEventListener("input", updateTotalLinea);
    }

    updateTotalLinea();
  }
})();
