// Toggle the spreadsheet preview without leaving the mapping review.

document.querySelectorAll("[data-preview-toggle]").forEach((button) => {
    const preview = document.getElementById(button.getAttribute("aria-controls"));
    if (!preview) {
        return;
    }

    button.addEventListener("click", () => {
        const isExpanded = button.getAttribute("aria-expanded") === "true";
        button.setAttribute("aria-expanded", String(!isExpanded));
        button.textContent = isExpanded ? "Show preview" : "Hide preview";
        preview.hidden = isExpanded;
    });
});
