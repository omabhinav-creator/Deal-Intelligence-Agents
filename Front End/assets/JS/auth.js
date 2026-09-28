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

        const email =
            document.getElementById("signinEmail").value.trim();

        const password =
            document.getElementById("signinPassword").value.trim();

        if (!email || !password) {
            alert("Please fill in all fields.");
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

        const email =
            document.getElementById("signupEmail").value.trim();

        const password =
            document.getElementById("signupPassword").value.trim();

        const terms =
            document.getElementById("terms").checked;


        if (!name || !email || !password) {

            alert("Please fill in all fields.");
            return;

        }


        if (password.length < 8) {

            alert("Password must contain at least 8 characters.");
            return;

        }


        if (!terms) {

            alert("Please accept the Terms of Service.");
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

        alert(
            "Google authentication will be connected when the backend is added."
        );

    });


    googleSignUp.addEventListener("click", () => {

        alert(
            "Google authentication will be connected when the backend is added."
        );

    });


    /* ================================
       FORGOT PASSWORD
    ================================= */

    forgotPassword.addEventListener("click", (event) => {

        event.preventDefault();

        const email =
            document.getElementById("signinEmail").value.trim();

        if (!email) {

            alert(
                "Enter your email address first to reset your password."
            );

            document.getElementById("signinEmail").focus();

            return;

        }

        alert(
            `Password reset instructions would be sent to ${email}.`
        );

    });


});