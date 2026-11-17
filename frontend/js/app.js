// ==========================================================================
// CENTRAL CONFIGURATION & LAYER INTEGRATION
// ==========================================================================
// Frontend aur backend aik hi server se serve hotay hain, is liye relative "/api" use hota hai.
// Fallback: file:// ya VS Code Live Server se kholo to local backend use hoga
// (us surat mai backend ki .env mai CORS_ORIGINS=http://127.0.0.1:5500 jaisa set karna zaroori hai).
const BACKEND_API_URL = (window.location.protocol === "file:" || window.location.port === "5500" || window.location.port === "5501")
    ? "http://127.0.0.1:8000/api"
    : "/api";

// POST/PATCH/DELETE requests par server yeh header check karta hai (CSRF se bachao)
const CSRF_HEADERS = { "X-Requested-With": "WheelDeal" };

// Logged-in user (DOMContentLoaded mai /api/me se set hota hay). Car cards par apni ads pehchanne ke kaam aata hay.
let currentUser = null;

const CAR_STATUS_LABELS = { available: "Available", pending: "Pending", sold: "Sold" };
const FUEL_LABELS = { petrol: "Petrol", diesel: "Diesel", hybrid: "Hybrid", electric: "Electric", cng: "CNG", lpg: "LPG" };
const TRANSMISSION_LABELS = { manual: "Manual", automatic: "Automatic" };
const CONDITION_LABELS = { new: "New", used: "Used" };

function statusLabel(value) {
    return CAR_STATUS_LABELS[value] || "Available";
}

// CSS class ke liye safe key (sirf available / pending / sold)
function statusKey(value) {
    return Object.prototype.hasOwnProperty.call(CAR_STATUS_LABELS, value) ? value : "available";
}

function formatPrice(value) {
    return `PKR ${Number(value).toLocaleString()}`;
}

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

