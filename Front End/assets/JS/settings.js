/* ==========================================
   DEALMIND SETTINGS JAVASCRIPT
========================================== */

document.addEventListener("DOMContentLoaded", () => {

    const themeToggle =
        document.getElementById("themeToggle");

    const appearanceSelect =
        document.getElementById("appearanceSelect");

    const logoutButton =
        document.getElementById("logoutButton");

    const signOutButton =
        document.getElementById("signOutButton");

    const editProfileButton =
        document.getElementById("editProfileButton");

    const changePasswordButton =
        document.getElementById("changePasswordButton");

    const saveButton =
        document.getElementById("saveButton");

    const resetButton =
        document.getElementById("resetButton");


    /* ==========================================
       AUTH CHECK
    ========================================== */

    const isAuthenticated =
        localStorage.getItem("dealMindAuthenticated");

    if (isAuthenticated !== "true") {
        window.location.href = "auth.html";
        return;
    }


    /* ==========================================
       USER INFORMATION
    ========================================== */

    const storedEmail =
        localStorage.getItem("dealMindUser");

    const profileEmail =
        document.getElementById("profileEmail");

    const profileName =
        document.getElementById("profileName");

    const profileAvatar =
        document.getElementById("profileAvatar");


    if (storedEmail) {

        profileEmail.textContent =
            storedEmail;

        /*
            Generate a simple display name
            from the email address.
        */

        const emailName =
            storedEmail
                .split("@")[0]
                .replace(/[._-]/g, " ");

        const formattedName =
            emailName
                .split(" ")
                .filter(Boolean)
                .map(word =>
                    word.charAt(0).toUpperCase() +
                    word.slice(1)
                )
                .join(" ");

        if (formattedName) {

            profileName.textContent =
                formattedName;

            profileAvatar.textContent =
                formattedName
                    .charAt(0)
                    .toUpperCase();

        }

    }


    /* ==========================================
       SAVE SETTINGS
    ========================================== */

    saveButton.addEventListener("click", () => {

        const settings = {

            aiInsights:
                document.getElementById(
                    "aiInsightsToggle"
                ).checked,

            meetingReminders:
                document.getElementById(
                    "meetingReminderToggle"
                ).checked,

            learningSuggestions:
                document.getElementById(
                    "learningToggle"
                ).checked,

            riskAlerts:
                document.getElementById(
                    "riskAlertsToggle"
                ).checked,

            aiRecommendations:
                document.getElementById(
                    "recommendationToggle"
                ).checked

        };


        localStorage.setItem(
            "dealMindSettings",
            JSON.stringify(settings)
        );


        saveButton.textContent =
            "Saved ✓";


        setTimeout(() => {

            saveButton.textContent =
                "Save Changes";

        }, 1800);

    });


    /* ==========================================
       LOAD SETTINGS
    ========================================== */

    const savedSettings =
        localStorage.getItem("dealMindSettings");


    if (savedSettings) {

        const settings =
            JSON.parse(savedSettings);


        document.getElementById(
            "aiInsightsToggle"
        ).checked =
            settings.aiInsights;


        document.getElementById(
            "meetingReminderToggle"
        ).checked =
            settings.meetingReminders;


        document.getElementById(
            "learningToggle"
        ).checked =
            settings.learningSuggestions;


        document.getElementById(
            "riskAlertsToggle"
        ).checked =
            settings.riskAlerts;


        document.getElementById(
            "recommendationToggle"
        ).checked =
            settings.aiRecommendations;

    }


    /* ==========================================
       RESET
    ========================================== */

    resetButton.addEventListener("click", () => {

        document.getElementById(
            "aiInsightsToggle"
        ).checked = true;

        document.getElementById(
            "meetingReminderToggle"
        ).checked = true;

        document.getElementById(
            "learningToggle"
        ).checked = true;

        document.getElementById(
            "riskAlertsToggle"
        ).checked = true;

        document.getElementById(
            "recommendationToggle"
        ).checked = true;

        appearanceSelect.value =
            document.body.classList.contains("dark")
                ? "dark"
                : "light";

        localStorage.removeItem(
            "dealMindSettings"
        );

    });


    /* ==========================================
       EDIT PROFILE
    ========================================== */

    editProfileButton.addEventListener(
        "click",
        () => {

            const newName =
                prompt(
                    "Enter your name:",
                    profileName.textContent
                );

            if (!newName || !newName.trim()) {
                return;
            }

            const cleanName =
                newName.trim();

            profileName.textContent =
                cleanName;

            profileAvatar.textContent =
                cleanName
                    .charAt(0)
                    .toUpperCase();

            localStorage.setItem(
                "dealMindName",
                cleanName
            );

        }
    );


    /* ==========================================
       LOAD CUSTOM NAME
    ========================================== */

    const savedName =
        localStorage.getItem("dealMindName");

    if (savedName) {

        profileName.textContent =
            savedName;

        profileAvatar.textContent =
            savedName
                .charAt(0)
                .toUpperCase();

    }


    /* ==========================================
       CHANGE PASSWORD
    ========================================== */

    changePasswordButton.addEventListener(
        "click",
        () => {

            alert(
                "Password change functionality will be connected to the backend."
            );

        }
    );


    /* ==========================================
       LOGOUT
    ========================================== */

    function logout() {

        localStorage.removeItem(
            "dealMindAuthenticated"
        );

        localStorage.removeItem(
            "dealMindUser"
        );

        window.location.href =
            "auth.html";

    }


    logoutButton.addEventListener(
        "click",
        logout
    );

    signOutButton.addEventListener(
        "click",
        logout
    );

});