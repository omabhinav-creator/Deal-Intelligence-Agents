document.addEventListener("DOMContentLoaded", () => {
    const signinForm = document.getElementById("signinForm");
    const signupForm = document.getElementById("signupForm");
    const signInFormElement = document.getElementById("signInForm");
    const signUpFormElement = document.getElementById("signUpForm");

    function showError(form, message) {
        let error = form.querySelector(".auth-error");
        if (!error) {
            error = document.createElement("p");
            error.className = "auth-error";
            error.setAttribute("role", "alert");
            form.querySelector("form").prepend(error);
        }
        error.textContent = message;
    }
    function setBusy(form, busy) {
        const button = form.querySelector("button[type='submit']");
        button.disabled = busy;
        button.dataset.label ||= button.textContent;
        button.textContent = busy ? "Please wait…" : button.dataset.label;
    }
    document.getElementById("showSignup").addEventListener("click", () => {
        signinForm.classList.remove("active"); signupForm.classList.add("active");
    });
    document.getElementById("showSignin").addEventListener("click", () => {
        signupForm.classList.remove("active"); signinForm.classList.add("active");
    });
    document.querySelectorAll(".password-toggle").forEach((toggle) => toggle.addEventListener("click", () => {
        const input = document.getElementById(toggle.dataset.target);
        input.type = input.type === "password" ? "text" : "password";
        toggle.textContent = input.type === "password" ? "Show" : "Hide";
    }));
    signInFormElement.addEventListener("submit", async (event) => {
        event.preventDefault(); setBusy(signinForm, true);
        try {
            const session = await DealMindAPI.request("/api/auth/login", { method: "POST", body: JSON.stringify({
                email: document.getElementById("signinEmail").value.trim(),
                password: document.getElementById("signinPassword").value,
            }) });
            DealMindAPI.saveSession(session);
            window.location.assign("dashboard.html");
        } catch (error) { showError(signinForm, error.message); }
        finally { setBusy(signinForm, false); }
    });
    signUpFormElement.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (!document.getElementById("terms").checked) { showError(signupForm, "Please accept the Terms of Service."); return; }
        setBusy(signupForm, true);
        try {
            const session = await DealMindAPI.request("/api/auth/signup", { method: "POST", body: JSON.stringify({
                name: document.getElementById("signupName").value.trim(),
                email: document.getElementById("signupEmail").value.trim(),
                password: document.getElementById("signupPassword").value,
            }) });
            DealMindAPI.saveSession(session);
            window.location.assign("dashboard.html");
        } catch (error) { showError(signupForm, error.message); }
        finally { setBusy(signupForm, false); }
    });
    ["googleSignIn", "googleSignUp"].forEach((id) => document.getElementById(id).addEventListener("click", () => {
        showError(id === "googleSignIn" ? signinForm : signupForm, "Google sign-in is not available yet.");
    }));
    document.getElementById("forgotPassword").addEventListener("click", (event) => {
        event.preventDefault(); showError(signinForm, "Password reset is not available yet.");
    });
});
