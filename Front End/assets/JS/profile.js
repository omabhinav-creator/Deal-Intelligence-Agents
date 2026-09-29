/* Shared account display plus the editable backend-backed profile page. */
function readStoredUser() {
    try {
        const value = JSON.parse(localStorage.getItem("dealMindUser") || "null");
        if (value && typeof value === "object") return value;
    } catch (_) {
        // Older demo sessions stored the email as a plain string.
    }
    return { email: localStorage.getItem("dealMindUser") || "", name: "" };
}

const storedUser = readStoredUser();
const email = storedUser.email || "";
const inferredName = email
    ? email.split("@")[0].replace(/[._-]/g, " ").split(/\s+/).filter(Boolean)
        .map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join(" ")
    : "Current user";
const displayedName = localStorage.getItem("dealMindName") || storedUser.name || inferredName;

document.querySelectorAll("[data-profile-name]").forEach((element) => {
    element.textContent = displayedName;
});
document.querySelectorAll("[data-profile-email]").forEach((element) => {
    element.textContent = email;
});
document.querySelectorAll("[data-profile-avatar]").forEach((element) => {
    element.textContent = displayedName.charAt(0).toUpperCase() || "U";
});

const dashboardProfile = document.getElementById("dashboardProfileLink");
if (dashboardProfile) {
    dashboardProfile.textContent = (displayedName.match(/\b\w/g) || ["U"])
        .slice(0, 2).join("").toUpperCase();
}

document.addEventListener("DOMContentLoaded", async () => {
    const form = document.getElementById("profileForm");
    if (!form || !window.DealMindAPI) return;

    const status = document.getElementById("profileStatus");
    const actions = document.getElementById("profileActions");
    let user = await window.DealMindAPI.requireAuth();
    if (!user) return;

    const render = (current) => {
        user = current;
        document.getElementById("profileName").textContent = user.name;
        document.getElementById("profileEmail").textContent = user.email;
        document.getElementById("profileRole").textContent = user.role;
        document.getElementById("profileCreated").textContent = new Date(user.created_at).toLocaleDateString();
        document.getElementById("profileAvatar").textContent = user.name.charAt(0).toUpperCase();
        document.getElementById("editName").value = user.name;
        document.getElementById("editEmail").value = user.email;
        status.textContent = "";
    };

    render(user);
    document.getElementById("editProfile").addEventListener("click", () => {
        form.hidden = false;
        actions.hidden = true;
    });
    document.getElementById("cancelEdit").addEventListener("click", () => {
        form.hidden = true;
        actions.hidden = false;
        render(user);
    });
    document.getElementById("logout").addEventListener("click", window.DealMindAPI.logout);
    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        status.textContent = "Saving profile…";
        try {
            const updated = await window.DealMindAPI.request("/api/auth/profile", {
                method: "PUT",
                body: JSON.stringify({
                    name: document.getElementById("editName").value.trim(),
                    email: document.getElementById("editEmail").value.trim(),
                }),
            });
            localStorage.setItem("dealMindUser", JSON.stringify(updated));
            localStorage.removeItem("dealMindName");
            form.hidden = true;
            actions.hidden = false;
            render(updated);
            status.textContent = "Profile saved.";
        } catch (error) {
            status.textContent = error.message;
        }
    });
});
