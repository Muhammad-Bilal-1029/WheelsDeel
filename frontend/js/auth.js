// Backend aur frontend aik hi server se serve hotay hain, is liye relative "/api" use hota hai.
// Fallback: file:// ya VS Code Live Server (port 5500) se kholo to local backend use hoga
// (us surat mai backend ki .env mai CORS_ORIGINS=http://127.0.0.1:5500 jaisa set karna zaroori hai).
const API_BASE_URL = (window.location.protocol === "file:" || window.location.port === "5500" || window.location.port === "5501")
    ? "http://127.0.0.1:8000/api"
    : "/api";

// POST requests par server yeh header check karta hai (CSRF se bachao)
const CSRF_HEADERS = { "X-Requested-With": "WheelDeal" };

// Login ab HttpOnly cookie se hota hai. Purane version ka token localStorage mai reh gaya ho to hata do.
try {
    localStorage.removeItem("token");
    localStorage.removeItem("username");
} catch (error) { /* storage blocked ho to koi masla nahi */ }

function extractErrorMessage(data, fallback) {
    if (data && typeof data.detail === "string") return data.detail;
    if (data && Array.isArray(data.detail) && data.detail.length > 0) {
        return data.detail
            .map((item) => {
                const field = Array.isArray(item.loc) ? item.loc[item.loc.length - 1] : "";
                const message = String(item.msg || "").replace(/^Value error, /, "");
                return field ? `${field}: ${message}` : message;
            })
            .join(" | ");
    }
    return fallback;
}

// Pehle se logged in user ko login/signup page ki zaroorat nahi: seedha Home par bhej do
if (document.getElementById("loginForm") || document.getElementById("signupForm")) {
    fetch(`${API_BASE_URL}/me`, { credentials: "include", cache: "no-store" })
        .then((response) => { if (response.ok) window.location.replace("index.html"); })
        .catch(() => { /* server band ho to login page dikhta rahe */ });
}

async function resendVerification(email) {
    const response = await fetch(`${API_BASE_URL}/resend-verification`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json", ...CSRF_HEADERS },
        body: JSON.stringify({ email })
    });
    const data = await response.json().catch(() => ({}));
    alert(response.ok ? data.msg : extractErrorMessage(data, "Could not resend the email."));
}

const loginForm = document.getElementById("loginForm");
if (loginForm) {
    loginForm.addEventListener("submit", async (event) => {
        event.preventDefault();

        const username_or_email = document.getElementById("username_or_email").value.trim();
        const password = document.getElementById("password").value;
        const errorMsg = document.getElementById("error-msg");
        errorMsg.textContent = "";
        errorMsg.style.display = "none";

        try {
            const response = await fetch(`${API_BASE_URL}/login`, {
                method: "POST",
                credentials: "include",
                headers: { "Content-Type": "application/json", ...CSRF_HEADERS },
                body: JSON.stringify({ username_or_email, password })
            });
            const data = await response.json().catch(() => ({}));

            if (response.ok) {
                // Token yahan nahi aata: server ne HttpOnly cookie set kar di hay
                alert(data.msg);
                window.location.href = "index.html";
            } else {
                errorMsg.textContent = extractErrorMessage(data, "Login failed. Please check your credentials.");

                // Email verify nahi hui to dobara bhejne ka button
                if (response.status === 403) {
                    const resend = document.createElement("button");
                    resend.type = "button";
                    resend.textContent = "Resend verification email";
                    resend.style.cssText = "display:block;margin:0.75rem auto 0;cursor:pointer;";
                    resend.addEventListener("click", async () => {
                        const email = username_or_email.includes("@")
                            ? username_or_email
                            : window.prompt("Enter the email you signed up with:");
                        if (email) await resendVerification(email.trim());
                    });
                    errorMsg.append(resend);
                }
                errorMsg.style.display = "block";
            }
        } catch (error) {
            console.error("Error during login:", error);
            errorMsg.textContent = "Could not reach the server. Please try again later.";
            errorMsg.style.display = "block";
        }
    });
}

const signupForm = document.getElementById("signupForm");
if (signupForm) {
    signupForm.addEventListener("submit", async (event) => {
        event.preventDefault();

        const errorBox = document.getElementById("error-box");
        errorBox.textContent = "";
        errorBox.style.display = "none";
        const user = {
            username: document.getElementById("sign_username").value.trim(),
            email: document.getElementById("sign_email").value.trim(),
            password: document.getElementById("sign_password").value
        };

        try {
            const response = await fetch(`${API_BASE_URL}/signup`, {
                method: "POST",
                credentials: "include",
                headers: { "Content-Type": "application/json", ...CSRF_HEADERS },
                body: JSON.stringify(user)
            });
            const data = await response.json().catch(() => ({}));

            if (response.ok) {
                alert(data.msg || "Account created successfully. Please log in.");
                window.location.href = "login.html";
            } else {
                errorBox.textContent = extractErrorMessage(data, "Registration failed. Check the submitted details.");
                errorBox.style.display = "block";
            }
        } catch (error) {
            console.error("Error during signup:", error);
            errorBox.textContent = "Could not reach the server. Please try again later.";
            errorBox.style.display = "block";
        }
    });
}