// Shared API helper (sell, my-ads, car pages istemal karte hain).
// Kamyabi par JSON lautata hay; error par Error (message + status) throw karta hay; 401 par login page.
async function apiRequest(path, { method = "GET", body, headers = {}, rawBody = false } = {}) {
    const options = { method, credentials: "include", headers: { ...CSRF_HEADERS, ...headers } };
    if (body !== undefined) {
        options.body = rawBody ? body : JSON.stringify(body);
        if (!rawBody) options.headers["Content-Type"] = "application/json";
    }
    const response = await fetch(`${BACKEND_API_URL}${path}`, options);
    if (response.status === 401) {
        window.location.replace("login.html");
        throw new Error("Please log in again.");
    }
    const data = await response.json().catch(() => null);
    if (!response.ok) {
        const error = new Error(extractErrorMessage(data, `Request failed (${response.status}).`));
        error.status = response.status;
        throw error;
    }
    return data;
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

// Page ke apne scripts (sell.js, car.js, my-ads.js) login check ke baad chalne ke liye
function onWheelDealReady(callback) {
    if (window.__wheelDealUser) {
        callback(window.__wheelDealUser);
    } else {
        document.addEventListener("wheeldeal:ready", (event) => callback(event.detail.user), { once: true });
    }
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
        createNavigationLink("index.html#home", "Home", "nav-page-link nav-main-link"),
        createNavigationLink("services.html#services-list", "Our Services", "nav-page-link nav-main-link"),
        createNavigationLink("contact.html#contact", "Contact", "nav-page-link nav-main-link"),
        createNavigationLink("analytics.html", "Analytics", "nav-page-link nav-main-link"),
    ];

    const currentPage = window.location.pathname.split("/").pop() || "index.html";
    const activeLink = links.find((link) => link.pathname.split("/").pop() === currentPage);
    if (activeLink) activeLink.setAttribute("aria-current", "page");

    // Header ki 2 rows: upar (search ke saath) Login / Logout / Welcome, neeche logo + page links
    const authLinks = [];
    if (user) {
        const logout = createNavigationLink("#", "Logout");
        logout.addEventListener("click", (event) => {
            event.preventDefault();
            logoutUser();
        });
        const myAds = createNavigationLink("my-ads.html", "My Ads", "nav-page-link");
        if (currentPage === "my-ads.html") myAds.setAttribute("aria-current", "page");
        links.push(myAds);
        if (user.is_admin) {
            links.push(createNavigationLink("admin.html", "Admin", "nav-page-link"));
        }
        links.push(createNavigationLink("sell.html", "Sell Car", "btn-nav nav-page-link"));

        const welcome = document.createElement("span");
        welcome.className = "nav-welcome";
        welcome.textContent = `Welcome, ${user.username}!`;
        authLinks.push(logout, welcome);
    } else {
        authLinks.push(
            createNavigationLink("login.html", "Login"),
            createNavigationLink("signup.html", "Sign Up"),
        );
    }

    // Purane markup mai auth box na ho to sab kuch pehle ki tarah nav mai hi rehta hay
    const authBox = document.getElementById("auth-links-container");
    if (authBox) authBox.replaceChildren(...authLinks);
    else links.push(...authLinks);

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

// Ad ka status badlo (owner). true = kamyab. Mukhtalif pages (home / My Ads) apni list khud refresh karte hain.
async function changeCarStatus(carId, newStatus) {
    try {
        await apiRequest(`/cars/${encodeURIComponent(carId)}/status`, { method: "PATCH", body: { status: newStatus } });
        return true;
    } catch (error) {
        alert(error.message || "Could not update the status.");
        return false;
    }
}

const REPORT_REASONS = {
    spam: "Spam or duplicate ad",
    fake_or_scam: "Fake ad or scam",
    wrong_info: "Wrong price or details",
    inappropriate: "Inappropriate content",
    other: "Other (please describe)",
};

// Kisi ad ki shikayat: chhota dialog, jawab seedha moderators (admin) tak jata hay
function openReportDialog(car, reportButton) {
    const dialog = document.createElement("dialog");
    dialog.style.cssText = "border:1px solid #cbd5e1;border-radius:12px;padding:1.25rem;width:min(420px,92vw);";

    const form = document.createElement("form");
    form.style.cssText = "display:flex;flex-direction:column;gap:0.75rem;";

    const heading = document.createElement("h3");
    heading.textContent = "Report this ad";
    const subject = document.createElement("p");
    subject.textContent = `${car.brand} ${car.model} (${car.year})`;

    const reason = document.createElement("select");
    reason.required = true;
    reason.setAttribute("aria-label", "Reason");
    for (const [value, text] of Object.entries(REPORT_REASONS)) {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = text;
        reason.append(option);
    }

    const details = document.createElement("textarea");
    details.rows = 4;
    details.maxLength = 500;
    details.placeholder = "Tell the moderators what is wrong (optional)";
    details.setAttribute("aria-label", "Details");

    const error = document.createElement("p");
    error.style.cssText = "color:#dc2626;display:none;margin:0;";
    error.setAttribute("role", "alert");

    const actions = document.createElement("div");
    actions.style.cssText = "display:flex;gap:0.5rem;justify-content:flex-end;";
    const cancel = document.createElement("button");
    cancel.type = "button";
    cancel.textContent = "Cancel";
    cancel.addEventListener("click", () => dialog.close());
    const submit = document.createElement("button");
    submit.type = "submit";
    submit.textContent = "Send report";
    actions.append(cancel, submit);

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        error.style.display = "none";
        submit.disabled = true;
        try {
            const data = await apiRequest(`/cars/${encodeURIComponent(car.id)}/report`, {
                method: "POST",
                body: { reason: reason.value, details: details.value.trim() || null },
            });
            reportButton.textContent = "Reported";
            reportButton.disabled = true;
            dialog.close();
            alert(data.msg);
        } catch (err) {
            if (err.status === 409) {
                // Pehle hi report kar chuke hain: dobara button ki zaroorat nahi
                reportButton.textContent = "Reported";
                reportButton.disabled = true;
            }
            error.textContent = err.message || "Could not send the report.";
            error.style.display = "block";
        } finally {
            submit.disabled = false;
        }
    });
    form.append(heading, subject, reason, details, error, actions);
    dialog.append(form);
    dialog.addEventListener("close", () => dialog.remove());
    document.body.append(dialog);
    dialog.showModal();
}

