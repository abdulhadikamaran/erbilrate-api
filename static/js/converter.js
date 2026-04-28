/**
 * converter.js — Real-time USD ↔ IQD converter
 * Pure client-side math using cached rate. No API calls per keystroke.
 */

let currentRate = 0; // average IQD per $100
let isSwapped = false; // false = USD→IQD, true = IQD→USD
let isInitialized = false;

export function setRate(avg) {
    currentRate = avg;
}

export function getRate() {
    return currentRate;
}

function formatInputText(val) {
    if (!val) return "";
    const parts = val.toString().replace(/[^0-9.]/g, '').split('.');
    if (parts.length > 2) parts.length = 2; // only one decimal point
    parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    return parts.join('.');
}

export function init(rate) {
    currentRate = rate;

    const usdInput = document.getElementById("usd-input");
    const iqdInput = document.getElementById("iqd-input");
    const swapBtn = document.getElementById("swap-btn");
    const usdClear = document.getElementById("usd-clear");
    const iqdClear = document.getElementById("iqd-clear");

    if (!usdInput || !iqdInput) return;

    // Set initial default to 100 only on first load
    if (!isInitialized) {
        usdInput.value = "100";
    }

    // Re-calculate math with the fresh background rate
    if (isSwapped) updateReverseConversion();
    else updateConversion();

    // PREVENT duplicate event listeners breaking the Swap button!
    if (isInitialized) return;
    isInitialized = true;

    function handleInput(e, isReverse) {
        const cursor = e.target.selectionStart;
        const oldLen = e.target.value.length;

        e.target.value = formatInputText(e.target.value);

        const newLen = e.target.value.length;
        const newCursor = cursor + (newLen - oldLen);
        if (newCursor >= 0) {
            e.target.setSelectionRange(newCursor, newCursor);
        }

        if (isReverse && isSwapped) updateReverseConversion();
        else if (!isReverse && !isSwapped) updateConversion();
    }

    // Real-time on every keystroke
    usdInput.addEventListener("input", (e) => handleInput(e, false));
    iqdInput.addEventListener("input", (e) => handleInput(e, true));

    // Clear buttons logic
    if (usdClear) {
        usdClear.addEventListener("click", () => {
            if (!isSwapped) {
                usdInput.value = "";
                updateConversion();
            }
        });
    }

    if (iqdClear) {
        iqdClear.addEventListener("click", () => {
            if (isSwapped) {
                iqdInput.value = "";
                updateReverseConversion();
            }
        });
    }

    // Swap button
    if (swapBtn) {
        swapBtn.addEventListener("click", () => {
            isSwapped = !isSwapped;
            const icon = swapBtn.querySelector(".material-symbols-outlined");
            if (icon) {
                icon.style.transition = "transform 0.3s ease";
                icon.style.transform = isSwapped ? "rotate(180deg)" : "rotate(0deg)";
            }

            const usdContainer = document.getElementById("usd-container");
            const iqdContainer = document.getElementById("iqd-container");

            // Transfer the value they typed to the new top input
            const activeValue = isSwapped ? usdInput.value : iqdInput.value;

            // Swap input editability and visual order
            if (isSwapped) {
                if (usdContainer && iqdContainer) {
                    usdContainer.style.order = "2";
                    iqdContainer.style.order = "1";
                }
                usdInput.readOnly = true;
                iqdInput.readOnly = false;
                iqdInput.setAttribute("inputmode", "decimal");
                usdInput.removeAttribute("inputmode");
                iqdInput.classList.remove("pointer-events-none");
                usdInput.classList.add("pointer-events-none");

                // Move the typed value
                iqdInput.value = activeValue;
                // Convert current IQD back to USD
                updateReverseConversion();
            } else {
                if (usdContainer && iqdContainer) {
                    usdContainer.style.order = "1";
                    iqdContainer.style.order = "2";
                }
                usdInput.readOnly = false;
                iqdInput.readOnly = true;
                usdInput.setAttribute("inputmode", "decimal");
                iqdInput.removeAttribute("inputmode");
                iqdInput.classList.add("pointer-events-none");
                usdInput.classList.remove("pointer-events-none");

                // Move the typed value
                usdInput.value = activeValue;
                updateConversion();
            }
        });
    }
}

function updateConversion() {
    const usdInput = document.getElementById("usd-input");
    const iqdInput = document.getElementById("iqd-input");
    const usdClear = document.getElementById("usd-clear");
    const iqdClear = document.getElementById("iqd-clear");
    if (!usdInput || !iqdInput || !currentRate) return;

    if (usdClear) usdClear.classList.toggle("hidden", !usdInput.value || isSwapped);
    if (iqdClear) iqdClear.classList.add("hidden"); // iqd is readonly here

    if (!usdInput.value) {
        iqdInput.value = "";
        return;
    }

    const usd = parseFloat(usdInput.value.replace(/,/g, '')) || 0;
    const iqd = usd * (currentRate / 100);
    iqdInput.value = formatNumber(Math.round(iqd));
}

function updateReverseConversion() {
    const usdInput = document.getElementById("usd-input");
    const iqdInput = document.getElementById("iqd-input");
    const usdClear = document.getElementById("usd-clear");
    const iqdClear = document.getElementById("iqd-clear");
    if (!usdInput || !iqdInput || !currentRate) return;

    if (iqdClear) iqdClear.classList.toggle("hidden", !iqdInput.value || !isSwapped);
    if (usdClear) usdClear.classList.add("hidden"); // usd is readonly here

    if (!iqdInput.value) {
        usdInput.value = "";
        return;
    }

    const iqd = parseFloat(iqdInput.value.replace(/,/g, '')) || 0;
    const usd = iqd / (currentRate / 100);
    const usdStr = Number.isInteger(usd) ? usd.toString() : usd.toFixed(2);
    usdInput.value = formatInputText(usdStr);
}

export function formatNumber(num) {
    return num.toLocaleString("en-US");
}
