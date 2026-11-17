// ==========================================================================
// MY ADS: user ki apni ads. Yahan se edit, delete aur Available/Pending/Sold mark hota hay.
// app.js pehle load hota hay (login check, apiRequest, changeCarStatus wahin se aate hain).
// ==========================================================================
const adsListBox = document.getElementById("my-ads-list");
const adsMessageBox = document.getElementById("my-ads-message");

function showAdsMessage(text, isError = false) {
    adsMessageBox.textContent = text;
    adsMessageBox.style.color = isError ? "#dc2626" : "";
}

function adLink(href, text, className = "my-ad-link") {
    const anchor = document.createElement("a");
    anchor.href = href;
    anchor.textContent = text;
    anchor.className = className;
    return anchor;
}

function createMyAdRow(car) {
    const row = document.createElement("article");
    row.className = car.status === "sold" ? "my-ad is-sold" : "my-ad";
    const detailUrl = `car.html?id=${encodeURIComponent(car.id)}`;
    const name = `${car.brand} ${car.model}`;

    const media = document.createElement("a");
    media.className = "my-ad-media";
    media.href = detailUrl;
    media.setAttribute("aria-label", `View ${name}`);
    if (car.cover_thumb) {
        const photo = document.createElement("img");
        photo.src = car.cover_thumb;
        photo.alt = name;
        photo.loading = "lazy";
        media.append(photo);
    } else {
        const none = document.createElement("span");
        none.className = "car-card-noimage";
        none.textContent = "No photo";
        media.append(none);
    }

    const info = document.createElement("div");
    info.className = "my-ad-info";

    const title = document.createElement("h3");
    title.append(adLink(detailUrl, `${name} (${car.year})`, "my-ad-title"));

    const price = document.createElement("div");
    price.className = "price";
    price.textContent = formatPrice(car.price);

    const specs = carSpecList(car);
    const specLine = document.createElement("div");
    specLine.className = "car-specs";
    specLine.textContent = specs.join(" • ");

    const statusLine = document.createElement("div");
    statusLine.className = "my-ad-status";
    const statusValue = document.createElement("strong");
    statusValue.className = `status-text status-${statusKey(car.status)}`;
    statusValue.textContent = statusLabel(car.status);
    statusLine.append("Status: ", statusValue);

    info.append(title, price);
    if (specs.length > 0) info.append(specLine);
    info.append(statusLine);

    const actions = document.createElement("div");
    actions.className = "my-ad-actions";

    if (car.is_hidden) {
        // Moderators ne hide ki hui ad: owner kuch nahi badal sakta
        const notice = document.createElement("p");
        notice.className = "my-ad-notice";
        notice.textContent = "This ad was removed by the moderators and is not visible to buyers.";
        actions.append(notice);
    } else {
        const label = document.createElement("label");
        label.textContent = "Mark as: ";
        const select = document.createElement("select");
        select.setAttribute("aria-label", `Status of ${name}`);
        for (const [value, text] of Object.entries(CAR_STATUS_LABELS)) {
            const option = document.createElement("option");
            option.value = value;
            option.textContent = text;
            option.selected = value === car.status;
            select.append(option);
        }
        select.addEventListener("change", async () => {
            select.disabled = true;
            const ok = await changeCarStatus(car.id, select.value);
            if (ok) showAdsMessage(`"${name}" is now marked as ${statusLabel(select.value)}.`);
            await loadMyAds();
        });
        label.append(select);

        const remove = document.createElement("button");
        remove.type = "button";
        remove.className = "my-ad-delete";
        remove.textContent = "Delete";
        remove.addEventListener("click", async () => {
            if (!window.confirm(`Delete "${name}"? This cannot be undone.`)) return;
            remove.disabled = true;
            try {
                await apiRequest(`/cars/${encodeURIComponent(car.id)}`, { method: "DELETE" });
                showAdsMessage(`"${name}" was deleted.`);
            } catch (error) {
                showAdsMessage(error.message, true);
            }
            await loadMyAds();
        });

        actions.append(label, adLink(`sell.html?id=${encodeURIComponent(car.id)}`, "Edit"), adLink(detailUrl, "View"), remove);
    }

    row.append(media, info, actions);
    return row;
}

async function loadMyAds() {
    try {
        const cars = await apiRequest("/my/cars");
        if (cars.length === 0) {
            const empty = document.createElement("p");
            empty.className = "muted";
            empty.append("You have not posted any ads yet. ", adLink("sell.html", "Post your first ad"), ".");
            adsListBox.replaceChildren(empty);
            return;
        }
        adsListBox.replaceChildren(...cars.map(createMyAdRow));
    } catch (error) {
        showAdsMessage(error.message || "Could not load your ads.", true);
    }
}

onWheelDealReady(() => loadMyAds());
