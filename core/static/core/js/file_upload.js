// Maintain a multi-file queue across repeated picker selections.

document.querySelectorAll(".ws-upload-form").forEach((form) => {
    const input = form.querySelector('input[type="file"][multiple]');
    const queue = form.querySelector("[data-file-queue]");
    const fileList = form.querySelector("[data-file-list]");
    const clearButton = form.querySelector("[data-clear-files]");

    if (!input || !queue || !fileList || !clearButton || !window.DataTransfer) {
        return;
    }

    const selectedFiles = new DataTransfer();

    const fileKey = (file) => `${file.name}:${file.size}:${file.lastModified}`;

    const renderQueue = () => {
        fileList.replaceChildren();

        Array.from(selectedFiles.files).forEach((file) => {
            const item = document.createElement("li");
            item.className = "ws-file-queue-item";

            const name = document.createElement("span");
            name.className = "ws-file-queue-name";
            name.textContent = file.name;

            const size = document.createElement("span");
            size.className = "ws-file-queue-size";
            size.textContent = `${Math.max(1, Math.ceil(file.size / 1024))} KB`;

            item.append(name, size);
            fileList.append(item);
        });

        queue.hidden = selectedFiles.files.length === 0;
    };

    input.addEventListener("change", () => {
        const existingKeys = new Set(
            Array.from(selectedFiles.files).map(fileKey),
        );

        Array.from(input.files).forEach((file) => {
            if (!existingKeys.has(fileKey(file))) {
                selectedFiles.items.add(file);
                existingKeys.add(fileKey(file));
            }
        });

        input.files = selectedFiles.files;
        renderQueue();
    });

    clearButton.addEventListener("click", () => {
        selectedFiles.items.clear();
        input.files = selectedFiles.files;
        renderQueue();
    });
});