// "42,000 km", "Petrol", "Automatic", "Lahore" jaise chhote facts (jo ad mai likhe hon)
function carSpecList(car) {
    return [
        car.mileage !== null && car.mileage !== undefined ? `${Number(car.mileage).toLocaleString()} km` : null,
        FUEL_LABELS[car.fuel_type] || null,
        TRANSMISSION_LABELS[car.transmission] || null,
        car.city || null,
    ].filter(Boolean);
}

function createCarCard(car) {
    const card = document.createElement("article");
    card.className = car.status === "sold" ? "car-card is-sold" : "car-card";
    const detailUrl = `car.html?id=${encodeURIComponent(car.id)}`;
    const carName = `${car.brand} ${car.model}`;

    // Photo (thumbnail) ya "No photo" placeholder: dono click karne par detail page kholte hain
    const media = document.createElement("a");
    media.className = "car-card-media";
    media.href = detailUrl;
    media.setAttribute("aria-label", `View details: ${carName}`);
    if (car.cover_thumb) {
        const photo = document.createElement("img");
        photo.src = car.cover_thumb;
        photo.alt = carName;
        photo.loading = "lazy";
        media.append(photo);
        if (car.images && car.images.length > 1) {
            const count = document.createElement("span");
            count.className = "photo-count";
            count.textContent = `${car.images.length} photos`;
            media.append(count);
        }
    } else {
        const placeholder = document.createElement("span");
        placeholder.className = "car-card-noimage";
        placeholder.textContent = "No photo";
        media.append(placeholder);
    }

    const body = document.createElement("div");
    body.className = "car-card-body";

    const title = document.createElement("h3");
    const titleLink = document.createElement("a");
    titleLink.href = detailUrl;
    titleLink.textContent = carName;
    title.append(titleLink);

    const price = document.createElement("div");
    price.className = "price";
    price.textContent = formatPrice(car.price);

    const specs = carSpecList(car);
    const specLine = document.createElement("div");
    specLine.className = "car-specs";
    specLine.textContent = specs.join(" • ");

    const details = document.createElement("div");
    details.className = "details-meta";
    const year = document.createElement("span");
    year.textContent = `Year: ${car.year}`;
    const status = document.createElement("span");
    const statusValue = document.createElement("strong");
    statusValue.className = `status-text status-${statusKey(car.status)}`;
    statusValue.textContent = statusLabel(car.status);
    status.append("Status: ", statusValue);
    details.append(year, status);

    const contact = document.createElement("div");
    contact.className = "contact-btn";
    contact.textContent = `Contact: ${car.seller_phone}`;

    body.append(title, price);
    if (specs.length > 0) body.append(specLine);
    body.append(details, contact);

    // Sirf ad ka maalik status badal sakta hay (server bhi yehi check karta hay)
    if (currentUser && car.owner_id === currentUser.id) {
        const controls = document.createElement("div");
        controls.className = "status-controls";
        controls.style.marginTop = "0.75rem";

        const label = document.createElement("label");
        label.textContent = "Your ad status: ";

        const select = document.createElement("select");
        select.setAttribute("aria-label", "Change ad status");
        for (const [value, text] of Object.entries(CAR_STATUS_LABELS)) {
            const option = document.createElement("option");
            option.value = value;
            option.textContent = text;
            option.selected = value === car.status;
            select.append(option);
        }
        select.addEventListener("change", async () => {
            select.disabled = true;
            await changeCarStatus(car.id, select.value);
            filterCars();   // list dobara load: asli status dikhe (fail hone par purani value wapas aa jaye)
        });

        label.append(select);
        controls.append(label);
        body.append(controls);
    } else if (currentUser) {
        // Dusre ki ad: report ka option
        const report = document.createElement("button");
        report.type = "button";
        report.className = "report-btn";
        report.textContent = "Report ad";
        report.style.cssText = "margin-top:0.75rem;background:none;border:none;color:#dc2626;cursor:pointer;text-decoration:underline;padding:0;font-size:0.85rem;";
        report.addEventListener("click", () => openReportDialog(car, report));
        body.append(report);
    }

    card.append(media, body);
    return card;
}

