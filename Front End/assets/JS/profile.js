const email = localStorage.getItem("dealMindUser") || "";
const storedName = localStorage.getItem("dealMindName") || "";
const inferredName = email
  ? email.split("@")[0].replace(/[._-]/g, " ").split(/\s+/).filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join(" ")
  : "Current user";
const name = storedName || inferredName;

document.querySelectorAll("[data-profile-name]").forEach((element) => {
  element.textContent = name;
});
document.querySelectorAll("[data-profile-email]").forEach((element) => {
  element.textContent = email;
});
document.querySelectorAll("[data-profile-avatar]").forEach((element) => {
  element.textContent = name.charAt(0).toUpperCase() || "U";
});

const dashboardProfile = document.getElementById("dashboardProfileLink");
if (dashboardProfile) {
  dashboardProfile.textContent = (name.match(/\b\w/g) || ["U"])
    .slice(0, 2).join("").toUpperCase();
}
