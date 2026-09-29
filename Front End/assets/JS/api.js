/* Shared authenticated API client for the canonical DealMind FastAPI service. */
(function () {
    const API_BASE_URL = (window.DEALMIND_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
    const TOKEN_KEY = "dealMindAccessToken";
    const USER_KEY = "dealMindUser";
    const loginPage = () => "auth.html";

    function apiError(message, kind, status = null) {
        const error = new Error(message);
        error.kind = kind;
        error.status = status;
        return error;
    }

    function clearSession() {
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(USER_KEY);
        localStorage.removeItem("dealMindAuthenticated");
    }
    function saveSession(session) {
        localStorage.setItem(TOKEN_KEY, session.access_token);
        localStorage.setItem(USER_KEY, JSON.stringify(session.user));
    }
    function renderUser(user) {
        const initial = user.name.trim().charAt(0).toUpperCase() || "?";
        document.querySelectorAll(".user-profile").forEach((profile) => {
            const avatar = profile.querySelector(".avatar");
            const name = profile.querySelector("strong");
            const role = profile.querySelector("span");
            if (avatar) avatar.textContent = initial;
            if (name) name.textContent = user.name;
            if (role) role.textContent = user.role;
        });
        document.querySelectorAll(".profile .avatar").forEach((avatar) => {
            avatar.textContent = initial;
        });
    }
    async function request(path, options = {}) {
        const headers = new Headers(options.headers || {});
        headers.set("Accept", "application/json");
        if (options.body !== undefined && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
        const token = localStorage.getItem(TOKEN_KEY);
        const publicAuthRequest = /^\/api\/auth\/(login|signup)$/.test(path);
        if (!token && !publicAuthRequest) {
            clearSession();
            if (!window.location.pathname.endsWith("/auth.html")) window.location.replace(loginPage());
            throw apiError("Sign in to access DealMind data.", "authentication", 401);
        }
        if (token) headers.set("Authorization", `Bearer ${token}`);
        let response;
        try { response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers }); }
        catch (_) { throw apiError("Unable to reach DealMind at the configured API address. Check that the API is running.", "network"); }
        const body = response.status === 204 ? null : await response.json().catch(() => null);
        if (!response.ok) {
            if (response.status === 401 || response.status === 403) {
                clearSession();
                if (!window.location.pathname.endsWith("/auth.html")) window.location.replace(loginPage());
                throw apiError(body?.detail || "Your session has expired. Please sign in again.", "authentication", response.status);
            }
            const kind = response.status >= 500 ? "backend" : "request";
            const detail = Array.isArray(body?.detail)
                ? body.detail.map((item) => item.msg).filter(Boolean).join(" ")
                : body?.detail;
            const message = response.status >= 500
                ? detail || "Deal Intelligence is temporarily unavailable. Please try again shortly."
                : response.status === 404
                    ? "The requested DealMind record could not be found."
                : response.status === 400
                    ? "The selected deal or request is invalid."
                : response.status === 409
                    ? detail || "An account with that email already exists."
                : response.status === 422
                        ? detail || "Please check the submitted information and try again."
                        : detail || "The request could not be completed.";
            const error = apiError(message, kind, response.status);
            error.endpoint = path;
            error.providerMessage = body?.provider_message || null;
            error.retryAfter = body?.retry_after || response.headers.get("Retry-After");
            throw error;
        }
        return body;
    }
    async function requireAuth() {
        if (!localStorage.getItem(TOKEN_KEY)) {
            clearSession();
            window.location.replace(loginPage());
            return null;
        }
        try {
            const user = await request("/api/auth/me");
            localStorage.setItem(USER_KEY, JSON.stringify(user));
            renderUser(user);
            return user;
        } catch (_) { return null; }
    }
    async function logout() {
        try { await request("/api/auth/logout", { method: "POST" }); } catch (_) { /* Clear stale local state. */ }
        clearSession();
        window.location.replace(loginPage());
    }
    function wireProfileNavigation() {
        document.querySelectorAll(".profile, .user-profile, .profile-section").forEach((element) => {
            element.tabIndex = 0;
            element.setAttribute("role", "link");
            element.addEventListener("click", (event) => {
                if (!event.target.closest("button, a, input, select")) window.location.href = "profile.html";
            });
            element.addEventListener("keydown", (event) => {
                if (event.key === "Enter" || event.key === " ") window.location.href = "profile.html";
            });
        });
    }
    function setSelectedDeal(deal) {
        if (deal) localStorage.setItem("dealMindSelectedDeal", JSON.stringify(deal));
        else localStorage.removeItem("dealMindSelectedDeal");
    }
    function getSelectedDeal() {
        try { return JSON.parse(localStorage.getItem("dealMindSelectedDeal") || "null"); }
        catch (_) { return null; }
    }
    window.DealMindAPI = { request, saveSession, clearSession, requireAuth, logout, wireProfileNavigation, setSelectedDeal, getSelectedDeal, baseUrl: API_BASE_URL };
    document.addEventListener("DOMContentLoaded", () => {
        if (!window.location.pathname.endsWith("/auth.html")) { wireProfileNavigation(); requireAuth(); }
    });
}());
