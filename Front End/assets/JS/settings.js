/* ==========================================
   DEALMIND SETTINGS JAVASCRIPT
========================================== */

document.addEventListener("DOMContentLoaded", async () => {

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


    const user = await DealMindAPI.requireAuth();
    if (!user) return;

    const profileEmail =
        document.getElementById("profileEmail");

    const profileName =
        document.getElementById("profileName");

    const profileAvatar =
        document.getElementById("profileAvatar");


    profileName.textContent = user.name;
    profileEmail.textContent = user.email;
    profileAvatar.textContent = user.name.charAt(0).toUpperCase();


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

    editProfileButton.addEventListener("click", () => {
        window.location.assign("profile.html");
    });


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

    logoutButton.addEventListener("click", DealMindAPI.logout);
    signOutButton.addEventListener("click", DealMindAPI.logout);

});