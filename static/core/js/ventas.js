(() => {
  const table = document.querySelector("[data-factura]");
  if (!table) {
    return;
  }

  const descuentoInput = document.querySelector('input[data-role="descuento"]');
  const urlDescuento = table.dataset.urlDescuento;
  const urlIva = table.dataset.urlIva;

  const parseNumber = (value) => {
    if (value === null || value === undefined) {
      return 0;
    }
    const normalized = String(value).replace(/\./g, "").replace(",", ".");
    const numberValue = Number(normalized);
    return Number.isFinite(numberValue) ? numberValue : 0;
  };

  const formatMiles = (value) => {
    const rounded = Math.round(Number(value) || 0);
    const sign = rounded < 0 ? "-" : "";
    const absolute = Math.abs(rounded);
    const parts = [];
    let current = absolute;
    while (current >= 1000) {
      const rest = current % 1000;
      parts.unshift(String(rest).padStart(3, "0"));
      current = Math.floor(current / 1000);
    }
    parts.unshift(String(current));
    return sign + parts.join(".");
  };

  const getCell = (role) => table.querySelector(`[data-role="${role}"]`);

  const getCookie = (name) => {
    const cookies = document.cookie ? document.cookie.split(";") : [];
    for (let i = 0; i < cookies.length; i += 1) {
      const cookie = cookies[i].trim();
      if (cookie.startsWith(`${name}=`)) {
        return decodeURIComponent(cookie.slice(name.length + 1));
      }
    }
    return "";
  };

  const postData = (url, data) => {
    if (!url) {
      return Promise.resolve();
    }
    const csrfToken = getCookie("csrftoken");
    return fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
        "X-CSRFToken": csrfToken,
      },
      body: new URLSearchParams(data).toString(),
    }).catch(() => {});
  };

  const postForm = (form, submitter) => {
    const url = form.getAttribute("action");
    if (!url) {
      return Promise.resolve(null);
    }
    const csrfToken = getCookie("csrftoken");
    const formData = new FormData(form);
    if (submitter && submitter.name) {
      formData.set(submitter.name, submitter.value);
    }
    const payload = new URLSearchParams(formData).toString();
    return fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
        "X-CSRFToken": csrfToken,
        "X-Requested-With": "XMLHttpRequest",
      },
      body: payload,
    })
      .then((response) => response.json())
      .catch(() => null);
  };

  const debounce = (callback, delay) => {
    let timeoutId;
    return (...args) => {
      window.clearTimeout(timeoutId);
      timeoutId = window.setTimeout(() => callback(...args), delay);
    };
  };

  const saveDescuento = debounce((value) => {
    postData(urlDescuento, { descuento_total: value });
  }, 400);

  const saveIva = debounce((productoId, value) => {
    postData(urlIva, { producto: productoId, iva: value });
  }, 400);

  const updateTotals = () => {
    const descuentoPct = descuentoInput
      ? parseNumber(descuentoInput.value)
      : parseNumber(table.dataset.descuentoPct || 0);
    let subtotal = 0;
    let ivaTotal = 0;

    table.querySelectorAll("tbody tr[data-product]").forEach((row) => {
      const cantidad = parseNumber(row.dataset.cantidad || 0);
      const precio = parseNumber(row.dataset.precio || 0);
      const ivaInput = row.querySelector('input[data-role="iva"]');
      const ivaPct = ivaInput ? parseNumber(ivaInput.value) : parseNumber(row.dataset.iva || 0);
      const lineTotal = cantidad * precio;
      let lineSubtotal = lineTotal;
      let lineIva = 0;
      if (ivaPct > 0) {
        lineSubtotal = lineTotal / (1 + ivaPct / 100);
        lineIva = lineTotal - lineSubtotal;
      }
      subtotal += lineSubtotal;
      ivaTotal += lineIva;

      const lineCell = row.querySelector('[data-role="total-linea"]');
      if (lineCell) {
        lineCell.textContent = formatMiles(lineTotal);
      }
    });

    const descuentoValor = (subtotal + ivaTotal) * (descuentoPct / 100);
    const total = subtotal + ivaTotal - descuentoValor;

    const subtotalCell = getCell("subtotal");
    const ivaCell = getCell("iva-total");
    const descuentoCell = getCell("descuento-total");
    const totalCell = getCell("total");

    if (subtotalCell) {
      subtotalCell.textContent = formatMiles(subtotal);
    }
    if (ivaCell) {
      ivaCell.textContent = formatMiles(ivaTotal);
    }
    if (descuentoCell) {
      descuentoCell.textContent = formatMiles(descuentoValor);
    }
    if (totalCell) {
      totalCell.textContent = formatMiles(total);
    }
  };

  table.addEventListener("input", (event) => {
    if (event.target && event.target.matches('input[data-role="iva"]')) {
      const row = event.target.closest("tr[data-product]");
      if (row) {
        row.dataset.iva = event.target.value || "0";
      }
      updateTotals();
      if (row) {
        const cantidad = parseNumber(row.dataset.cantidad || 0);
        if (cantidad > 0) {
          saveIva(row.dataset.productId, event.target.value);
        }
      }
      return;
    }
  });

  if (descuentoInput) {
    descuentoInput.addEventListener("input", () => {
      const value = descuentoInput.value;
      table.dataset.descuentoPct = value || "0";
      updateTotals();
      saveDescuento(value);
    });
  }

  const showToast = (message, variant = "info") => {
    const container =
      document.querySelector("[data-toast-container]") ||
      (() => {
        const el = document.createElement("div");
        el.className = "messages messages-floating";
        el.setAttribute("data-toast-container", "");
        el.setAttribute("aria-live", "polite");
        el.setAttribute("aria-atomic", "true");
        document.body.appendChild(el);
        return el;
      })();
    const toast = document.createElement("div");
    toast.className = `alert ${variant}`;
    toast.textContent = message;
    container.appendChild(toast);
    window.setTimeout(() => {
      toast.classList.add("is-hiding");
      toast.addEventListener(
        "transitionend",
        () => {
          toast.remove();
        },
        { once: true }
      );
    }, 7000);
  };

  const handleFormSubmit = (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement)) {
      return;
    }
    if (!form.classList.contains("table-form")) {
      return;
    }
    event.preventDefault();
    const row = form.closest("tr[data-product]");
    const buttons = Array.from(form.querySelectorAll("button"));
    buttons.forEach((button) => {
      button.disabled = true;
    });
    postForm(form, event.submitter).then((data) => {
      buttons.forEach((button) => {
        button.disabled = false;
      });
      if (!data) {
        showToast("No se pudo actualizar la venta.", "error");
        return;
      }
      if (!data.ok) {
        showToast(data.error || "No se pudo actualizar la venta.", "error");
        return;
      }
      if (!row) {
        updateTotals();
        return;
      }
      if (typeof data.cantidad === "number") {
        row.dataset.cantidad = String(data.cantidad);
        const qtyCell = row.querySelector('[data-role="cantidad"]');
        if (qtyCell) {
          qtyCell.textContent = formatMiles(data.cantidad);
        }
      }
      if (typeof data.stock === "number") {
        row.dataset.stock = String(data.stock);
        const stockCell = row.querySelector('[data-role="stock"]');
        if (stockCell) {
          stockCell.textContent = formatMiles(data.stock);
        }
      }
      updateTotals();
    });
  };

  table.querySelectorAll("form.table-form").forEach((form) => {
    form.addEventListener("submit", handleFormSubmit);
  });

  document.addEventListener("submit", handleFormSubmit, true);

  updateTotals();
})();
