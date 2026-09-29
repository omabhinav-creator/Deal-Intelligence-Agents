(() => {
  let activeDialog = null;
  let toastTimer = null;

  const toastRegion = document.createElement("div");
  toastRegion.className = "dm-toast-region";
  toastRegion.setAttribute("aria-live", "polite");
  toastRegion.setAttribute("aria-relevant", "additions text");
  document.body.appendChild(toastRegion);

  function closeActiveDialog(restoreFocus = true) {
    if (!activeDialog) return;
    const current = activeDialog;
    activeDialog = null;
    current.overlay.remove();
    if (restoreFocus && current.previousFocus?.isConnected) {
      current.previousFocus.focus();
    }
  }

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeActiveDialog();
  });

  function showDialog({
    title,
    message,
    note,
    noteType = "demo",
    size = "standard",
    sections = [],
    contentBuilder,
    actions = [],
    closeOnOutside = true,
  }) {
    closeActiveDialog(false);

    const previousFocus = document.activeElement;
    const overlay = document.createElement("div");
    overlay.className = "dm-dialog-overlay";
    overlay.addEventListener("click", (event) => {
      if (closeOnOutside && event.target === overlay) closeActiveDialog();
    });

    const dialog = document.createElement("section");
    dialog.className = `dm-dialog dm-dialog--${size}`;
    dialog.setAttribute("role", "dialog");
    dialog.setAttribute("aria-modal", "true");
    dialog.setAttribute("aria-labelledby", "dmDialogTitle");

    const header = document.createElement("header");
    header.className = "dm-dialog__header";
    const heading = document.createElement("h2");
    heading.id = "dmDialogTitle";
    heading.textContent = title;
    const closeButton = document.createElement("button");
    closeButton.type = "button";
    closeButton.className = "dm-dialog__close";
    closeButton.setAttribute("aria-label", `Close ${title}`);
    closeButton.textContent = "×";
    header.append(heading, closeButton);
    dialog.appendChild(header);

    const body = document.createElement("div");
    body.className = "dm-dialog__body";
    if (message) {
      const messageElement = document.createElement("p");
      messageElement.className = "dm-dialog__message";
      messageElement.textContent = message;
      body.appendChild(messageElement);
    }
    sections.forEach((section) => {
      const sectionElement = document.createElement("section");
      sectionElement.className = "dm-dialog__section";
      if (section.title) {
        const sectionTitle = document.createElement("h3");
        sectionTitle.textContent = section.title;
        sectionElement.appendChild(sectionTitle);
      }
      if (section.text) {
        const text = document.createElement("p");
        text.textContent = section.text;
        sectionElement.appendChild(text);
      }
      if (section.items?.length) {
        const list = document.createElement("ul");
        section.items.forEach((item) => {
          const listItem = document.createElement("li");
          listItem.textContent = item;
          list.appendChild(listItem);
        });
        sectionElement.appendChild(list);
      }
      body.appendChild(sectionElement);
    });
    if (contentBuilder) contentBuilder(body, () => closeActiveDialog());
    if (note) {
      const noteElement = document.createElement("p");
      noteElement.className = `dm-dialog__note dm-dialog__note--${noteType}`;
      noteElement.textContent = note;
      body.appendChild(noteElement);
    }
    dialog.appendChild(body);

    if (actions.length) {
      const footer = document.createElement("footer");
      footer.className = "dm-dialog__actions";
      actions.forEach((action) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = `dm-dialog__action ${action.variant || ""}`.trim();
        button.textContent = action.label;
        button.addEventListener("click", () => action.onClick?.(() => closeActiveDialog()));
        footer.appendChild(button);
      });
      dialog.appendChild(footer);
    }

    overlay.appendChild(dialog);
    document.body.appendChild(overlay);
    activeDialog = { overlay, previousFocus };
    closeButton.addEventListener("click", () => closeActiveDialog());
    closeButton.focus();
    return { dialog, body, close: () => closeActiveDialog() };
  }

  function showSelector({ title, message, options, selectedValue, onSelect }) {
    return showDialog({
      title,
      message,
      contentBuilder(body, close) {
        const list = document.createElement("div");
        list.className = "dm-selector-list";
        options.forEach((option) => {
          const button = document.createElement("button");
          button.type = "button";
          button.className = "dm-selector-option";
          if (option.value === selectedValue) button.setAttribute("aria-current", "true");
          const name = document.createElement("span");
          name.className = "dm-selector-option__name";
          name.textContent = option.label;
          button.appendChild(name);
          if (option.description) {
            const description = document.createElement("small");
            description.textContent = option.description;
            button.appendChild(description);
          }
          button.addEventListener("click", () => {
            close();
            onSelect(option.value);
          });
          list.appendChild(button);
        });
        body.appendChild(list);
      },
    });
  }

  function showInputDialog({ title, label, value = "", submitLabel = "Save", onSubmit }) {
    return showDialog({
      title,
      contentBuilder(body, close) {
        const form = document.createElement("form");
        form.className = "dm-input-form";
        const fieldLabel = document.createElement("label");
        fieldLabel.textContent = label;
        const input = document.createElement("input");
        input.type = "text";
        input.value = value;
        fieldLabel.appendChild(input);
        form.appendChild(fieldLabel);
        const error = document.createElement("p");
        error.className = "dm-input-form__error";
        error.setAttribute("role", "alert");
        error.hidden = true;
        error.textContent = "Enter a value before saving.";
        form.appendChild(error);
        input.addEventListener("input", () => { error.hidden = true; });
        const actions = document.createElement("div");
        actions.className = "dm-dialog__actions";
        const cancel = document.createElement("button");
        cancel.type = "button";
        cancel.className = "dm-dialog__action";
        cancel.textContent = "Cancel";
        cancel.addEventListener("click", close);
        const save = document.createElement("button");
        save.type = "submit";
        save.className = "dm-dialog__action dm-dialog__action--primary";
        save.textContent = submitLabel;
        actions.append(cancel, save);
        form.appendChild(actions);
        form.addEventListener("submit", (event) => {
          event.preventDefault();
          const cleanValue = input.value.trim();
          if (!cleanValue) {
            error.hidden = false;
            input.focus();
            return;
          }
          close();
          onSubmit(cleanValue);
        });
        body.appendChild(form);
        input.focus();
        input.select();
      },
    });
  }

  function showToast(message, type = "info") {
    window.clearTimeout(toastTimer);
    toastRegion.replaceChildren();
    const toast = document.createElement("div");
    toast.className = `dm-toast dm-toast--${type}`;
    toast.setAttribute("role", type === "error" ? "alert" : "status");
    const text = document.createElement("p");
    text.textContent = message;
    const close = document.createElement("button");
    close.type = "button";
    close.setAttribute("aria-label", "Dismiss notification");
    close.textContent = "×";
    close.addEventListener("click", () => toast.remove());
    toast.append(text, close);
    toastRegion.appendChild(toast);
    toastTimer = window.setTimeout(() => toast.remove(), 8000);
    return toast;
  }

  let openNotificationPanel = null;
  let openNotificationTrigger = null;

  function closeNotifications() {
    if (openNotificationPanel) openNotificationPanel.remove();
    openNotificationPanel = null;
    if (openNotificationTrigger) {
      openNotificationTrigger.setAttribute("aria-expanded", "false");
    }
    openNotificationTrigger = null;
  }

  document.querySelectorAll("[data-notifications-trigger]").forEach((trigger) => {
    trigger.setAttribute("aria-haspopup", "true");
    trigger.addEventListener("click", () => {
      if (openNotificationTrigger === trigger) {
        closeNotifications();
        return;
      }
      closeNotifications();

      const host = trigger.closest(".profile, .topbar-actions") || trigger.parentElement;
      if (!host) return;
      host.classList.add("dm-notifications-host");

      const panel = document.createElement("section");
      panel.className = "dm-notifications-panel";
      panel.setAttribute("role", "status");
      panel.setAttribute("aria-label", "Notifications");
      const heading = document.createElement("h2");
      heading.textContent = "Notifications";
      const message = document.createElement("p");
      message.textContent = "No new notifications.";
      const dismiss = document.createElement("button");
      dismiss.type = "button";
      dismiss.className = "dm-notifications-panel__close";
      dismiss.setAttribute("aria-label", "Close notifications");
      dismiss.textContent = "×";
      dismiss.addEventListener("click", closeNotifications);
      panel.append(heading, message, dismiss);
      host.appendChild(panel);
      trigger.setAttribute("aria-expanded", "true");
      openNotificationPanel = panel;
      openNotificationTrigger = trigger;
    });
  });

  document.addEventListener("click", (event) => {
    if (!openNotificationPanel) return;
    if (openNotificationPanel.contains(event.target) || openNotificationTrigger?.contains(event.target)) return;
    closeNotifications();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeNotifications();
  });

  window.DealMindUI = { showDialog, showSelector, showInputDialog, showToast };
})();
