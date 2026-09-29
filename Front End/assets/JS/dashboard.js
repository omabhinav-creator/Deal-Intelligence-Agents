/* =========================================
   DEALMIND — DASHBOARD JAVASCRIPT
========================================= */

if (localStorage.getItem("dealMindAuthenticated") !== "true") {
     window.location.href = "auth.html";
} else {

const profile = document.querySelector(".profile");
const logoutButton = document.createElement("button");

logoutButton.type = "button";
logoutButton.className = "notification";
logoutButton.setAttribute("aria-label", "Log out");
logoutButton.title = "Log out";
logoutButton.textContent = "↪";
logoutButton.addEventListener("click", logout);
profile.appendChild(logoutButton);


function logout() {
    localStorage.removeItem("dealMindAuthenticated");
    localStorage.removeItem("dealMindUser");
    window.location.href = "auth.html";
}


/* =========================================
   SIDEBAR NAVIGATION
========================================= */

const navItems =
    document.querySelectorAll(".nav-item");

const pageRoutes = {
    dashboard: "dashboard.html",
    deals: "deals.html",
    memory: "dealmemory.html",
    copilot: "aicopilot.html",
    learning: "learning.html",
    settings: "settings.html"
};

document.querySelectorAll("[data-page]").forEach((item) => {
    item.addEventListener("click", () => {
        const destination = pageRoutes[item.dataset.page];

        if (destination) {
            window.location.href = destination;
        }
    });
});


navItems.forEach((item) => {

    item.addEventListener(
        "click",
        () => {

            navItems.forEach((nav) => {

                nav.classList.remove("active");

            });

            item.classList.add("active");

        }
    );

});


}
