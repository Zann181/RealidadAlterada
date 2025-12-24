(() => {
  const form = document.getElementById("producto-form");
  const categoriaSelect = document.getElementById("id_categoria");
  const editLink = document.getElementById("categoria-edit");
  const actionLinks = document.querySelectorAll(".categoria-action");
  const STORAGE_KEY = "producto_form_draft";
  const RESTORE_KEY = "producto_form_restore";

  if (categoriaSelect && editLink) {
    const template = editLink.dataset.urlTemplate;

    const updateEditLink = () => {
      const value = categoriaSelect.value;
      if (value) {
        editLink.href = template.replace("/0/", `/${value}/`);
        editLink.classList.remove("is-disabled");
        editLink.removeAttribute("aria-disabled");
      } else {
        editLink.href = "#";
        editLink.classList.add("is-disabled");
        editLink.setAttribute("aria-disabled", "true");
      }
    };

    updateEditLink();
    categoriaSelect.addEventListener("change", updateEditLink);
  }

  if (!form) {
    return;
  }

  const saveDraft = () => {
    const data = {};
    Array.from(form.elements).forEach((element) => {
      if (!element.name || element.type === "file") {
        return;
      }
      if (element.type === "checkbox") {
        data[element.name] = element.checked ? "1" : "0";
      } else if (element.type === "radio") {
        if (element.checked) {
          data[element.name] = element.value;
        }
      } else {
        data[element.name] = element.value;
      }
    });
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(data));
    sessionStorage.setItem(RESTORE_KEY, "1");
  };

  const restoreDraft = () => {
    if (form.dataset.mode !== "create") {
      return;
    }
    if (sessionStorage.getItem(RESTORE_KEY) !== "1") {
      return;
    }
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return;
    }
    let data = null;
    try {
      data = JSON.parse(raw);
    } catch (err) {
      return;
    }
    Object.entries(data).forEach(([name, value]) => {
      const element = form.elements[name];
      if (!element) {
        return;
      }
      if (typeof RadioNodeList !== "undefined" && element instanceof RadioNodeList) {
        element.value = value;
        return;
      }
      if (element.type === "checkbox") {
        element.checked = value === "1";
        return;
      }
      if (element.type !== "file") {
        element.value = value;
      }
    });
    sessionStorage.removeItem(RESTORE_KEY);
  };

  restoreDraft();

  actionLinks.forEach((link) => {
    link.addEventListener("click", (event) => {
      if (link.classList.contains("is-disabled")) {
        event.preventDefault();
        return;
      }
      saveDraft();
    });
  });

  form.addEventListener("submit", () => {
    sessionStorage.removeItem(STORAGE_KEY);
    sessionStorage.removeItem(RESTORE_KEY);
  });
})();
