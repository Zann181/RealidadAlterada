(() => {
  const charts = Array.from(document.querySelectorAll("[data-chart]"));
  if (!charts.length) {
    return;
  }

  const readSeries = (id) => {
    if (!id) {
      return [];
    }
    const script = document.getElementById(id);
    if (!script) {
      return [];
    }
    try {
      const data = JSON.parse(script.textContent);
      return Array.isArray(data) ? data : [];
    } catch (error) {
      return [];
    }
  };

  const numberFormatter = new Intl.NumberFormat("es-CO", {
    maximumFractionDigits: 0,
  });
  const percentFormatter = new Intl.NumberFormat("es-CO", {
    maximumFractionDigits: 1,
  });

  const formatNumber = (value) => {
    const numeric = Number.isFinite(value) ? value : 0;
    return numberFormatter.format(Math.round(numeric));
  };

  const formatPercent = (value) => {
    const numeric = Number.isFinite(value) ? value : 0;
    return `${percentFormatter.format(numeric)}%`;
  };

  const createSvgEl = (tag, attrs = {}) => {
    const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
    Object.entries(attrs).forEach(([key, value]) => {
      el.setAttribute(key, value);
    });
    return el;
  };

  const setEmpty = (chart, message) => {
    chart.innerHTML = "";
    const empty = document.createElement("div");
    empty.className = "chart-empty";
    empty.textContent = message;
    chart.appendChild(empty);
  };

  const drawLineChart = (chart, series) => {
    const width = chart.clientWidth;
    const height = chart.clientHeight;
    if (!width || !height) {
      return;
    }

    if (!series.length) {
      setEmpty(chart, "Sin datos para el periodo seleccionado.");
      return;
    }

    const values = series.map((item) => {
      const value = Number(item.value);
      return Number.isFinite(value) ? value : 0;
    });

    const max = Math.max(...values, 0);
    const min = Math.min(...values, 0);
    if (max === 0 && min === 0) {
      setEmpty(chart, "Sin movimientos en el periodo.");
      return;
    }

    const padding = {
      top: 18,
      right: 18,
      bottom: 32,
      left: 56,
    };
    const innerWidth = width - padding.left - padding.right;
    const innerHeight = height - padding.top - padding.bottom;
    const range = max - min || 1;
    const format = chart.dataset.chartFormat === "percent" ? "percent" : "number";
    const formatValue = format === "percent" ? formatPercent : formatNumber;

    const toY = (value) =>
      padding.top + ((max - value) / range) * innerHeight;

    const points = series.map((item, index) => {
      const value = Number(item.value);
      return {
        x: padding.left + (innerWidth * index) / Math.max(series.length - 1, 1),
        y: toY(Number.isFinite(value) ? value : 0),
        value: Number.isFinite(value) ? value : 0,
        label: item.label || "",
      };
    });

    const svg = createSvgEl("svg", {
      viewBox: `0 0 ${width} ${height}`,
      role: "img",
      "aria-hidden": "true",
    });

    const gridLines = 4;
    for (let i = 0; i <= gridLines; i += 1) {
      const y = padding.top + (innerHeight / gridLines) * i;
      const line = createSvgEl("line", {
        x1: padding.left,
        x2: width - padding.right,
        y1: y,
        y2: y,
        class: "chart-grid",
      });
      svg.appendChild(line);

      const value = max - (range / gridLines) * i;
      const label = createSvgEl("text", {
        x: padding.left - 8,
        y: y,
        class: "chart-label",
        "text-anchor": "end",
        "dominant-baseline": "middle",
      });
      label.textContent = formatValue(value);
      svg.appendChild(label);
    }

    const axisX = createSvgEl("line", {
      x1: padding.left,
      x2: width - padding.right,
      y1: height - padding.bottom,
      y2: height - padding.bottom,
      class: "chart-axis",
    });
    svg.appendChild(axisX);

    const axisY = createSvgEl("line", {
      x1: padding.left,
      x2: padding.left,
      y1: padding.top,
      y2: height - padding.bottom,
      class: "chart-axis",
    });
    svg.appendChild(axisY);

    if (min < 0 && max > 0) {
      const zeroY = toY(0);
      const zeroLine = createSvgEl("line", {
        x1: padding.left,
        x2: width - padding.right,
        y1: zeroY,
        y2: zeroY,
        class: "chart-zero",
      });
      svg.appendChild(zeroLine);
    }

    const labelSlots = Math.min(series.length, 6);
    const step = Math.max(1, Math.round((series.length - 1) / Math.max(labelSlots - 1, 1)));
    const usedIndexes = new Set();
    for (let i = 0; i < series.length; i += step) {
      usedIndexes.add(i);
    }
    usedIndexes.add(series.length - 1);

    usedIndexes.forEach((index) => {
      const point = points[index];
      const label = createSvgEl("text", {
        x: point.x,
        y: height - padding.bottom + 18,
        class: "chart-label",
        "text-anchor": "middle",
      });
      label.textContent = point.label;
      svg.appendChild(label);
    });

    const linePath = points
      .map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`)
      .join(" ");

    const baseY = min < 0 && max > 0 ? toY(0) : height - padding.bottom;
    const areaPath = `${linePath} L ${points[points.length - 1].x} ${baseY} L ${points[0].x} ${baseY} Z`;

    const area = createSvgEl("path", {
      d: areaPath,
      class: "chart-area",
    });
    svg.appendChild(area);

    const line = createSvgEl("path", {
      d: linePath,
      class: "chart-line",
    });
    svg.appendChild(line);

    points.forEach((point) => {
      const circle = createSvgEl("circle", {
        cx: point.x,
        cy: point.y,
        r: 2.5,
        class: "chart-point",
      });
      svg.appendChild(circle);
    });

    chart.innerHTML = "";
    chart.appendChild(svg);
  };

  const drawDonutChart = (chart, series) => {
    const width = chart.clientWidth;
    const height = chart.clientHeight;
    if (!width || !height) {
      return;
    }

    if (!series.length) {
      setEmpty(chart, "Sin datos para el periodo seleccionado.");
      return;
    }

    const weights = series.map((item) => {
      const ganancia = Number(item.ganancia);
      if (Number.isFinite(ganancia)) {
        return ganancia;
      }
      const percent = Number(item.percent);
      if (Number.isFinite(percent)) {
        return percent;
      }
      const value = Number(item.value);
      return Number.isFinite(value) ? value : 0;
    });

    const total = weights.reduce((sum, value) => sum + value, 0);
    if (!total) {
      setEmpty(chart, "Sin margen positivo en el periodo.");
      return;
    }

    const styles = getComputedStyle(document.documentElement);
    const paletteKeys = [
      "--psy-1",
      "--psy-2",
      "--psy-3",
      "--psy-4",
      "--primary",
      "--success",
      "--warning",
      "--danger",
      "--info",
    ];
    const palette = paletteKeys
      .map((key) => styles.getPropertyValue(key).trim())
      .filter(Boolean);

    const size = Math.min(width, height);
    const strokeWidth = Math.max(14, Math.round(size * 0.12));
    const radius = (size - strokeWidth) / 2 - 4;
    const centerX = width / 2;
    const centerY = height / 2;

    const polarToCartesian = (cx, cy, r, angle) => {
      const radians = ((angle - 90) * Math.PI) / 180;
      return {
        x: cx + r * Math.cos(radians),
        y: cy + r * Math.sin(radians),
      };
    };

    const describeArc = (cx, cy, r, startAngle, endAngle) => {
      const start = polarToCartesian(cx, cy, r, endAngle);
      const end = polarToCartesian(cx, cy, r, startAngle);
      const largeArc = endAngle - startAngle <= 180 ? "0" : "1";
      return `M ${start.x} ${start.y} A ${r} ${r} 0 ${largeArc} 0 ${end.x} ${end.y}`;
    };

    const svg = createSvgEl("svg", {
      viewBox: `0 0 ${width} ${height}`,
      role: "img",
      "aria-hidden": "true",
    });

    const track = createSvgEl("circle", {
      cx: centerX,
      cy: centerY,
      r: radius,
      class: "donut-track",
    });
    track.style.strokeWidth = `${strokeWidth}`;
    svg.appendChild(track);

    let startAngle = -90;
    weights.forEach((weight, index) => {
      if (weight <= 0) {
        return;
      }
      const slice = (weight / total) * 360;
      const endAngle = startAngle + slice;
      const path = createSvgEl("path", {
        d: describeArc(centerX, centerY, radius, startAngle, endAngle),
        class: "donut-segment",
        "stroke-linecap": "round",
      });
      const color = palette[index % palette.length] || "currentColor";
      path.style.stroke = color;
      path.style.strokeWidth = `${strokeWidth}`;
      svg.appendChild(path);
      startAngle = endAngle;
    });

    chart.innerHTML = "";
    chart.appendChild(svg);

    const centerLabel = chart.dataset.centerLabel;
    const centerValue = chart.dataset.centerValue;
    if (centerLabel || centerValue) {
      const center = document.createElement("div");
      center.className = "donut-center";
      if (centerLabel) {
        const label = document.createElement("span");
        label.className = "donut-center-label";
        label.textContent = centerLabel;
        center.appendChild(label);
      }
      if (centerValue) {
        const value = document.createElement("strong");
        value.className = "donut-center-value";
        value.textContent = centerValue;
        center.appendChild(value);
      }
      chart.appendChild(center);
    }
  };

  const renderChart = (chart) => {
    const seriesId = chart.dataset.series;
    const series = readSeries(seriesId);
    const type = chart.dataset.chartType;
    if (type === "donut") {
      drawDonutChart(chart, series);
      return;
    }
    drawLineChart(chart, series);
  };

  const renderCharts = () => {
    charts.forEach((chart) => {
      if (chart.closest(".is-hidden")) {
        return;
      }
      renderChart(chart);
    });
  };

  renderCharts();

  if (typeof ResizeObserver !== "undefined") {
    const observer = new ResizeObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.target instanceof HTMLElement) {
          renderChart(entry.target);
        }
      });
    });
    charts.forEach((chart) => observer.observe(chart));
  }

  const cards = Array.from(document.querySelectorAll("[data-stat]"));
  const applyStats = (selected) => {
    const selectedSet = new Set((selected || []).filter(Boolean));
    const showAll = selectedSet.has("todas") || selectedSet.size === 0;

    cards.forEach((card) => {
      const stats = (card.dataset.stat || "").split(" ").filter(Boolean);
      const isVisible = showAll || stats.some((stat) => selectedSet.has(stat));
      card.classList.toggle("is-hidden", !isVisible);
    });

    renderCharts();
  };

  const statCheckboxes = Array.from(document.querySelectorAll("[data-stat-checkbox]"));
  if (statCheckboxes.length) {
    const statSummary = document.querySelector("[data-stat-summary]");
    const detailSections = Array.from(document.querySelectorAll("[data-stat-detail]"));
    const allCheckbox = statCheckboxes.find((checkbox) => checkbox.value === "todas") || null;
    const optionCheckboxes = allCheckbox
      ? statCheckboxes.filter((checkbox) => checkbox !== allCheckbox)
      : statCheckboxes;
    const fallbackCheckbox =
      optionCheckboxes.find((checkbox) => checkbox.value === "finanzas") || optionCheckboxes[0] || null;

    const labelFor = (checkbox) => {
      const label = checkbox.closest("label");
      const text = (label && label.textContent) || checkbox.value;
      return text.trim();
    };

    const getSelected = () =>
      statCheckboxes.filter((checkbox) => checkbox.checked).map((checkbox) => checkbox.value);

    const syncAllCheckbox = () => {
      if (!allCheckbox) {
        return;
      }
      const allSelected = optionCheckboxes.length > 0 && optionCheckboxes.every((checkbox) => checkbox.checked);
      allCheckbox.checked = allSelected;
    };

    const syncSummary = () => {
      if (!statSummary) {
        return;
      }
      if (allCheckbox && allCheckbox.checked) {
        statSummary.textContent = "Todas";
        return;
      }
      const selected = optionCheckboxes.filter((checkbox) => checkbox.checked);
      if (!selected.length) {
        statSummary.textContent = "Seleccionar";
        return;
      }
      if (selected.length === 1) {
        statSummary.textContent = labelFor(selected[0]);
        return;
      }
      statSummary.textContent = `${selected.length} seleccionadas`;
    };

    const applyDetail = (activeStat) => {
      const stat = activeStat || "";
      const focus = Boolean(stat) && stat !== "finanzas";
      document.body.classList.toggle("dashboard-focus", focus);
      detailSections.forEach((section) => {
        const target = section.dataset.statDetail;
        const isVisible = Boolean(stat) && target === stat;
        section.classList.toggle("is-hidden", !isVisible);
      });
    };

    const applySelection = () => {
      const selectedOptions = optionCheckboxes
        .filter((checkbox) => checkbox.checked)
        .map((checkbox) => checkbox.value);
      const activeDetail = selectedOptions.length === 1 ? selectedOptions[0] : null;
      applyStats(getSelected());
      syncSummary();
      applyDetail(activeDetail);
    };

    const ensureFallback = () => {
      if (!statCheckboxes.some((checkbox) => checkbox.checked) && fallbackCheckbox) {
        fallbackCheckbox.checked = true;
      }
    };

    const handleChange = (changedCheckbox) => {
      if (allCheckbox && changedCheckbox === allCheckbox) {
        optionCheckboxes.forEach((checkbox) => {
          checkbox.checked = allCheckbox.checked;
        });
        ensureFallback();
        syncAllCheckbox();
        applySelection();
        return;
      }

      if (allCheckbox && allCheckbox.checked && changedCheckbox && !changedCheckbox.checked) {
        allCheckbox.checked = false;
      }

      ensureFallback();
      syncAllCheckbox();
      applySelection();
    };

    if (allCheckbox && allCheckbox.checked) {
      optionCheckboxes.forEach((checkbox) => {
        checkbox.checked = true;
      });
    }

    ensureFallback();
    syncAllCheckbox();
    applySelection();

    statCheckboxes.forEach((checkbox) => {
      checkbox.addEventListener("change", () => {
        handleChange(checkbox);
      });
    });
    return;
  }

  const statSelect = document.querySelector("[data-stat-select]");
  if (statSelect) {
    applyStats([statSelect.value || "todas"]);
    statSelect.addEventListener("change", () => {
      applyStats([statSelect.value]);
    });
  }
})();
