// ==========================================================================
// SELL / EDIT AD PAGE
// sell.html            -> nayi ad
// sell.html?id=12      -> apni ad 12 edit karo (details + photos)
// app.js pehle load hota hay (login check, apiRequest, onWheelDealReady wahin se aate hain).
// ==========================================================================
const MAX_PHOTOS = 8;
const MAX_PHOTO_BYTES = 5 * 1024 * 1024;
const ALLOWED_PHOTO_TYPES = ["image/jpeg", "image/png", "image/webp"];

const sellForm = document.getElementById("sellForm");
let editingId = null;      // edit mode mai ad ki id
let savedPhotos = [];      // server par pehle se maujood photos {id, url, thumb_url}
let pendingPhotos = [];    // abhi upload honay wali photos {file, previewUrl}

function showSellError(message) {
    const box = document.getElementById("error-box");
    box.textContent = message;
    box.style.display = message ? "block" : "none";
}

function setPhotoHint(message = null) {
    const used = savedPhotos.length + pendingPhotos.length;
    document.getElementById("photo-hint").textContent = message !== null
        ? message
        : `${used}/${MAX_PHOTOS} photos. JPEG, PNG or WebP, max 5 MB each. The first photo is the cover.`;
}

function photoButton(label, onClick) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "photo-btn";
    button.textContent = label;
    button.addEventListener("click", onClick);
    return button;
}

function photoItem(src, altText) {
    const figure = document.createElement("figure");
    figure.className = "photo-item";
    const image = document.createElement("img");
    image.src = src;
    image.alt = altText;
    figure.append(image);
    return figure;
}

function renderPhotos() {
    const savedBox = document.getElementById("existing-photos");
    const newBox = document.getElementById("new-photos");

    savedBox.replaceChildren(...savedPhotos.map((photo, index) => {
        const item = photoItem(photo.thumb_url, `Saved photo ${index + 1}`);
        if (index === 0) {
            const badge = document.createElement("span");
            badge.className = "photo-cover-badge";
            badge.textContent = "Cover";
            item.append(badge);
        }
        const actions = document.createElement("div");
        actions.className = "photo-actions";
        if (index > 0) actions.append(photoButton("Make cover", () => makeCover(photo)));
        actions.append(photoButton("Delete", () => deleteSavedPhoto(photo)));
        item.append(actions);
        return item;
    }));

    newBox.replaceChildren(...pendingPhotos.map((pending) => {
        const item = photoItem(pending.previewUrl, pending.file.name);
        const badge = document.createElement("span");
        badge.className = "photo-new-badge";
        badge.textContent = "New";
        const actions = document.createElement("div");
        actions.className = "photo-actions";
        actions.append(photoButton("Remove", () => {
            URL.revokeObjectURL(pending.previewUrl);
            pendingPhotos = pendingPhotos.filter((p) => p !== pending);
            renderPhotos();
        }));
        item.append(badge, actions);
        return item;
    }));

    setPhotoHint();
}

function handleFilesSelected(fileList) {
    const problems = [];
    for (const file of Array.from(fileList)) {
        if (savedPhotos.length + pendingPhotos.length >= MAX_PHOTOS) {
            problems.push(`Only ${MAX_PHOTOS} photos are allowed per ad.`);
            break;
        }
        if (!ALLOWED_PHOTO_TYPES.includes(file.type)) {
            problems.push(`${file.name}: only JPEG, PNG or WebP images are allowed.`);
        } else if (file.size > MAX_PHOTO_BYTES) {
            problems.push(`${file.name}: too large (max 5 MB).`);
        } else if (file.size === 0) {
            problems.push(`${file.name}: the file is empty.`);
        } else {
            pendingPhotos.push({ file, previewUrl: URL.createObjectURL(file) });
        }
    }
    renderPhotos();
    if (problems.length > 0) setPhotoHint(problems.join(" "));
}

async function deleteSavedPhoto(photo) {
    if (!window.confirm("Delete this photo?")) return;
    try {
        await apiRequest(`/cars/${editingId}/images/${photo.id}`, { method: "DELETE" });
        savedPhotos = savedPhotos.filter((p) => p.id !== photo.id);
        renderPhotos();
    } catch (error) {
        showSellError(error.message);
    }
}

async function makeCover(photo) {
    try {
        await apiRequest(`/cars/${editingId}/images/${photo.id}/cover`, { method: "POST" });
        savedPhotos = [photo, ...savedPhotos.filter((p) => p.id !== photo.id)];
        renderPhotos();
    } catch (error) {
        showSellError(error.message);
    }
}

