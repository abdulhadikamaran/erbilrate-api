/**
 * chart.js — Chart rendering for today's hourly and history tabs
 * Uses inline SVG (matching the design files) for lightweight rendering
 */

import { getCachedHistory, setCachedHistory } from "./cache.js";
import { t } from "./i18n.js";

const API_BASE = "/api";

// ── Today's hourly chart (Removed) ───────────────────────────────────

// ── History chart ────────────────────────────────────────────────────

let currentHistoryDays = 1;

export async function renderHistoryChart(days = 1) {
    currentHistoryDays = days;
    const container = document.getElementById("history-chart");
    const labelContainer = document.getElementById("history-labels");
    const highEl = document.getElementById("history-high");
    const lowEl = document.getElementById("history-low");

    if (!container) return;

    try {
        // Try cache first
        let rates = getCachedHistory(days);

        if (!rates) {
            const res = await fetch(`${API_BASE}/rate/history?days=${days}`);
            if (!res.ok) throw new Error("API error");
            const data = await res.json();
            rates = data.rates || [];
            setCachedHistory(days, rates);
        }

        if (rates.length === 0) {
            container.innerHTML = `<p class="text-center text-slate-400 py-8">${t("no_data")}</p>`;
            return;
        }

        // Hide drilldown initially
        document.getElementById("hourly-drilldown")?.classList.add("hidden");

        // Use DB aggregated data directly
        const keys = [];
        const values = [];
        const sortedRates = [...rates].reverse(); // oldest first
        const dailyDrillData = {};

        if (days === 1) {
            for (const r of sortedRates) {
                values.push(r.average);
                keys.push(new Date(r.last_updated).getHours().toString().padStart(2, '0'));
            }
        } else if (days <= 7) {
            // Group the hourly DB data into daily averages for the top chart
            const daily = {};
            const counts = {};
            for (const r of sortedRates) {
                const dateStr = r.last_updated.split("T")[0];
                const hourStr = new Date(r.last_updated).getHours().toString().padStart(2, '0');
                if (!daily[dateStr]) {
                    daily[dateStr] = 0;
                    counts[dateStr] = 0;
                    dailyDrillData[dateStr] = [];
                }
                daily[dateStr] += r.average;
                counts[dateStr]++;
                dailyDrillData[dateStr].push({ hour: hourStr, average: r.average });
            }
            for (const d in daily) {
                keys.push(d);
                values.push(Math.round(daily[d] / counts[d]));
            }
        } else {
            // Already daily average
            for (const r of sortedRates) {
                values.push(r.average);
                keys.push(r.last_updated.split("T")[0]);
            }
        }

        const min = Math.min(...values);
        const max = Math.max(...values);
        const range = max - min || 1;

        if (highEl) highEl.textContent = max.toLocaleString();
        if (lowEl) lowEl.textContent = min.toLocaleString();

        // Update High/Low labels based on selected period
        const highLabel = document.getElementById("history-high-label");
        const lowLabel = document.getElementById("history-low-label");
        if (highLabel && lowLabel) {
            if (days === 1) {
                highLabel.textContent = t("daily_high");
                lowLabel.textContent = t("daily_low");
            } else if (days <= 7) {
                highLabel.textContent = t("weekly_high");
                lowLabel.textContent = t("weekly_low");
            } else if (days <= 30) {
                highLabel.textContent = t("monthly_high");
                lowLabel.textContent = t("monthly_low");
            } else {
                highLabel.textContent = t("period_high");
                lowLabel.textContent = t("period_low");
            }
        }

        // Build SVG
        const width = 300;
        const height = 150;
        const padding = 10;
        const paddingX = 15; // Extra padding so circles don't touch Y-axis

        const points = values.map((v, i) => {
            const x = values.length === 1 ? width / 2 : paddingX + (i / (values.length - 1)) * (width - 2 * paddingX);
            const y = padding + ((max - v) / range) * (height - 2 * padding);
            return { x, y };
        });

        const pathD = buildSmoothPath(points);
        const isDark = document.documentElement.classList.contains("dark");
        const color = isDark ? "#f0b429" : "#2563eb";

        // Grid lines at 25%, 50%, 75% height
        const gridLines = [0.25, 0.5, 0.75].map(
            (f) =>
                `<line x1="0" y1="${f * height}" x2="${width}" y2="${f * height}" stroke="${isDark ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.05)"}" stroke-dasharray="4,4"/>`
        ).join("");

        // Y-axis price labels — exact values
        const yAxisEl = document.getElementById("history-y-axis");
        if (yAxisEl) {
            const mid = Math.round(min + range / 2);
            yAxisEl.innerHTML = `
              <span class="text-[10px] font-medium text-slate-400 dark:text-slate-500 leading-none">${max.toLocaleString()}</span>
              <span class="text-[10px] font-medium text-slate-400 dark:text-slate-500 leading-none">${mid.toLocaleString()}</span>
              <span class="text-[10px] font-medium text-slate-400 dark:text-slate-500 leading-none">${min.toLocaleString()}</span>
            `;
        }

        // Data point circles — no CSS transforms (they break with preserveAspectRatio="none")
        const circles = points
            .map((p, i) => {
                const r = i === points.length - 1 ? 5 : 4;
                const fill = i === points.length - 1 ? color : (isDark ? "#1a242e" : "#ffffff");

                // Tooltip data
                const val = values[i].toLocaleString();
                let label = keys[i];
                if (days === 1) {
                    label = `${label}:00`;
                } else if (days <= 7) {
                    const d = new Date(keys[i]);
                    const dayNames = [t("sun"), t("mon"), t("tue"), t("wed"), t("thu"), t("fri"), t("sat")];
                    label = `${dayNames[d.getDay()]} ${d.getMonth() + 1}/${d.getDate()}`;
                } else {
                    const d = new Date(keys[i]);
                    label = `${d.getMonth() + 1}/${d.getDate()}`;
                }

                // Visible circle + invisible fat touch target (no transforms!)
                return `<circle cx="${p.x}" cy="${p.y}" r="${r}" fill="${fill}" stroke="${color}" stroke-width="2" class="pointer-events-none" />
                        <circle cx="${p.x}" cy="${p.y}" r="12" fill="transparent" stroke="transparent" data-idx="${i}" data-val="${val}" data-lbl="${label}" class="chart-point" style="cursor:pointer;" />`;
            })
            .join("");

        container.innerHTML = `
      <svg class="w-full h-full overflow-visible" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">
        ${gridLines}
        <path d="${pathD}" fill="none" stroke="${color}" stroke-width="3" stroke-linecap="round"/>
        ${circles}
      </svg>
      <div id="chart-tooltip" class="absolute pointer-events-none opacity-0 transition-opacity duration-150 bg-slate-900/95 dark:bg-black/95 text-white text-[11px] py-2 px-3 rounded-lg shadow-xl border border-white/10 z-50 whitespace-nowrap" style="transform: translate(-50%, -100%); margin-top: -12px;">
          <span id="tooltip-val" class="font-bold text-primary"></span>
          <span class="mx-1 text-slate-500">·</span>
          <span id="tooltip-label" class="text-slate-300"></span>
      </div>
    `;

        // Tooltip positioning using getBoundingClientRect (pixel-perfect on all screens)
        const tooltip = container.querySelector("#chart-tooltip");
        const tVal = container.querySelector("#tooltip-val");
        const tLbl = container.querySelector("#tooltip-label");
        const svg = container.querySelector("svg");

        container.querySelectorAll("circle.chart-point").forEach(c => {
            const show = () => {
                if (!tooltip || !tVal || !tLbl || !svg) return;
                tVal.textContent = c.getAttribute("data-val");
                tLbl.textContent = c.getAttribute("data-lbl");

                // Convert SVG coords to container pixel coords
                const svgRect = svg.getBoundingClientRect();
                const containerRect = container.getBoundingClientRect();
                const cx = parseFloat(c.getAttribute("cx"));
                const cy = parseFloat(c.getAttribute("cy"));
                const pixelX = (cx / width) * svgRect.width + (svgRect.left - containerRect.left);
                const pixelY = (cy / height) * svgRect.height + (svgRect.top - containerRect.top);

                // Prevent tooltip from getting cut off on edges
                if (pixelX > containerRect.width - 60) {
                    tooltip.style.transform = "translate(calc(-100% + 8px), -100%)";
                } else if (pixelX < 60) {
                    tooltip.style.transform = "translate(-8px, -100%)";
                } else {
                    tooltip.style.transform = "translate(-50%, -100%)";
                }

                tooltip.style.left = `${pixelX}px`;
                tooltip.style.top = `${pixelY}px`;
                tooltip.style.opacity = "1";
            };

            const hide = () => { if (tooltip) tooltip.style.opacity = "0"; };

            c.addEventListener("mouseenter", show);
            c.addEventListener("mouseleave", hide);
            c.addEventListener("touchstart", (e) => {
                e.preventDefault();
                show();
                // Auto-hide after 2s on mobile
                setTimeout(hide, 2000);
            }, { passive: false });
        });

        // 7D drilldown click
        if (days === 7) {
            container.querySelectorAll("circle.chart-point").forEach(c => {
                c.addEventListener("click", () => {
                    const idx = c.getAttribute("data-idx");
                    const dateKey = keys[idx];
                    if (dailyDrillData[dateKey]) {
                        renderDrillDown(dateKey, dailyDrillData[dateKey], isDark, color);
                    }
                });
            });
        }

        if (labelContainer) {
            const numPoints = keys.length;
            let labelIndices = [];

            if (days === 1) {
                const step = Math.ceil((numPoints - 1) / 4);
                for (let i = 0; i < numPoints; i += step) labelIndices.push(i);
                if (numPoints > 0 && labelIndices[labelIndices.length - 1] !== numPoints - 1) labelIndices.push(numPoints - 1);
            } else if (days <= 7) {
                labelIndices = keys.map((_, i) => i);
            } else {
                const step = Math.ceil((numPoints - 1) / 5);
                for (let i = 0; i < numPoints; i += step) labelIndices.push(i);
                if (numPoints > 0 && labelIndices[labelIndices.length - 1] !== numPoints - 1) labelIndices.push(numPoints - 1);
            }

            labelContainer.innerHTML = labelIndices.map(i => {
                let l = keys[i];
                if (days === 1) {
                    l = `${l}:00`;
                } else if (days <= 7) {
                    const d = new Date(l);
                    const dayNames = [t("sun"), t("mon"), t("tue"), t("wed"), t("thu"), t("fri"), t("sat")];
                    l = dayNames[d.getDay()];
                } else {
                    const d = new Date(l);
                    l = `${d.getMonth() + 1}/${d.getDate()}`;
                }

                const xPercent = numPoints === 1 ? 50 : ((paddingX + (i / (numPoints - 1)) * (width - 2 * paddingX)) / width) * 100;
                return `<span class="absolute top-0 whitespace-nowrap" style="left: ${xPercent}%; transform: translateX(-50%);">${l}</span>`;
            }).join("");
        }
    } catch (err) {
        console.warn("History chart error:", err);
        if (container)
            container.innerHTML = `<p class="text-center text-slate-400 py-8">${t("no_data")}</p>`;
    }
}

