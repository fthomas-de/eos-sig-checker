/*
 * Hide Cosmic Anomalies: the switch in the result header hides the rows
 * marked data-eos-sig-checker-anomaly and points the Copy button at the
 * list without them (data-eos-sig-checker-copy-signatures), so Copy takes
 * what is shown. On by default; switched off, it stays off in every tab
 * (localStorage) until switched on again.
 */
document.addEventListener("DOMContentLoaded", () => {
    "use strict";

    const toggle = document.getElementById("eos-sig-checker-hide-anomalies");
    if (!toggle) {
        return;
    }

    const key = "eos_sig_checker.show_anomalies";
    const copy = document.querySelector("[data-eos-sig-checker-copy-signatures]");
    const everything = copy?.dataset.eosSigCheckerCopy;

    // storage can be blocked (private mode, site data off): then the
    // switch starts on with every page
    try {
        toggle.checked = window.localStorage.getItem(key) !== "1";
    } catch {
        // see above
    }

    const apply = () => {
        document.querySelectorAll("[data-eos-sig-checker-anomaly]").forEach((row) => {
            row.classList.toggle("d-none", toggle.checked);
        });
        if (copy) {
            copy.dataset.eosSigCheckerCopy = toggle.checked ? copy.dataset.eosSigCheckerCopySignatures : everything;
        }
    };

    toggle.addEventListener("change", () => {
        try {
            if (toggle.checked) {
                window.localStorage.removeItem(key);
            } else {
                window.localStorage.setItem(key, "1");
            }
        } catch {
            // see above
        }
        apply();
    });

    apply();
});