function fieldValue(id) {
    return document.getElementById(id).value.trim();
}

function numberValue(id) {
    const value = fieldValue(id);
    return value === "" ? null : Number(value);
}

function collectPayload() {
    return {
        brand: fieldValue("brand"),
        model: fieldValue("model"),
        year: numberValue("year"),
        price: numberValue("price"),
        seller_phone: fieldValue("phone"),
        city: fieldValue("city"),
        mileage: numberValue("mileage"),
        fuel_type: fieldValue("fuel_type"),
        transmission: fieldValue("transmission"),
        condition: fieldValue("condition"),
        engine_cc: numberValue("engine_cc"),
        color: fieldValue("color") || null,
        description: fieldValue("description") || null,
    };
}

function fillForm(car) {
    const set = (id, value) => { document.getElementById(id).value = value === null || value === undefined ? "" : value; };
    set("brand", car.brand);
    set("model", car.model);
    set("year", car.year);
    set("price", car.price);
    set("phone", car.seller_phone);
    set("city", car.city);
    set("mileage", car.mileage);
    set("fuel_type", car.fuel_type);
    set("transmission", car.transmission);
    set("condition", car.condition);
    set("engine_cc", car.engine_cc);
    set("color", car.color);
    set("description", car.description);
}

function enterEditMode(carId) {
    editingId = carId;
    document.title = "Edit Ad - Car Marketplace";
    document.getElementById("sell-title").textContent = "Edit Your Ad";
    document.getElementById("sell-subtitle").textContent = "Update the details or manage the photos of your ad.";
    document.getElementById("sell-submit").textContent = "Save changes";
}

// Pending photos aik aik kar ke upload hoti hain. Jo fail hon unka naam + wajah wapas aata hay.
async function uploadPendingPhotos(carId) {
    const failures = [];
    for (const pending of [...pendingPhotos]) {
        try {
            const saved = await apiRequest(`/cars/${carId}/images`, {
                method: "POST",
                body: pending.file,
                rawBody: true,
                headers: { "Content-Type": pending.file.type },
            });
            savedPhotos.push(saved);
            URL.revokeObjectURL(pending.previewUrl);
            pendingPhotos = pendingPhotos.filter((p) => p !== pending);
        } catch (error) {
            failures.push(`${pending.file.name}: ${error.message}`);
        }
    }
    renderPhotos();
    return failures;
}

async function startEdit(carId, user) {
    try {
        const car = await apiRequest(`/cars/${encodeURIComponent(carId)}`);
        if (car.owner_id !== user.id) {
            alert("You can only edit your own ads.");
            window.location.replace("my-ads.html");
            return;
        }
        if (car.is_hidden) {
            alert("This ad was removed by the moderators and can no longer be edited.");
            window.location.replace("my-ads.html");
            return;
        }
        enterEditMode(car.id);
        fillForm(car);
        savedPhotos = car.images;
        renderPhotos();
    } catch (error) {
        alert(error.message || "Could not load this ad.");
        window.location.replace("my-ads.html");
    }
}

if (sellForm) {
    document.getElementById("year").max = new Date().getFullYear() + 1;

    document.getElementById("photos").addEventListener("change", (event) => {
        handleFilesSelected(event.target.files);
        event.target.value = "";      // wohi file dobara chunni ho to bhi change event aaye
    });

    sellForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        showSellError("");
        if (!sellForm.reportValidity()) return;

        const submitButton = document.getElementById("sell-submit");
        submitButton.disabled = true;
        try {
            const payload = collectPayload();
            const car = editingId
                ? await apiRequest(`/cars/${editingId}`, { method: "PATCH", body: payload })
                : await apiRequest("/cars", { method: "POST", body: payload });

            const failures = await uploadPendingPhotos(car.id);
            if (failures.length > 0) {
                // Ad save ho gayi: ab edit mode mai rehte hain taake failed photos dobara try ho saken (duplicate ad na bane)
                enterEditMode(car.id);
                window.history.replaceState(null, "", `sell.html?id=${encodeURIComponent(car.id)}`);
                showSellError(`Your ad was saved, but ${failures.length} photo(s) could not be uploaded: ${failures.join(" | ")}`);
                return;
            }
            window.location.href = `car.html?id=${encodeURIComponent(car.id)}`;
        } catch (error) {
            showSellError(error.message || "Could not publish the ad. Check the submitted details.");
        } finally {
            submitButton.disabled = false;
        }
    });

    onWheelDealReady((user) => {
        const id = new URLSearchParams(window.location.search).get("id");
        if (id) startEdit(id, user);
        else renderPhotos();
    });
}
