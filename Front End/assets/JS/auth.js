/* ================================
   DEALMIND AUTH JAVASCRIPT
================================ */

document.addEventListener("DOMContentLoaded", () => {

    if (localStorage.getItem("dealMindAuthenticated") === "true") {
        window.location.href = "dashboard.html";
        return;
    }

    const signinForm = document.getElementById("signinForm");
    const signupForm = document.getElementById("signupForm");

    const showSignup = document.getElementById("showSignup");
    const showSignin = document.getElementById("showSignin");

    const signInFormElement = document.getElementById("signInForm");
    const signUpFormElement = document.getElementById("signUpForm");

    const themeToggle = document.getElementById("themeToggle");

    const googleSignIn = document.getElementById("googleSignIn");
    const googleSignUp = document.getElementById("googleSignUp");

    const forgotPassword = document.getElementById("forgotPassword");


    /* ================================
       SWITCH SIGN IN / SIGN UP
    ================================= */

    showSignup.addEventListener("click", () => {

        signinForm.classList.remove("active");
        signupForm.classList.add("active");

    });


    showSignin.addEventListener("click", () => {

        signupForm.classList.remove("active");
        signinForm.classList.add("active");

    });


    /* ================================
       PASSWORD VISIBILITY
    ================================= */

    const passwordToggles =
        document.querySelectorAll(".password-toggle");

    passwordToggles.forEach(toggle => {

        toggle.addEventListener("click", () => {

            const targetId = toggle.dataset.target;
            const passwordInput =
                document.getElementById(targetId);

            if (passwordInput.type === "password") {

                passwordInput.type = "text";
                toggle.textContent = "Hide";

            } else {

                passwordInput.type = "password";
                toggle.textContent = "Show";

            }

        });

    });


    /* ================================
       SIGN IN
    ================================= */

    signInFormElement.addEventListener("submit", (event) => {

        event.preventDefault();

        const emailInput = document.getElementById("signinEmail");
        const email = emailInput.value.trim();

        const password =
            document.getElementById("signinPassword").value.trim();

        if (!email || !password) {
            window.DealMindUI.showToast("Please fill in all fields.", "error");
            return;
        }

        if (emailInput.validity.typeMismatch) {
            window.DealMindUI.showToast("Enter a valid email address.", "error");
            emailInput.focus();
            return;
        }

        localStorage.setItem("dealMindAuthenticated", "true");
        localStorage.setItem("dealMindUser", email);
        window.location.href = "dashboard.html";

    });


    /* ================================
       SIGN UP
    ================================= */

    signUpFormElement.addEventListener("submit", (event) => {

        event.preventDefault();

        const name =
            document.getElementById("signupName").value.trim();

        const emailInput = document.getElementById("signupEmail");
        const email = emailInput.value.trim();

        const password =
            document.getElementById("signupPassword").value.trim();

        const terms =
            document.getElementById("terms").checked;


        if (!name || !email || !password) {

            window.DealMindUI.showToast("Please fill in all fields.", "error");
            return;

        }

        if (emailInput.validity.typeMismatch) {
            window.DealMindUI.showToast("Enter a valid email address.", "error");
            emailInput.focus();
            return;
        }


        if (password.length < 8) {

            window.DealMindUI.showToast("Password must contain at least 8 characters.", "error");
            return;

        }


        if (!terms) {

            window.DealMindUI.showToast("Please accept the Terms of Service.", "error");
            return;

        }


        localStorage.setItem("dealMindAuthenticated", "true");
        localStorage.setItem("dealMindUser", email);
        window.location.href = "dashboard.html";

    });


    /* ================================
       GOOGLE BUTTONS
    ================================= */

    googleSignIn.addEventListener("click", () => {

        window.DealMindUI.showToast(
            "Google authentication will be connected when the backend is added.",
            "info",
        );

    });


    googleSignUp.addEventListener("click", () => {

        window.DealMindUI.showToast(
            "Google authentication will be connected when the backend is added.",
            "info",
        );

    });


    /* ================================
       FORGOT PASSWORD
    ================================= */

    forgotPassword.addEventListener("click", (event) => {

        event.preventDefault();

        const emailInput = document.getElementById("signinEmail");
        const email = emailInput.value.trim();

        if (!email) {

            window.DealMindUI.showToast(
                "Enter your email address first to reset your password.",
                "error",
            );

            document.getElementById("signinEmail").focus();

            return;

        }

        if (emailInput.validity.typeMismatch) {
            window.DealMindUI.showToast("Enter a valid email address.", "error");
            emailInput.focus();
            return;
        }

        window.DealMindUI.showToast(
            `Password reset instructions would be sent to ${email}.`,
            "info",
        );

    });


});
