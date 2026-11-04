/*
 * The signature list: a sortable DataTable with one filter field per column
 * instead of DataTables' single search box. Each input marked
 * data-eos-sig-checker-column="<index>" searches that column only, and the
 * fields combine. The filters go through DataTables' own column search, not
 * by hiding rows: that would miss the rows on other pages. Cells sort by
 * their data-order where they have one (signal as a number, dates as ISO).
 */
document.addEventListener("DOMContentLoaded", () => {
    "use strict";

    const PAGE_LENGTHS = [25, 50, 100, 250, 500];
    const PAGE_LENGTH = 100;

    const element = document.querySelector("table.eos-sig-checker-signatures");
    if (!element) {
        return;
    }

    // Alliance Auth's DataTables translation for the viewer's language;
    // empty for English, where DataTables needs none
    const languageUrl = element.dataset.eosSigCheckerDatatablesLanguage || "";

    const table = new DataTable(element, {
        ...(languageUrl ? { language: { url: languageUrl } } : {}),
        pageLength: PAGE_LENGTH,
        lengthMenu: PAGE_LENGTHS,
        // searching stays on for the column filters; the global box is left out
        layout: { topEnd: null },
        autoWidth: false,
        // keep the server's order (last checked first) until a header is clicked
        order: [],
        columnDefs: [{ targets: "_all", className: "dt-left" }],
    });

    document.querySelectorAll("input[data-eos-sig-checker-column]").forEach((input) => {
        const column = table.column(Number(input.dataset.eosSigCheckerColumn));
        input.addEventListener("input", () => {
            column.search(input.value).draw();
        });
    });
});
