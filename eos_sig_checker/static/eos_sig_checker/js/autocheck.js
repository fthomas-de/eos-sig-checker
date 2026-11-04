/*
 * Check on paste: Ctrl+V (or the context menu) into the probe scanner box
 * submits the form, so the result shows without pressing Check.
 *
 * At most one check per data-eos-sig-checker-interval milliseconds: a paste
 * inside that time waits for the rest of it and then checks what the box
 * holds by then. The page reloads with every check, so the time of the last
 * one is kept in sessionStorage. The server enforces the same limit; this
 * only spares the request it would refuse.
 */
document.addEventListener("DOMContentLoaded", () => {
    "use strict";

    const form = document.querySelector("form[data-eos-sig-checker-interval]");
    const area = form?.querySelector("textarea");
    if (!form || !area) {
        return;
    }

    const interval = Number(form.dataset.eosSigCheckerInterval) || 1000;
    const key = "eos_sig_checker.last_check";

    // storage can be blocked (private mode, site data off): then only the
    // pending timer guards, which is enough within one page
    const lastCheck = () => {
        try {
            return Number(window.sessionStorage.getItem(key)) || 0;
        } catch {
            return 0;
        }
    };
    const remember = () => {
        try {
            window.sessionStorage.setItem(key, String(Date.now()));
        } catch {
            // see above
        }
    };

    let pending = null;
    let submitting = false;

    const submit = () => {
        pending = null;
        if (submitting || !area.value.trim()) {
            return;
        }
        submitting = true;
        remember();
        form.requestSubmit();
    };

    // a click on Check counts as well, so a paste right after it waits
    form.addEventListener("submit", () => {
        submitting = true;
        remember();
    });

    area.addEventListener("paste", () => {
        if (pending !== null || submitting) {
            return;
        }
        // the pasted text is in the box only after this event
        // capped: a clock set back must not hold the check for hours
        const wait = Math.min(interval, Math.max(0, lastCheck() + interval - Date.now()));
        pending = window.setTimeout(submit, wait);
    });
});
