// ==========================================================================
// CENTRAL CONFIGURATION & LAYER INTEGRATION
// ==========================================================================
// Frontend aur backend aik hi server se serve hotay hain, is liye relative "/api" use hota hai.
// Fallback: file:// ya VS Code Live Server se kholo to local backend use hoga
// (us surat mai backend ki .env mai CORS_ORIGINS=http://127.0.0.1:5500 jaisa set karna zaroori hai).
const BACKEND_API_URL = (window.location.protocol === "file:" || window.location.port === "5500" || window.location.port === "5501")
    ? "http://127.0.0.1:8000/api"
    : "/api";

// POST requests par server yeh header check karta hai (CSRF se bachao)
const CSRF_HEADERS = { "X-Requested-With": "WheelDeal" };

// Login ab HttpOnly cookie se hota hai (JavaScript usay padh nahi sakti).
// Purane version ka token localStorage mai reh gaya ho to hata do.
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

async function fetchCurrentUser() {
    try {
        const response = await fetch(`${BACKEND_API_URL}/me`, { credentials: "include", cache: "no-store" });
        if (!response.ok) return null;
        return await response.json();
    } catch (error) {
        return null;
    }
}

async function logoutUser() {
    try {
        await fetch(`${BACKEND_API_URL}/logout`, {
            method: "POST",
            credentials: "include",
            headers: CSRF_HEADERS,
        });
    } catch (error) {
        console.error("Logout request failed:", error);
    }
    window.location.href = "login.html";
}

function createNavigationLink(href, text, className = "") {
    const anchor = document.createElement("a");
    anchor.href = href;
    anchor.textContent = text;
    if (className) anchor.className = className;
    return anchor;
}

function buildNavigation(user) {
    const nav = document.getElementById("nav-links-container");
    if (!nav) return;

    // Login se pehle sirf Login / Sign Up dikhte hain; baqi pages login ke baad
    const links = !user ? [] : [
        createNavigationLink("index.html#home", "Home", "nav-page-link"),
        createNavigationLink("services.html#services-list", "Our Services", "nav-page-link"),
        createNavigationLink("contact.html#contact", "Contact", "nav-page-link"),
        createNavigationLink("analytics.html", "Analytics", "nav-page-link"),
    ];

    const currentPage = window.location.pathname.split("/").pop() || "index.html";
    const activeLink = links.find((link) => link.pathname.split("/").pop() === currentPage);
    if (activeLink) activeLink.setAttribute("aria-current", "page");

    if (user) {
        const logout = createNavigationLink("#", "Logout");
        logout.addEventListener("click", (event) => {
            event.preventDefault();
            logoutUser();
        });
        links.push(
            createNavigationLink("sell.html", "Sell Car", "btn-nav nav-page-link"),
            logout,
        );

        const welcome = document.createElement("span");
        welcome.className = "nav-welcome";
        welcome.textContent = `Welcome, ${user.username}!`;
        links.push(welcome);
    } else {
        links.push(
            createNavigationLink("login.html", "Login"),
            createNavigationLink("signup.html", "Sign Up"),
        );
    }

    nav.replaceChildren(...links);
}

async function renderNavigation() {
    buildNavigation(null);                       // foran logged-out nav dikhao
    const user = await fetchCurrentUser();       // phir server se pooch kar update karo
    if (user) buildNavigation(user);
    return user;
}

function showMarketplaceMessage(container, message, isError = false) {
    const paragraph = document.createElement("p");
    paragraph.textContent = message;
    paragraph.style.color = isError ? "#dc2626" : "#475569";
    paragraph.style.gridColumn = "1 / -1";
    paragraph.style.textAlign = "center";
    paragraph.style.fontWeight = "600";
    paragraph.style.padding = "2rem";
    container.replaceChildren(paragraph);
}

function createCarCard(car) {
    const card = document.createElement("article");
    card.className = "car-card";

    const body = document.createElement("div");
    body.className = "car-card-body";

    const title = document.createElement("h3");
    title.textContent = `${car.brand} ${car.model}`;

    const price = document.createElement("div");
    price.className = "price";
    price.textContent = `PKR ${Number(car.price).toLocaleString()}`;

    const details = document.createElement("div");
    details.className = "details-meta";
    const year = document.createElement("span");
    year.textContent = `Year: ${car.year}`;
    const status = document.createElement("span");
    status.textContent = "Status: Available";
    details.append(year, status);

    const contact = document.createElement("div");
    contact.className = "contact-btn";
    contact.textContent = `Contact: ${car.seller_phone}`;

    body.append(title, price, details, contact);
    card.append(body);
    return card;
}

async function loadMarketplaceCars(brandFilter = "") {
    const carsContainer = document.getElementById("cars-container");
    if (!carsContainer) return;

    try {
        const targetUrl = new URL(`${BACKEND_API_URL}/cars`, window.location.href);
        if (brandFilter) targetUrl.searchParams.set("brand", brandFilter);

        const response = await fetch(targetUrl, { credentials: "include" });
        if (response.status === 401) {
            window.location.replace("login.html");
            return;
        }
        if (!response.ok) {
            throw new Error(`Car listings request failed (${response.status}).`);
        }

        const cars = await response.json();
        if (!Array.isArray(cars)) {
            throw new Error("The server returned an invalid car listings response.");
        }
        if (cars.length === 0) {
            showMarketplaceMessage(carsContainer, "No vehicle listings found matching your search. Be the first to sell!");
            return;
        }

        carsContainer.replaceChildren(...cars.map(createCarCard));
    } catch (error) {
        console.error("Marketplace loader failure:", error);
        showMarketplaceMessage(carsContainer, "Could not load vehicle listings. Check that the backend server is running.", true);
    }
}

