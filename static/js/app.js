/**
 * app.js — Main application controller
 * Initializes all modules, fetches data, manages page navigation
 */

import { t, getLang, setLang, toggleLang } from "./i18n.js";
import {
    getCachedRate,
    setCachedRate,
    isCacheStale,
    getCacheAge,
} from "./cache.js";
import { init as initConverter, setRate, formatNumber } from "./converter.js";
import { renderHistoryChart, initHistoryTabs } from "./chart.js";

const API_BASE = "/api";

// ── State ────────────────────────────────────────────────────────────

let currentPage = "home"; // 'home' or 'analytics'

// ── Boot ─────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", async () => {
    // Apply saved language
    const lang = getLang();
    setLang(lang);

    // Show cached rate instantly
    const cached = getCachedRate();
    if (cached) {
        displayRate(cached);
        initConverter(cached.average);
    }

    // Setup navigation & controls
    setupNavigation();
    setupLangToggle();
    setupThemeToggle();

    // Fetch fresh data if stale
    if (isCacheStale()) {
        fetchAndDisplayRate(); // Removed 'await' to let UI load instantly
    }

    // Render charts if on analytics page
    // (deferred until user navigates there)

    // Refresh on tab focus
    document.addEventListener("visibilitychange", async () => {
        if (!document.hidden) {
            if (isCacheStale()) {
                fetchAndDisplayRate(); // Removed 'await'
            }
            if (!ws || ws.readyState === WebSocket.CLOSED) {
                reconnectDelay = 1000;
                setupWebSocket();
            }
        }
    });

    // Setup WebSockets for extreme real-time
    setupWebSocket();

    // Apply translations
    applyTranslations();

    // Dynamically update the time ago text every minute
    setInterval(() => {
        const cached = getCachedRate();
        if (cached) displayRate(cached);
    }, 60000);
});

// ── WebSockets ───────────────────────────────────────────────────────

let ws;
let reconnectDelay = 1000;
const MAX_RECONNECT_DELAY = 30000;
let pingInterval;

