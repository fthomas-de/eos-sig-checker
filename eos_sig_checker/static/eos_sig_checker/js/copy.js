/*
 * Copy button: a button marked data-eos-sig-checker-copy="<text>" puts the
 * text on the clipboard - the completed paste, tab-separated like the probe
 * scanner's own copy - and says so for a moment (data-eos-sig-checker-copied).
 * The Clipboard API needs HTTPS; over plain HTTP the older execCommand route
 * takes over.
 */
document.addEventListener("DOMContentLoaded", () => {
    "use strict";

    const fallback = (text) => {
        const area = document.createElement("textarea");
        area.value = text;
        area.setAttribute("readonly", "");
        area.style.position = "fixed";
        area.style.opacity = "0";
        document.body.appendChild(area);
        area.select();
        try {
            document.execCommand("copy");
        } finally {
            document.body.removeChild(area);
        }
    };

    const confirm = (button) => {
        const label = button.querySelector("span");
        const icon = button.querySelector("i");
        if (!label || button.dataset.eosSigCheckerCopying) {
            return;
        }
        button.dataset.eosSigCheckerCopying = "1";
        const text = label.textContent;
        label.textContent = button.dataset.eosSigCheckerCopied || text;
        icon?.classList.replace("fa-copy", "fa-check");
        window.setTimeout(() => {
            label.textContent = text;
            icon?.classList.replace("fa-check", "fa-copy");
            delete button.dataset.eosSigCheckerCopying;
        }, 1500);
    };

    document.querySelectorAll("[data-eos-sig-checker-copy]").forEach((button) => {
        button.addEventListener("click", () => {
            const text = button.dataset.eosSigCheckerCopy || "";
            if (navigator.clipboard && window.isSecureContext) {
                navigator.clipboard.writeText(text).then(
                    () => confirm(button),
                    () => {
                        fallback(text);
                        confirm(button);
                    },
                );
            } else {
                fallback(text);
                confirm(button);
            }
        });
    });
});
