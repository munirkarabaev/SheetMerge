// Toggle the spreadsheet preview without leaving the mapping review.

document.querySelectorAll("[data-preview-toggle]").forEach((button) => {
    const preview = document.getElementById(button.getAttribute("aria-controls"));
    if (!preview) {
        return;
    }

    button.addEventListener("click", () => {
        const isExpanded = button.getAttribute("aria-expanded") === "true";
        const showText = button.dataset.toggleShow || "Show preview";
        const hideText = button.dataset.toggleHide || "Hide preview";
        button.setAttribute("aria-expanded", String(!isExpanded));
        button.textContent = isExpanded ? showText : hideText;
        preview.hidden = isExpanded;
    });
});

document.querySelectorAll("[data-revision-form]").forEach((form) => {
    const textarea = form.querySelector("textarea");
    const submitButton = form.querySelector('button[type="submit"]');
    const loading = form.querySelector("[data-revision-loading]");
    const errorMessage = form.querySelector("[data-revision-error]");

    if (!textarea || !submitButton || !loading || !errorMessage) {
        return;
    }

    const setLoading = (isLoading) => {
        textarea.disabled = isLoading;
        submitButton.disabled = isLoading;
        loading.hidden = !isLoading;
    };

    const showError = (message) => {
        errorMessage.textContent = message;
        errorMessage.hidden = false;
    };

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        errorMessage.hidden = true;
        errorMessage.textContent = "";

        if (!textarea.value.trim()) {
            showError("Enter the edit you want AI to make.");
            textarea.focus();
            return;
        }

        setLoading(true);

        try {
            const formData = new FormData(form);
            formData.set(textarea.name, textarea.value.trim());
            const response = await fetch(form.action || window.location.href, {
                method: "POST",
                body: formData,
                headers: {
                    "X-Requested-With": "XMLHttpRequest",
                },
            });
            const data = await response.json();

            if (!response.ok) {
                const serverError = data.error || data.errors?.instruction?.[0]?.message;
                throw new Error(serverError || "The revision could not be generated.");
            }

            window.location.href = data.redirect_url || window.location.href;
        } catch (error) {
            showError(error.message);
            setLoading(false);
            textarea.focus();
        }
    });
});
