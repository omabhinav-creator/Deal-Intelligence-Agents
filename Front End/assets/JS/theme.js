(() => {
    const themeToggle = document.getElementById("themeToggle");
    const themeText = document.getElementById("themeText");
    const appearanceSelect = document.getElementById("appearanceSelect");

    function applyTheme(theme) {
        const isDark = theme === "dark";

        document.body.classList.toggle("dark", isDark);
        localStorage.setItem("dealMindTheme", isDark ? "dark" : "light");

        if (themeText) {
            themeText.textContent = isDark ? "Light mode" : "Dark mode";
        }

        if (appearanceSelect) {
            appearanceSelect.value = isDark ? "dark" : "light";
        }

        const icon = themeToggle?.querySelector("i");
        if (icon) {
            icon.classList.toggle("fa-sun", isDark);
            icon.classList.toggle("fa-moon", !isDark);
        } else if (themeToggle && !themeText) {
            themeToggle.textContent = isDark ? "☀" : "☾";
        }
    }

    applyTheme(localStorage.getItem("dealMindTheme") === "dark" ? "dark" : "light");

    themeToggle?.addEventListener("click", () => {
        applyTheme(document.body.classList.contains("dark") ? "light" : "dark");
    });

    appearanceSelect?.addEventListener("change", () => {
        applyTheme(appearanceSelect.value);
    });
})();