// ==========================================================================
// HOME PAGE: search + filters + sorting + "Load more"
// ==========================================================================
const MARKETPLACE_PAGE_SIZE = 12;
const marketplaceState = { offset: 0, total: 0, busy: false };

const FILTER_FIELDS = {
    q: "search-brand",              // header wala search box
    city: "filter-city",
    fuel_type: "filter-fuel",
    transmission: "filter-transmission",
    condition: "filter-condition",
    min_price: "filter-min-price",
    max_price: "filter-max-price",
    min_year: "filter-min-year",
    max_year: "filter-max-year",
    sort: "filter-sort",
};

function readField(id) {
    const element = document.getElementById(id);
    return element ? element.value.trim() : "";
}

function hasActiveFilters() {
    return Object.entries(FILTER_FIELDS).some(([param, id]) => param !== "sort" && readField(id) !== "");
}

function buildMarketplaceQuery(offset) {
    const params = new URLSearchParams();
    for (const [param, id] of Object.entries(FILTER_FIELDS)) {
        const value = readField(id);
        if (value) params.set(param, value);
    }
    params.set("limit", String(MARKETPLACE_PAGE_SIZE));
    params.set("offset", String(offset));
    return params;
}

function updateResultsSummary(message = null) {
    const summary = document.getElementById("results-summary");
    if (summary) {
        summary.textContent = message !== null
            ? message
            : marketplaceState.total === 0
                ? ""
                : `Showing ${Math.min(marketplaceState.offset, marketplaceState.total)} of ${marketplaceState.total} vehicle(s)`;
    }
    const loadMore = document.getElementById("load-more");
    if (loadMore) loadMore.hidden = marketplaceState.offset >= marketplaceState.total;
}

