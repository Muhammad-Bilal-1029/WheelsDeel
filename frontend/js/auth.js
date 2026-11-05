// Backend aur frontend aik hi server se serve hotay hain, is liye relative "/api" use hota hai.
// Fallback: file:// ya VS Code Live Server (port 5500) se kholo to local backend use hoga.
const API_BASE_URL = (window.location.protocol === "file:" || window.location.port === "5500")
    ? "http://127.0.0.1:8000/api"
    : "/api";

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
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ username_or_email, password })
            });
            const data = await response.json();

            if (response.ok) {
                localStorage.setItem("token", data.token);
                localStorage.setItem("username", data.username);
                alert(data.msg);
                window.location.href = "index.html";
            } else {
                errorMsg.textContent = typeof data.detail === "string"
                    ? data.detail
                    : "Login failed. Please check your credentials.";
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
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(user)
            });
            const data = await response.json();

            if (response.ok) {
                alert("Account created successfully. Please log in.");
                window.location.href = "login.html";
            } else {
                errorBox.textContent = typeof data.detail === "string"
                    ? data.detail
                    : "Registration failed. Check the submitted details.";
                errorBox.style.display = "block";
            }
        } catch (error) {
            console.error("Error during signup:", error);
            errorBox.textContent = "Could not reach the server. Please try again later.";
            errorBox.style.display = "block";
        }
    });
}
