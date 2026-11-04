/*
 * Location tracking, one character per browser tab.
 *
 * The server reads the tracked character from ?character=<id> in the page
 * URL (the paste form posts to the same URL), so each tab tracks its own.
 * The choice is kept in sessionStorage, which belongs to the tab: the menu
 * link without ?character= brings the tab back to its character, while a
 * new tab starts with tracking off.
 *
 * While tracking, the tab asks the server for the character's system every
 * data-eos-sig-checker-interval ms and reloads the page when it changed, so
 * the list of the new system shows without a paste. Refresh asks at once,
 * at most once per data-eos-sig-checker-refresh ms.
 */
document.addEventListener("DOMContentLoaded", () => {
    "use strict";

    const bar = document.querySelector("[data-eos-sig-checker-tracking]");
    const toggle = document.getElementById("eos-sig-checker-tracking-switch");
    const select = document.getElementById("eos-sig-checker-tracking-character");
    const refresh = document.getElementById("eos-sig-checker-tracking-refresh");
    const systemName = document.getElementById("eos-sig-checker-tracking-system");
    const age = document.getElementById("eos-sig-checker-tracking-age");
    const alert = document.getElementById("eos-sig-checker-tracking-error");
    if (!bar || !toggle) {
        return;
    }

    const key = "eos_sig_checker.tracked_character";
    const locationUrl = bar.dataset.eosSigCheckerLocationUrl;
    const tracked = bar.dataset.eosSigCheckerCharacter;
    const shownSystem = bar.dataset.eosSigCheckerSystem;
    const interval = Number(bar.dataset.eosSigCheckerInterval) || 10000;
    const refreshGap = Number(bar.dataset.eosSigCheckerRefresh) || 5000;

    // storage can be blocked (private mode, site data off): then tracking
    // still works, only the menu link turns it off
    const stored = () => {
        try {
            return window.sessionStorage.getItem(key) || "";
        } catch {
            return "";
        }
    };
    const store = (value) => {
        try {
            if (value) {
                window.sessionStorage.setItem(key, value);
            } else {
                window.sessionStorage.removeItem(key);
            }
        } catch {
            // see above
        }
    };

    const isOwn = (id) => Boolean(select) && Array.from(select.options).some((option) => option.value === id);

    // a GET, never a reload of a POST: the browser would ask to resend the paste
    const open = (id) => {
        const url = new URL(window.location.href);
        url.search = "";
        if (id) {
            url.searchParams.set("character", id);
        }
        window.location.replace(url.toString());
    };

    // the tab's choice, unless the URL names another (a bookmark, a link)
    const wanted = tracked || stored();
    if (wanted && !isOwn(wanted)) {
        // a character the user no longer has, or no token any more: the
        // server's message stays on the page, but the tab forgets the choice
        store("");
        if (tracked) {
            toggle.addEventListener("change", () => open(""));
            return;
        }
    } else if (wanted !== tracked) {
        open(wanted);
        return;
    } else if (tracked) {
        store(tracked);
    }

    toggle.addEventListener("change", () => {
        const id = toggle.checked ? select.value : "";
        store(id);
        open(id);
    });

    select?.addEventListener("change", () => {
        if (toggle.checked) {
            store(select.value);
            open(select.value);
        }
    });

    if (!tracked) {
        return;
    }

    const ageText = bar.dataset.eosSigCheckerAgeText || "{seconds} s";
    const unreachableText = bar.dataset.eosSigCheckerUnreachableText || "";

    let timer = null;
    let lastAsked = 0;
    // when the position shown was read; the page itself was rendered with it
    let readAt = shownSystem ? Date.now() : 0;

    const showAge = () => {
        if (age) {
            age.textContent = readAt ? ageText.replace("{seconds}", Math.round((Date.now() - readAt) / 1000)) : "";
        }
    };

    // the last position stays on screen; the message says why it may be old
    const showError = (message) => {
        if (alert) {
            alert.querySelector("span").textContent = message;
            alert.classList.remove("d-none");
        }
    };

    const clearError = () => {
        alert?.classList.add("d-none");
    };

    const ask = async () => {
        window.clearTimeout(timer);
        lastAsked = Date.now();
        try {
            const url = new URL(locationUrl, window.location.href);
            url.searchParams.set("character", tracked);
            const response = await fetch(url, { headers: { Accept: "application/json" }, credentials: "same-origin" });
            const data = await response.json().catch(() => ({}));
            if (!response.ok) {
                showError(data.error || `${response.status} ${response.statusText}`);
            } else if (String(data.system_id) !== shownSystem) {
                // a new system: the server renders its list
                open(tracked);
                return;
            } else {
                readAt = Date.now();
                if (systemName) {
                    systemName.textContent = data.system_name;
                }
                clearError();
                showAge();
            }
        } catch {
            // a network failure, the server restarting or the session gone
            showError(unreachableText);
        }
        timer = window.setTimeout(ask, interval);
    };

    showAge();
    window.setInterval(showAge, 1000);

    if (refresh) {
        refresh.addEventListener("click", () => {
            if (Date.now() - lastAsked < refreshGap) {
                return;
            }
            refresh.disabled = true;
            window.setTimeout(() => {
                refresh.disabled = false;
            }, refreshGap);
            ask();
        });
    }

    timer = window.setTimeout(ask, interval);
});
