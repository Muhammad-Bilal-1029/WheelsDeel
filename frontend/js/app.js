// ==========================================================================
// CENTRAL CONFIGURATION & LAYER INTEGRATION
// ==========================================================================
const BACKEND_API_URL = (window.location.protocol === "file:" || window.location.port === "5500" || window.location.port === "5501")
    ? "http://127.0.0.1:8000/api"
    : "/api";

function createNavigationLink(href, text, className = "") {
    const anchor = document.createElement("a");
    anchor.href = href;
    anchor.textContent = text;
    if (className) anchor.className = className;
    return anchor;
}

function renderNavigation() {
    const nav = document.getElementById("nav-links-container");
    if (!nav) return;

    const links = [
        createNavigationLink("index.html#home", "Home"),
        createNavigationLink("services.html#services-list", "Our Services"),
        createNavigationLink("contact.html#contact", "Contact"),
        createNavigationLink("about.html#about", "About Us"),
        createNavigationLink("careers.html#careers", "Careers"),
        createNavigationLink("blogs.html#blogs", "Our Blogs"),
    ];

    const token = localStorage.getItem("token");
    const username = localStorage.getItem("username");
    if (token && username) {
        const logout = createNavigationLink("#", "Logout");
        logout.addEventListener("click", (event) => {
            event.preventDefault();
            localStorage.removeItem("token");
            localStorage.removeItem("username");
            window.location.reload();
        });
        links.push(
            createNavigationLink("sell.html", "Sell Car", "btn-nav"),
            logout,
        );

        const welcome = document.createElement("span");
        welcome.className = "nav-welcome";
        welcome.textContent = `Welcome, ${username}!`;
        links.push(welcome);
    } else {
        links.push(
            createNavigationLink("login.html", "Login"),
            createNavigationLink("signup.html", "Sign Up"),
            createNavigationLink("sell.html", "Sell Car", "btn-nav"),
        );
    }

    nav.replaceChildren(...links);
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

        const response = await fetch(targetUrl);
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

        const token = localStorage.getItem("token");
        if (!token) {
            alert("Session invalid. Please log in first to create vehicle ads.");
            window.location.href = "login.html";
            return;
        }

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
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${token}`
                },
                body: JSON.stringify(carData)
            });
            const data = await response.json();

            if (response.ok) {
                alert("Success! Your car advertisement has been published.");
                window.location.href = "index.html";
            } else {
                errorBox.textContent = typeof data.detail === "string"
                    ? data.detail
                    : "Validation error. Check the submitted details.";
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
document.addEventListener("DOMContentLoaded", () => {
    renderNavigation();
    loadMarketplaceCars();


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
