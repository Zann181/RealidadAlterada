(() => {
  const store = document.querySelector("[data-store]");
  if (!store) {
    return;
  }

  const cartList = store.querySelector("[data-cart-items]");
  const cartEmpty = store.querySelector("[data-cart-empty]");
  const cartTotal = store.querySelector("[data-cart-total]");
  const cartCounts = Array.from(store.querySelectorAll("[data-cart-count]"));
  const checkoutButton = store.querySelector("[data-checkout]");
  const statusEl = store.querySelector("[data-cart-status]");
  const checkoutUrl = store.dataset.checkoutUrl;
  const storageKey = "tienda_cart";
  const customerKey = "tienda_customer";

  const nameInput = store.querySelector("[data-customer-name]");
  const phoneInput = store.querySelector("[data-customer-phone]");
  const emailInput = store.querySelector("[data-customer-email]");
  const noteInput = store.querySelector("[data-customer-note]");

  const cartDrawer = store.querySelector("[data-cart-drawer]");
  const cartToggles = Array.from(store.querySelectorAll("[data-cart-toggle]"));
  const cartCloses = Array.from(store.querySelectorAll("[data-cart-close]"));

  const formatter = new Intl.NumberFormat("es-CO", {
    maximumFractionDigits: 0,
  });

  const formatMoney = (value) => `$ ${formatter.format(Math.round(value || 0))}`;

  const initCarousels = () => {
    const carousels = Array.from(store.querySelectorAll("[data-store-carousel]"));
    carousels.forEach((carousel) => {
      const dataId = carousel.dataset.carouselData;
      if (!dataId) {
        return;
      }
      const script = document.getElementById(dataId);
      if (!script) {
        return;
      }
      let images = [];
      try {
        images = JSON.parse(script.textContent || "[]");
      } catch (error) {
        images = [];
      }
      if (!Array.isArray(images) || images.length <= 1) {
        return;
      }

      const img = carousel.querySelector("[data-carousel-image]");
      if (!img) {
        return;
      }
      const prev = carousel.querySelector("[data-carousel-prev]");
      const next = carousel.querySelector("[data-carousel-next]");
      const counter = carousel.querySelector("[data-carousel-counter]");

      let index = 0;
      const render = () => {
        const current = images[index] || {};
        if (current.url) {
          img.src = current.url;
        }
        img.alt = current.alt || "";
        if (counter) {
          counter.textContent = `${index + 1} / ${images.length}`;
        }
      };

      const goTo = (nextIndex) => {
        const safeIndex = ((nextIndex % images.length) + images.length) % images.length;
        index = safeIndex;
        render();
      };

      if (prev) {
        prev.addEventListener("click", () => goTo(index - 1));
      }
      if (next) {
        next.addEventListener("click", () => goTo(index + 1));
      }

      render();
    });
  };

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

  const cart = new Map();

  initCarousels();

  const loadCustomer = () => {
    try {
      const stored = JSON.parse(localStorage.getItem(customerKey) || "null");
      if (!stored || typeof stored !== "object") {
        return;
      }
      if (nameInput && !nameInput.value && stored.nombre) {
        nameInput.value = stored.nombre;
      }
      if (phoneInput && !phoneInput.value && stored.telefono) {
        phoneInput.value = stored.telefono;
      }
      if (emailInput && !emailInput.value && stored.correo) {
        emailInput.value = stored.correo;
      }
    } catch (error) {
      localStorage.removeItem(customerKey);
    }
  };

  const saveCustomer = () => {
    localStorage.setItem(
      customerKey,
      JSON.stringify({
        nombre: nameInput ? nameInput.value : "",
        telefono: phoneInput ? phoneInput.value : "",
        correo: emailInput ? emailInput.value : "",
      })
    );
  };

  const setStatus = (message, variant) => {
    if (!statusEl) {
      return;
    }
    statusEl.textContent = message;
    statusEl.classList.remove("is-error", "is-success", "is-loading");
    if (variant) {
      statusEl.classList.add(variant);
    }
  };

  const saveCart = () => {
    const items = Array.from(cart.values());
    localStorage.setItem(storageKey, JSON.stringify(items));
  };

  const loadCart = () => {
    try {
      const stored = JSON.parse(localStorage.getItem(storageKey) || "[]");
      if (!Array.isArray(stored)) {
        return;
      }
      stored.forEach((item) => {
        if (!item || !item.id) {
          return;
        }
        cart.set(item.id, item);
      });
    } catch (error) {
      localStorage.removeItem(storageKey);
    }
  };

  const updateSummary = () => {
    let total = 0;
    let count = 0;
    cart.forEach((item) => {
      total += item.precio * item.cantidad;
      count += item.cantidad;
    });
    if (cartTotal) {
      cartTotal.textContent = formatMoney(total);
    }
    cartCounts.forEach((badge) => {
      badge.textContent = count;
    });
    if (cartEmpty) {
      cartEmpty.style.display = cart.size ? "none" : "block";
    }
  };

  const renderCart = () => {
    if (!cartList) {
      return;
    }
    cartList.innerHTML = "";
    cart.forEach((item) => {
      const li = document.createElement("li");
      li.className = "cart-item";
      li.dataset.id = item.id;
      li.innerHTML = `
        <div class="cart-item-info">
          <strong>${item.nombre}</strong>
          <span class="text-muted small">${formatMoney(item.precio)} c/u</span>
        </div>
        <div class="cart-item-controls">
          <button type="button" class="btn btn-ghost btn-sm" data-action="dec">-</button>
          <span data-role="qty">${item.cantidad}</span>
          <button type="button" class="btn btn-ghost btn-sm" data-action="inc">+</button>
        </div>
        <div class="cart-item-total">${formatMoney(item.precio * item.cantidad)}</div>
        <button type="button" class="btn btn-ghost btn-sm" data-action="remove">x</button>
      `;
      cartList.appendChild(li);
    });
    updateSummary();
    saveCart();
  };

  const clamp = (value, min, max) => Math.min(Math.max(value, min), max);

  const updateQuantity = (id, delta, maxStock) => {
    const item = cart.get(id);
    if (!item) {
      return;
    }
    const nextQty = clamp(item.cantidad + delta, 0, maxStock || 9999);
    if (nextQty <= 0) {
      cart.delete(id);
    } else {
      item.cantidad = nextQty;
      cart.set(id, item);
    }
    renderCart();
  };

  const addToCart = (data, qty) => {
    const current = cart.get(data.id);
    const nextQty = (current ? current.cantidad : 0) + qty;
    const maxStock = Number.isFinite(data.stock) ? Math.max(0, Math.floor(data.stock)) : 0;
    if (maxStock > 0 && nextQty > maxStock) {
      setStatus("La cantidad supera el stock disponible.", "is-error");
      return;
    }
    cart.set(data.id, {
      ...data,
      cantidad: nextQty,
    });
    setStatus("Producto agregado al carrito.", "is-success");
    renderCart();
  };

  const readCardData = (card) => {
    const id = Number(card.dataset.productId);
    const nombre = card.dataset.productName || "";
    const precio = Number(card.dataset.productPrice || 0);
    const stock = Number(card.dataset.productStock || 0);
    return { id, nombre, precio, stock };
  };

  store.querySelectorAll("[data-product-card]").forEach((card) => {
    const qtyInput = card.querySelector("[data-qty-input]");
    const addButton = card.querySelector("[data-add-cart]");
    const incButton = card.querySelector("[data-qty-inc]");
    const decButton = card.querySelector("[data-qty-dec]");
    const data = readCardData(card);
    const maxStock = Number.isFinite(data.stock) ? Math.max(0, Math.floor(data.stock)) : 0;

    const normalizeQty = () => {
      const raw = qtyInput ? Number(qtyInput.value) : 1;
      let safe = Number.isFinite(raw) ? Math.max(1, Math.round(raw)) : 1;
      if (maxStock > 0) {
        safe = clamp(safe, 1, maxStock);
      }
      if (qtyInput) {
        qtyInput.value = safe;
      }
      return safe;
    };

    if (incButton && qtyInput) {
      incButton.addEventListener("click", () => {
        const next = normalizeQty() + 1;
        qtyInput.value = maxStock > 0 ? clamp(next, 1, maxStock) : next;
      });
    }

    if (decButton && qtyInput) {
      decButton.addEventListener("click", () => {
        const next = Math.max(1, normalizeQty() - 1);
        qtyInput.value = next;
      });
    }

    if (qtyInput) {
      qtyInput.addEventListener("change", () => {
        normalizeQty();
      });
    }

    if (addButton) {
      addButton.addEventListener("click", () => {
        const qty = normalizeQty();
        if (!data.id) {
          return;
        }
        if (data.stock <= 0) {
          setStatus("Producto sin stock disponible.", "is-error");
          return;
        }
        addToCart(data, qty);
      });
    }
  });

  if (cartList) {
    cartList.addEventListener("click", (event) => {
      const button = event.target.closest("button[data-action]");
      if (!button) {
        return;
      }
      const item = button.closest(".cart-item");
      if (!item) {
        return;
      }
      const id = Number(item.dataset.id);
      const action = button.dataset.action;
      if (!id || !action) {
        return;
      }
      const productCard = store.querySelector(`[data-product-card][data-product-id="${id}"]`);
      const maxStock = productCard ? Number(productCard.dataset.productStock || 0) : 0;
      if (action === "inc") {
        updateQuantity(id, 1, maxStock || 9999);
      } else if (action === "dec") {
        updateQuantity(id, -1, maxStock || 9999);
      } else if (action === "remove") {
        cart.delete(id);
        renderCart();
      }
    });
  }

  if (checkoutButton) {
    checkoutButton.addEventListener("click", () => {
      if (!cart.size) {
        setStatus("Agrega productos antes de continuar.", "is-error");
        return;
      }
      setStatus("Venta en proceso, redirigiendo a WhatsApp...", "is-loading");
      checkoutButton.disabled = true;

      const items = Array.from(cart.values()).map((item) => ({
        id: item.id,
        cantidad: item.cantidad,
      }));

      const payload = new URLSearchParams();
      payload.set("items", JSON.stringify(items));
      payload.set("nombre", nameInput ? nameInput.value : "");
      payload.set("telefono", phoneInput ? phoneInput.value : "");
      payload.set("correo", emailInput ? emailInput.value : "");
      payload.set("nota", noteInput ? noteInput.value : "");

      fetch(checkoutUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
          "X-CSRFToken": getCookie("csrftoken"),
        },
        body: payload.toString(),
      })
        .then((response) => response.json())
        .then((data) => {
          if (!data || data.error) {
            throw new Error(data && data.error ? data.error : "Error al procesar la venta.");
          }
          saveCustomer();
          localStorage.removeItem(storageKey);
          window.location.href = data.redirect_url;
        })
        .catch((error) => {
          setStatus(error.message, "is-error");
        })
        .finally(() => {
          checkoutButton.disabled = false;
        });
    });
  }

  loadCart();
  loadCustomer();
  renderCart();

  const openCart = () => {
    if (!cartDrawer) {
      return;
    }
    cartDrawer.classList.add("is-open");
    cartDrawer.setAttribute("aria-hidden", "false");
  };

  const closeCart = () => {
    if (!cartDrawer) {
      return;
    }
    cartDrawer.classList.remove("is-open");
    cartDrawer.setAttribute("aria-hidden", "true");
  };

  cartToggles.forEach((toggle) => {
    toggle.addEventListener("click", () => {
      if (!cartDrawer) {
        return;
      }
      if (cartDrawer.classList.contains("is-open")) {
        closeCart();
      } else {
        openCart();
      }
    });
  });

  cartCloses.forEach((close) => {
    close.addEventListener("click", () => {
      closeCart();
    });
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeCart();
    }
  });
})();