function setupWebSocket() {
    // Prevent multiple connections
    if (ws && (ws.readyState === WebSocket.CONNECTING || ws.readyState === WebSocket.OPEN)) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${window.location.host}/api/ws`);

    ws.onopen = () => {
        console.log("WebSocket connected");
        reconnectDelay = 1000; // Reset backoff on success

        // Start pinging every 30s to keep connection alive
        pingInterval = setInterval(() => {
            if (ws.readyState === WebSocket.OPEN) {
                ws.send("ping");
            }
        }, 30000);
    };

    ws.onmessage = (event) => {
        if (event.data === "pong") return; // Ignore heartbeat responses

        try {
            const data = JSON.parse(event.data);

            // Reformat as expected by the UI
            const rateData = {
                average: data.average,
                penzi: data.penzi,
                sur: data.sur,
                daily_change: data.daily_change,
                last_updated: data.last_updated,
            };

            setCachedRate(rateData);
            displayRate(rateData);
            initConverter(data.average);
        } catch (err) {
            console.error("WS parsing error:", err);
        }
    };

    ws.onclose = () => {
        console.log(`WebSocket closed. Reconnecting in ${reconnectDelay}ms...`);
        clearInterval(pingInterval);
        setTimeout(setupWebSocket, reconnectDelay);
        reconnectDelay = Math.min(reconnectDelay * 2, MAX_RECONNECT_DELAY);
    };
}

// ── API Fetch ────────────────────────────────────────────────────────

async function fetchAndDisplayRate() {
    try {
        const res = await fetch(`${API_BASE}/rate/latest`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        const rateData = {
            average: data.average,
            penzi: data.penzi,
            sur: data.sur,
            daily_change: data.daily_change,
            last_updated: data.last_updated,
        };

        setCachedRate(rateData);
        displayRate(rateData);
        setRate(data.average);
        initConverter(data.average);
        hideOfflineBanner();
    } catch (err) {
        console.warn("Failed to fetch rate:", err);
        showOfflineBanner();
    }
}

// ── Display ──────────────────────────────────────────────────────────

function displayRate(data) {
    const rateEl = document.getElementById("main-rate");
    const perEl = document.getElementById("rate-per-100");
    const diffEl = document.getElementById("rate-diff");
    const diffIcon = document.getElementById("rate-diff-icon");
    const updatedEl = document.getElementById("rate-updated");

    if (rateEl) {
        rateEl.textContent = formatNumber(data.average);
    }

    if (perEl) {
        perEl.textContent = t("per_100");
    }

    // Direction indicator
    if (diffEl && data.daily_change !== undefined && data.daily_change !== null) {
        const diff = data.daily_change;
        const sign = diff > 0 ? "+" : "";

        let percentText = "";
        const prevAvg = data.average - diff;
        if (prevAvg > 0) {
            const pct = (diff / prevAvg) * 100;
            const pctSign = pct > 0 ? "+" : "";
            percentText = ` (${pctSign}${pct.toFixed(2)}%)`;
        }

        diffEl.textContent = `${sign}${formatNumber(diff)}${percentText}`;

        // Remove old color classes
        const parent = diffEl.closest("[data-diff-container]");
        if (parent) {
            parent.classList.remove(
                "text-green-500",
                "bg-green-500/10",
                "border-green-500/20",
                "text-red-500",
                "bg-red-500/10",
                "border-red-500/20"
            );
            if (diff >= 0) {
                parent.classList.add("text-green-500", "bg-green-500/10", "border-green-500/20");
            } else {
                parent.classList.add("text-red-500", "bg-red-500/10", "border-red-500/20");
            }
        }

        if (diffIcon) {
            diffIcon.textContent = diff >= 0 ? "trending_up" : "trending_down";
        }
    }

    // Updated time
    if (updatedEl && data.last_updated) {
        const updated = new Date(data.last_updated);
        // Use Math.max to prevent negative minutes (e.g., if server time is a few seconds ahead)
        const minsTotal = Math.max(0, Math.floor((Date.now() - updated.getTime()) / 60000));

        if (minsTotal < 1) {
            updatedEl.textContent = t("updated_just");
        } else if (minsTotal < 60) {
            updatedEl.textContent = t("updated_ago").replace("{n}", minsTotal);
        } else if (minsTotal < 1440) {
            const hrs = Math.floor(minsTotal / 60);
            const mins = minsTotal % 60;
            updatedEl.textContent = t("updated_hr_min").replace("{h}", hrs).replace("{m}", mins);
        } else {
            const days = Math.floor(minsTotal / 1440);
            const hrs = Math.floor((minsTotal % 1440) / 60);
            updatedEl.textContent = t("updated_day_hr").replace("{d}", days).replace("{h}", hrs);
        }
    }
}

// ── Navigation ───────────────────────────────────────────────────────

function setupNavigation() {
    const navHome = document.getElementById("nav-home");
    const navAnalytics = document.getElementById("nav-analytics");

    const homePage = document.getElementById("page-home");
    const analyticsPage = document.getElementById("page-analytics");

    if (navHome) {
        navHome.addEventListener("click", (e) => {
            e.preventDefault();
            showPage("home");
        });
    }

    if (navAnalytics) {
        navAnalytics.addEventListener("click", (e) => {
            e.preventDefault();
            showPage("analytics");
        });
    }

    // Back button on analytics
    const backBtn = document.getElementById("analytics-back");
    if (backBtn) {
        backBtn.addEventListener("click", () => showPage("home"));
    }
}

function showPage(page) {
    currentPage = page;
    const homePage = document.getElementById("page-home");
    const analyticsPage = document.getElementById("page-analytics");
    const navHome = document.getElementById("nav-home");
    const navAnalytics = document.getElementById("nav-analytics");

    if (page === "home") {
        homePage?.classList.remove("hidden");
        analyticsPage?.classList.add("hidden");
        // Update nav active states
        setNavActive(navHome, true);
        setNavActive(navAnalytics, false);
    } else {
        homePage?.classList.add("hidden");
        analyticsPage?.classList.remove("hidden");
        setNavActive(navHome, false);
        setNavActive(navAnalytics, true);
        // Load charts
        renderHistoryChart(1);
        initHistoryTabs();
    }
}

function setNavActive(el, active) {
    if (!el) return;
    const icon = el.querySelector(".material-symbols-outlined");
    const label = el.querySelector(":scope > span:last-child");

    if (active) {
        el.classList.remove("text-slate-400", "dark:text-slate-500");
        el.classList.add("text-primary");
        if (icon) icon.style.fontVariationSettings = "'FILL' 1";
    } else {
        el.classList.remove("text-primary");
        el.classList.add("text-slate-400", "dark:text-slate-500");
        if (icon) icon.style.fontVariationSettings = "'FILL' 0";
    }
}

// ── Language Toggle ──────────────────────────────────────────────────

function setupLangToggle() {
    const btn = document.getElementById("lang-toggle");
    if (!btn) return;

    btn.addEventListener("click", () => {
        toggleLang();
        applyTranslations();
    });
}

// ── Theme Toggle ────────────────────────────────────────────────────

function setupThemeToggle() {
    // Restore saved theme
    const saved = localStorage.getItem("theme");
    if (saved === "light") {
        document.documentElement.classList.remove("dark");
    } else if (saved === "dark") {
        document.documentElement.classList.add("dark");
    }
    // else: follow system default (CSS handles via prefers-color-scheme)

    const btn = document.getElementById("theme-toggle");
    if (!btn) return;

    btn.addEventListener("click", () => {
        const isDark = document.documentElement.classList.toggle("dark");
        localStorage.setItem("theme", isDark ? "dark" : "light");
    });
}

function applyTranslations() {
    // Update all elements with data-i18n attribute
    document.querySelectorAll("[data-i18n]").forEach((el) => {
        el.textContent = t(el.dataset.i18n);
    });

    // Update lang toggle flag icon
    const langFlag = document.getElementById("lang-flag");
    if (langFlag) {
        // Show the flag of the language you'll switch TO
        // Kurdish active → show US flag (tap to switch to English)
        // English active → show Kurdish flag (tap to switch to Kurdish)
        langFlag.src = getLang() === "ku" ? "/static/flags/us.svg" : "/static/flags/kurd.svg";
    }

    // Re-display rate with new translations
    const cached = getCachedRate();
    if (cached) displayRate(cached);
}

// ── Offline Banner ───────────────────────────────────────────────────

function showOfflineBanner() {
    let banner = document.getElementById("offline-banner");
    if (!banner) {
        banner = document.createElement("div");
        banner.id = "offline-banner";
        banner.className =
            "fixed top-0 left-0 right-0 z-[100] bg-amber-500/90 text-black text-center text-sm py-2 px-4 font-medium backdrop-blur-md transition-transform";
        document.body.prepend(banner);
    }

    const age = getCacheAge();
    let timeStr = "";
    if (age) {
        const hrs = Math.floor(age / 3600000);
        const mins = Math.floor((age % 3600000) / 60000);
        timeStr = hrs > 0 ? `${hrs}h ${mins}m` : `${mins}m`;
    }

    banner.textContent = t("offline_banner").replace("{time}", timeStr);
    banner.style.transform = "translateY(0)";
}

function hideOfflineBanner() {
    const banner = document.getElementById("offline-banner");
    if (banner) {
        banner.style.transform = "translateY(-100%)";
        setTimeout(() => banner.remove(), 300);
    }
}

// ── Unregister Old Service Workers ───────────────────────────────────
if ('serviceWorker' in navigator) {
    navigator.serviceWorker.getRegistrations().then(function (registrations) {
        for (let registration of registrations) {
            registration.unregister();
        }
    });
}