export function initHistoryTabs() {
    const tabs = document.querySelectorAll("[data-history-tab]");
    tabs.forEach((tab) => {
        tab.addEventListener("click", () => {
            const days = parseInt(tab.dataset.historyTab);
            // Update active style
            tabs.forEach((t) => {
                t.classList.remove(
                    "bg-white",
                    "dark:bg-primary",
                    "text-slate-900",
                    "dark:text-background-dark",
                    "shadow-sm"
                );
                t.classList.add("text-slate-500", "dark:text-text-muted");
            });
            tab.classList.add(
                "bg-white",
                "dark:bg-primary",
                "text-slate-900",
                "dark:text-background-dark",
                "shadow-sm"
            );
            tab.classList.remove("text-slate-500", "dark:text-text-muted");
            renderHistoryChart(days);
        });
    });

    const closeBtn = document.getElementById("close-drilldown");
    if (closeBtn) {
        closeBtn.addEventListener("click", () => {
            document.getElementById("hourly-drilldown")?.classList.add("hidden");
        });
    }
}

function renderDrillDown(dateStr, hourlyData, isDark, color) {
    const drillContainer = document.getElementById("hourly-drilldown");
    const chartDiv = document.getElementById("drilldown-chart");
    const labelsDiv = document.getElementById("drilldown-labels");
    const titleSpan = document.getElementById("drilldown-title");

    if (!drillContainer || !chartDiv || !labelsDiv) return;

    titleSpan.textContent = dateStr;
    drillContainer.classList.remove("hidden");

    if (hourlyData.length === 0) {
        chartDiv.innerHTML = `<p class="text-center text-slate-400 py-4">${t("no_data")}</p>`;
        return;
    }

    const values = hourlyData.map(d => d.average);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min || 1;

    const width = 300;
    const height = 120;
    const padding = 10;
    const paddingX = 15;

    const points = values.map((v, i) => {
        const x = values.length === 1 ? width / 2 : paddingX + (i / (values.length - 1)) * (width - 2 * paddingX);
        const y = padding + ((max - v) / range) * (height - 2 * padding);
        return { x, y };
    });

    const pathD = buildSmoothPath(points);
    const fillD = `${pathD} V${height} H0 Z`;

    const gradId = "gradientDrilldown";

    const circlesHTML = points.map((p, i) => {
        const val = values[i].toLocaleString();
        const lbl = `${hourlyData[i].hour}:00`;
        return `<circle cx="${p.x}" cy="${p.y}" r="3" fill="${color}" stroke="${color}" stroke-width="1" class="pointer-events-none" />
                <circle cx="${p.x}" cy="${p.y}" r="10" fill="transparent" stroke="transparent" data-val="${val}" data-lbl="${lbl}" class="drilldown-point" style="cursor:pointer;" />`;
    }).join("");

    chartDiv.innerHTML = `
      <svg class="w-full h-full overflow-visible" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">
        <defs>
          <linearGradient id="${gradId}" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="${color}" stop-opacity="0.2"/>
            <stop offset="100%" stop-color="${color}" stop-opacity="0"/>
          </linearGradient>
        </defs>
        <path d="${fillD}" fill="url(#${gradId})"/>
        <path d="${pathD}" fill="none" stroke="${color}" stroke-width="2" stroke-linecap="round"/>
        ${circlesHTML}
      </svg>
      <div id="drilldown-tooltip" class="absolute pointer-events-none opacity-0 transition-opacity duration-150 bg-slate-900/95 dark:bg-black/95 text-white text-[11px] py-2 px-3 rounded-lg shadow-xl border border-white/10 z-50 whitespace-nowrap" style="transform: translate(-50%, -100%); margin-top: -12px;">
          <span id="dt-val" class="font-bold text-primary"></span>
          <span class="mx-1 text-slate-500">·</span>
          <span id="dt-lbl" class="text-slate-300"></span>
      </div>
    `;

    const dTooltip = chartDiv.querySelector("#drilldown-tooltip");
    const dtVal = chartDiv.querySelector("#dt-val");
    const dtLbl = chartDiv.querySelector("#dt-lbl");
    const ddSvg = chartDiv.querySelector("svg");

    chartDiv.querySelectorAll("circle.drilldown-point").forEach((c) => {
        const show = () => {
            if (!dTooltip || !dtVal || !dtLbl || !ddSvg) return;
            dtVal.textContent = c.getAttribute("data-val");
            dtLbl.textContent = c.getAttribute("data-lbl");

            const svgRect = ddSvg.getBoundingClientRect();
            const containerRect = chartDiv.getBoundingClientRect();
            const cx = parseFloat(c.getAttribute("cx"));
            const cy = parseFloat(c.getAttribute("cy"));
            const pixelX = (cx / width) * svgRect.width + (svgRect.left - containerRect.left);
            const pixelY = (cy / height) * svgRect.height + (svgRect.top - containerRect.top);

            // Prevent tooltip from getting cut off on edges
            if (pixelX > containerRect.width - 60) {
                dTooltip.style.transform = "translate(calc(-100% + 8px), -100%)";
            } else if (pixelX < 60) {
                dTooltip.style.transform = "translate(-8px, -100%)";
            } else {
                dTooltip.style.transform = "translate(-50%, -100%)";
            }

            dTooltip.style.left = `${pixelX}px`;
            dTooltip.style.top = `${pixelY}px`;
            dTooltip.style.opacity = "1";
        };
        const hide = () => { if (dTooltip) dTooltip.style.opacity = "0"; };
        c.addEventListener("mouseenter", show);
        c.addEventListener("mouseleave", hide);
        c.addEventListener("touchstart", (e) => {
            e.preventDefault();
            show();
            setTimeout(hide, 2000);
        }, { passive: false });
    });

    const numPoints = hourlyData.length;
    let labelIndices = [];
    const step = Math.ceil((numPoints - 1) / 4);
    for (let i = 0; i < numPoints; i += step) labelIndices.push(i);
    if (numPoints > 0 && labelIndices[labelIndices.length - 1] !== numPoints - 1) labelIndices.push(numPoints - 1);

    labelsDiv.innerHTML = labelIndices.map((i) => {
        const h = hourlyData[i].hour;
        const xPercent = numPoints === 1 ? 50 : ((paddingX + (i / (numPoints - 1)) * (width - 2 * paddingX)) / width) * 100;
        return `<span class="absolute top-0 whitespace-nowrap" style="left: ${xPercent}%; transform: translateX(-50%);">${h}:00</span>`;
    }).join("");
}

// ── Helpers ──────────────────────────────────────────────────────────

// Helper removed since DB handles aggregations

function buildSmoothPath(points) {
    if (points.length === 0) return "";
    if (points.length === 1) return `M${points[0].x},${points[0].y}`;

    let d = `M${points[0].x},${points[0].y}`;
    for (let i = 1; i < points.length; i++) {
        const prev = points[i - 1];
        const curr = points[i];
        const cpx = (prev.x + curr.x) / 2;
        d += ` C${cpx},${prev.y} ${cpx},${curr.y} ${curr.x},${curr.y}`;
    }
    return d;
}