async function loadMarketplaceCars({ append = false } = {}) {
    const carsContainer = document.getElementById("cars-container");
    if (!carsContainer || marketplaceState.busy) return;

    const minPrice = Number(readField("filter-min-price"));
    const maxPrice = Number(readField("filter-max-price"));
    if (readField("filter-min-price") && readField("filter-max-price") && minPrice > maxPrice) {
        updateResultsSummary("Minimum price is higher than maximum price.");
        return;
    }

    marketplaceState.busy = true;
    const offset = append ? marketplaceState.offset : 0;
    try {
        const response = await fetch(`${BACKEND_API_URL}/cars?${buildMarketplaceQuery(offset)}`, { credentials: "include" });
        if (response.status === 401) {
            window.location.replace("login.html");
            return;
        }
        if (!response.ok) {
            const problem = await response.json().catch(() => null);
            throw new Error(extractErrorMessage(problem, `Car listings request failed (${response.status}).`));
        }

        const data = await response.json();
        if (!data || !Array.isArray(data.items) || typeof data.total !== "number") {
            throw new Error("The server returned an invalid car listings response.");
        }

        marketplaceState.total = data.total;
        marketplaceState.offset = offset + data.items.length;

        if (!append && data.items.length === 0) {
            showMarketplaceMessage(
                carsContainer,
                hasActiveFilters()
                    ? "No vehicles match your search or filters. Try changing or resetting them."
                    : "No vehicle listings found. Be the first to sell!",
            );
        } else if (append) {
            carsContainer.append(...data.items.map(createCarCard));
        } else {
            carsContainer.replaceChildren(...data.items.map(createCarCard));
        }
        updateResultsSummary();
    } catch (error) {
        console.error("Marketplace loader failure:", error);
        showMarketplaceMessage(carsContainer, "Could not load vehicle listings. Check that the backend server is running.", true);
    } finally {
        marketplaceState.busy = false;
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
        // Sold cars listing mai nahi aati (buyer ko sold car par request na karni pare): sirf available + pending
        const [analyticsResponse, carsResponse] = await Promise.all([
            fetch(`${BACKEND_API_URL}/analytics`, { credentials: "include" }),
            fetch(`${BACKEND_API_URL}/cars?status=available&status=pending&limit=100&sort=newest`, { credentials: "include" }),
        ]);
        if (analyticsResponse.status === 401 || carsResponse.status === 401) {
            window.location.replace("login.html");
            return;
        }
        if (!analyticsResponse.ok || !carsResponse.ok) {
            throw new Error("Analytics data request failed.");
        }

        const analytics = await analyticsResponse.json();
        const carsData = await carsResponse.json();
        const listedCars = carsData && Array.isArray(carsData.items) ? carsData.items : null;
        if (!listedCars || typeof analytics.total_listings !== "number") {
            throw new Error("The server returned invalid analytics data.");
        }

        totalListings.textContent = formatAnalyticsMetric(analytics.total_listings);
        availableCars.textContent = formatAnalyticsMetric(analytics.available_cars);
        document.getElementById("analytics-pending-cars").textContent = formatAnalyticsMetric(analytics.pending_cars);
        document.getElementById("analytics-sold-cars").textContent = formatAnalyticsMetric(analytics.sold_cars);

        if (listedCars.length === 0) {
            const row = document.createElement("tr");
            const cell = document.createElement("td");
            cell.colSpan = 4;
            cell.textContent = "No vehicle listings available right now.";
            row.append(cell);
            carTableBody.replaceChildren(row);
        } else {
            carTableBody.replaceChildren(...listedCars.map((car) => {
                const row = document.createElement("tr");
                [ `${car.brand} ${car.model}`, car.year, formatPrice(car.price), statusLabel(car.status) ]
                    .forEach((value, index) => {
                        const cell = document.createElement("td");
                        if (index === 3) {
                            // Status: Available = PKR wala green, Pending = amber orange
                            const badge = document.createElement("span");
                            badge.className = `status-text status-${statusKey(car.status)}`;
                            badge.textContent = value;
                            cell.append(badge);
                        } else {
                            cell.textContent = value;
                        }
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

// Search / filters apply karo (header search box aur status badalne ke baad bhi yehi chalta hay)
function filterCars() {
    loadMarketplaceCars();
}

function setupMarketplaceControls() {
    const searchForm = document.getElementById("navbar-search");
    if (searchForm) {
        searchForm.addEventListener("submit", (event) => {
            event.preventDefault();
            filterCars();
        });
    }

    const filterForm = document.getElementById("filter-form");
    if (filterForm) {
        filterForm.addEventListener("submit", (event) => {
            event.preventDefault();
            filterCars();
        });
    }

    const sortSelect = document.getElementById("filter-sort");
    if (sortSelect) sortSelect.addEventListener("change", filterCars);

    const resetButton = document.getElementById("filter-reset");
    if (resetButton) {
        resetButton.addEventListener("click", () => {
            for (const id of Object.values(FILTER_FIELDS)) {
                const element = document.getElementById(id);
                if (element) element.value = element.id === "filter-sort" ? "newest" : "";
            }
            filterCars();
        });
    }

    const loadMore = document.getElementById("load-more");
    if (loadMore) loadMore.addEventListener("click", () => loadMarketplaceCars({ append: true }));
}

// Global DOM Content Loaded Trigger
document.addEventListener("DOMContentLoaded", async () => {
    const user = await renderNavigation();

    // Har page login ke baad hi dikhta hay (asli rok server par hay, yeh sirf user ko login page par bhejta hay)
    if (!user) {
        window.location.replace("login.html");
        return;
    }

    currentUser = user;
    window.__wheelDealUser = user;
    document.dispatchEvent(new CustomEvent("wheeldeal:ready", { detail: { user } }));

    setupMarketplaceControls();
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
