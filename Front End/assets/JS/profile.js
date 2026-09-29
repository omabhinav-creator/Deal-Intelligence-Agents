document.addEventListener("DOMContentLoaded", async () => {
    const form = document.getElementById("profileForm");
    const actions = document.getElementById("profileActions");
    let user = await DealMindAPI.requireAuth();
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
        document.getElementById("profileStatus").textContent = "";
    };
    render(user);
    document.getElementById("editProfile").addEventListener("click", () => { form.hidden = false; actions.hidden = true; });
    document.getElementById("cancelEdit").addEventListener("click", () => { form.hidden = true; actions.hidden = false; render(user); });
    document.getElementById("logout").addEventListener("click", DealMindAPI.logout);
    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        try {
            const updated = await DealMindAPI.request("/api/auth/profile", { method: "PUT", body: JSON.stringify({ name: document.getElementById("editName").value.trim(), email: document.getElementById("editEmail").value.trim() }) });
            localStorage.setItem("dealMindUser", JSON.stringify(updated));
            form.hidden = true; actions.hidden = false; render(updated);
            document.getElementById("profileStatus").textContent = "Profile saved.";
        } catch (error) { document.getElementById("profileStatus").textContent = error.message; }
    });
});
