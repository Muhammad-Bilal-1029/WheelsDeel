// ==========================================================================
// CAR DETAIL PAGE: car.html?id=12
// app.js pehle load hota hay (login check, apiRequest, openReportDialog wahin se aate hain).
// Sab text textContent se dikhaya jata hay (HTML inject nahi hota).
// ==========================================================================
const detailBox = document.getElementById("car-detail");

function textElement(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    element.textContent = text;
    return element;
}

function buildGallery(car) {
    const gallery = document.createElement("div");
    gallery.className = "gallery";

    if (!car.images || car.images.length === 0) {
        gallery.append(textElement("div", "gallery-empty", "No photos for this ad"));
        return gallery;
    }

    const main = document.createElement("div");
    main.className = "gallery-main";
    const mainImage = document.createElement("img");
    mainImage.src = car.images[0].url;
    mainImage.alt = `${car.brand} ${car.model}`;
    main.append(mainImage);
    gallery.append(main);

    if (car.images.length > 1) {
        const strip = document.createElement("div");
        strip.className = "gallery-thumbs";
        car.images.forEach((photo, index) => {
            const button = document.createElement("button");
            button.type = "button";
            button.className = index === 0 ? "gallery-thumb is-active" : "gallery-thumb";
            button.setAttribute("aria-label", `Show photo ${index + 1}`);
            const thumb = document.createElement("img");
            thumb.src = photo.thumb_url;
            thumb.alt = "";
            thumb.loading = "lazy";
            button.append(thumb);
            button.addEventListener("click", () => {
                mainImage.src = photo.url;
                strip.querySelectorAll(".gallery-thumb").forEach((b) => b.classList.remove("is-active"));
                button.classList.add("is-active");
            });
            strip.append(button);
        });
        gallery.append(strip);
    }
    return gallery;
}

function buildSpecs(car) {
    const list = document.createElement("dl");
    list.className = "spec-list";
    const rows = [
        ["Model year", car.year],
        ["City", car.city],
        ["Mileage", car.mileage !== null && car.mileage !== undefined ? `${Number(car.mileage).toLocaleString()} km` : null],
        ["Fuel type", FUEL_LABELS[car.fuel_type]],
        ["Transmission", TRANSMISSION_LABELS[car.transmission]],
        ["Engine", car.engine_cc ? `${Number(car.engine_cc).toLocaleString()} cc` : null],
        ["Color", car.color],
        ["Condition", CONDITION_LABELS[car.condition]],
        ["Seller", car.seller_name],
    ];
    for (const [label, value] of rows) {
        if (value === null || value === undefined || value === "") continue;
        list.append(textElement("dt", "", label), textElement("dd", "", String(value)));
    }
    return list;
}

function renderCar(car, user) {
    document.title = `${car.brand} ${car.model} (${car.year}) - WheelDeal`;
    detailBox.className = car.status === "sold" ? "car-detail is-sold" : "car-detail";

    const layout = document.createElement("div");
    layout.className = "car-detail-layout";

    const info = document.createElement("div");
    info.className = "car-detail-info";

    info.append(textElement("h1", "detail-title", `${car.brand} ${car.model}`));
    info.append(textElement("div", "price detail-price", formatPrice(car.price)));

    const status = document.createElement("p");
    status.className = "detail-status";
    const statusValue = textElement("strong", `status-text status-${statusKey(car.status)}`, statusLabel(car.status));
    status.append("Status: ", statusValue);
    info.append(status);

    if (car.status === "sold") {
        info.append(textElement("p", "detail-notice", "This car has been sold and is no longer available."));
    } else if (car.status === "pending") {
        info.append(textElement("p", "detail-notice detail-notice-pending", "A buyer has reserved this car. It may be sold soon."));
    }
    if (car.is_hidden) {
        info.append(textElement("p", "detail-notice detail-notice-hidden", "This ad was removed by the moderators and is not visible to buyers."));
    }

    info.append(buildSpecs(car));

    if (car.description) {
        info.append(textElement("h2", "detail-heading", "Description"));
        info.append(textElement("p", "detail-description", car.description));
    }

    const contact = document.createElement("div");
    contact.className = "detail-contact";
    if (/^\+?\d{7,15}$/.test(car.seller_phone || "") && car.status !== "sold") {
        const call = document.createElement("a");
        call.className = "filter-apply detail-call";
        call.href = `tel:${car.seller_phone}`;
        call.textContent = `Call seller: ${car.seller_phone}`;
        contact.append(call);
    } else {
        contact.append(textElement("div", "contact-btn", `Contact: ${car.seller_phone}`));
    }

    if (user && car.owner_id === user.id) {
        const edit = document.createElement("a");
        edit.className = "my-ad-link";
        edit.href = `sell.html?id=${encodeURIComponent(car.id)}`;
        edit.textContent = "Edit this ad";
        const mine = document.createElement("a");
        mine.className = "my-ad-link";
        mine.href = "my-ads.html";
        mine.textContent = "My Ads";
        contact.append(edit, mine);
    } else if (user && !car.is_hidden) {
        const report = document.createElement("button");
        report.type = "button";
        report.className = "report-btn";
        report.textContent = "Report ad";
        report.style.cssText = "background:none;border:none;color:#dc2626;cursor:pointer;text-decoration:underline;padding:0;font-size:0.9rem;";
        report.addEventListener("click", () => openReportDialog(car, report));
        contact.append(report);
    }
    info.append(contact);

    layout.append(buildGallery(car), info);
    detailBox.replaceChildren(layout);
}

function showDetailMessage(message) {
    const wrapper = document.createElement("div");
    wrapper.className = "detail-missing";
    wrapper.append(textElement("p", "", message));
    const back = document.createElement("a");
    back.href = "index.html";
    back.textContent = "Browse available vehicles";
    wrapper.append(back);
    detailBox.replaceChildren(wrapper);
}

onWheelDealReady(async (user) => {
    const id = new URLSearchParams(window.location.search).get("id");
    if (!id || !/^\d+$/.test(id)) {
        showDetailMessage("This ad link is not valid.");
        return;
    }
    try {
        renderCar(await apiRequest(`/cars/${encodeURIComponent(id)}`), user);
    } catch (error) {
        showDetailMessage(error.status === 404 ? "This ad is no longer available." : (error.message || "Could not load this ad."));
    }
});
