// Submit AI planning messages without leaving the workspace.

document.querySelectorAll("[data-ai-chat-form]").forEach((form) => {
    const conversation = document.querySelector("[data-ai-conversation]");
    const status = document.querySelector("[data-ai-status]");
    const mappingLink = document.querySelector("[data-ai-mapping-link]");
    const mappingDisabled = document.querySelector("[data-ai-mapping-disabled]");
    const textarea = form.querySelector("textarea");
    const submitButton = form.querySelector('button[type="submit"]');

    if (!conversation || !textarea || !submitButton) {
        return;
    }

    const appendMessage = (role, content, extraClass = "") => {
        const message = document.createElement("div");
        message.className = `ai-message ai-message--${role} ${extraClass}`.trim();

        const paragraph = document.createElement("p");
        paragraph.textContent = content;
        message.append(paragraph);
        conversation.append(message);
        conversation.scrollTop = conversation.scrollHeight;
        return message;
    };

    form.addEventListener("submit", async (event) => {
        event.preventDefault();

        const content = textarea.value.trim();
        if (!content) {
            textarea.focus();
            return;
        }

        const formData = new FormData(form);
        formData.set(textarea.name, content);

        appendMessage("user", content);
        textarea.value = "";
        textarea.disabled = true;
        submitButton.disabled = true;
        const typingMessage = appendMessage("assistant", "...", "ai-message--typing");

        try {
            const response = await fetch(form.action || window.location.href, {
                method: "POST",
                body: formData,
                headers: {
                    "X-Requested-With": "XMLHttpRequest",
                },
            });
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || "The AI response could not be generated.");
            }

            typingMessage.querySelector("p").textContent = data.assistant_message.content;
            typingMessage.classList.remove("ai-message--typing");
            if (status && data.status) {
                status.textContent = data.status;
            }
            if (data.mapping_ready && mappingLink && data.mapping_url) {
                mappingLink.href = data.mapping_url;
                mappingLink.hidden = false;
                if (mappingDisabled) {
                    mappingDisabled.hidden = true;
                }
            }
        } catch (error) {
            typingMessage.querySelector("p").textContent = error.message;
            typingMessage.classList.remove("ai-message--typing");
            typingMessage.classList.add("ai-message--error");
        } finally {
            textarea.disabled = false;
            submitButton.disabled = false;
            textarea.focus();
        }
    });
});