function formatAnalyticsMetric(value) {
    return value === null || value === undefined ? "Not tracked" : Number(value).toLocaleString();
}

async function loadAnalyticsDashboard() {
    const dashboard = document.getElementById("analytics-dashboard");
    if (!dashboard) return;

    const status = document.getElementById("analytics-status");
    const availableCars = document.getElementById("analytics-available-cars");
    const totalListings = document.getElementById("analytics-total-listings");
    const carTableBody = document.getElementById("analytics-cars-list");

    try {
        const [analyticsResponse, carsResponse] = await Promise.all([
            fetch(`${BACKEND_API_URL}/analytics`, { credentials: "include" }),
            fetch(`${BACKEND_API_URL}/cars`, { credentials: "include" }),
        ]);
        if (analyticsResponse.status === 401 || carsResponse.status === 401) {
            window.location.replace("login.html");
            return;
        }
        if (!analyticsResponse.ok || !carsResponse.ok) {
            throw new Error("Analytics data request failed.");
        }

        const analytics = await analyticsResponse.json();
        const cars = await carsResponse.json();
        if (!Array.isArray(cars) || typeof analytics.total_listings !== "number") {
            throw new Error("The server returned invalid analytics data.");
        }

        totalListings.textContent = formatAnalyticsMetric(analytics.total_listings);
        availableCars.textContent = formatAnalyticsMetric(analytics.available_cars);
        document.getElementById("analytics-pending-cars").textContent = formatAnalyticsMetric(analytics.pending_cars);
        document.getElementById("analytics-sold-cars").textContent = formatAnalyticsMetric(analytics.sold_cars);

        if (cars.length === 0) {
            const row = document.createElement("tr");
            const cell = document.createElement("td");
            cell.colSpan = 4;
            cell.textContent = "No vehicle listings yet.";
            row.append(cell);
            carTableBody.replaceChildren(row);
        } else {
            carTableBody.replaceChildren(...cars.map((car) => {
                const row = document.createElement("tr");
                [ `${car.brand} ${car.model}`, car.year, `PKR ${Number(car.price).toLocaleString()}`, "Available" ]
                    .forEach((value) => {
                        const cell = document.createElement("td");
                        cell.textContent = value;
                        row.append(cell);
                    });
                return row;
            }));
        }
        status.textContent = "Live listing data loaded.";
        status.classList.remove("analytics-status-error");
    } catch (error) {
        console.error("Analytics loader failure:", error);
        status.textContent = "Could not load live analytics. Check that the backend server is running.";
        status.classList.add("analytics-status-error");
        totalListings.textContent = "—";
        availableCars.textContent = "—";
        document.getElementById("analytics-pending-cars").textContent = "—";
        document.getElementById("analytics-sold-cars").textContent = "—";
        carTableBody.replaceChildren();
    }
}

function filterCars() {
    const searchInput = document.getElementById("search-brand");
    loadMarketplaceCars(searchInput ? searchInput.value.trim() : "");
}

const sellForm = document.getElementById("sellForm");
if (sellForm) {
    sellForm.addEventListener("submit", async (event) => {
        event.preventDefault();

        const errorBox = document.getElementById("error-box");
        errorBox.textContent = "";
        errorBox.style.display = "none";

        const carData = {
            brand: document.getElementById("brand").value.trim(),
            model: document.getElementById("model").value.trim(),
            year: Number(document.getElementById("year").value),
            price: Number(document.getElementById("price").value),
            seller_phone: document.getElementById("phone").value.trim()
        };

        try {
            const response = await fetch(`${BACKEND_API_URL}/cars`, {
                method: "POST",
                credentials: "include",
                headers: {
                    "Content-Type": "application/json",
                    ...CSRF_HEADERS,
                },
                body: JSON.stringify(carData)
            });
            const data = await response.json().catch(() => ({}));

            if (response.ok) {
                alert("Success! Your car advertisement has been published.");
                window.location.href = "index.html";
            } else if (response.status === 401) {
                alert("Session expired. Please log in again to create vehicle ads.");
                window.location.href = "login.html";
            } else {
                errorBox.textContent = extractErrorMessage(data, "Could not publish the ad. Check the submitted details.");
                errorBox.style.display = "block";
            }
        } catch (error) {
            console.error("Ad pipeline execution failure:", error);
            errorBox.textContent = "Could not reach the server. Please try again later.";
            errorBox.style.display = "block";
        }
    });
}

// Global DOM Content Loaded Trigger
document.addEventListener("DOMContentLoaded", async () => {
    const user = await renderNavigation();

    // Har page login ke baad hi dikhta hay (asli rok server par hay, yeh sirf user ko login page par bhejta hay)
    if (!user) {
        window.location.replace("login.html");
        return;
    }

    loadMarketplaceCars();
    loadAnalyticsDashboard();

    const logoutBtn = document.getElementById("logoutBtn");
    if (logoutBtn) logoutBtn.style.display = "inline-block";

    const quoteForm = document.getElementById("quoteForm");
    if (quoteForm) {
        quoteForm.addEventListener("submit", (event) => {
            event.preventDefault();
            const formData = new FormData(quoteForm);
            const message = [
                `Name: ${formData.get("fullName")}`,
                `Phone: ${formData.get("phone")}`,
                `Vehicle: ${formData.get("vehicle")}`,
                `Service: ${formData.get("service")}`,
            ].join("\n");
            const subject = encodeURIComponent("WheelDeal consultation request");
            window.location.href = `mailto:bilalahmad10281029@gmail.com?subject=${subject}&body=${encodeURIComponent(message)}`;
        });
    }
});
