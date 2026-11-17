// ==========================================================================
// ADMIN PANEL
// Sab data server se aata hay aur sirf textContent / DOM APIs se dikhaya jata hay (HTML inject nahi hota).
// Asli security server par hay (/api/admin/* sirf admin ko); yeh page sirf uska interface hay.
// ==========================================================================
const API_BASE_URL = (window.location.protocol === "file:" || window.location.port === "5500" || window.location.port === "5501")
    ? "http://127.0.0.1:8000/api"
    : "/api";
const CSRF_HEADERS = { "X-Requested-With": "WheelDeal" };

const REASON_LABELS = {
    spam: "Spam / duplicate",
    fake_or_scam: "Fake or scam",
    wrong_info: "Wrong price/details",
    inappropriate: "Inappropriate",
    other: "Other",
};

const state = { tab: "reports", reportFilter: "open", adFilter: "all", adSearch: "", userSearch: "" };

// ---- chhote helpers --------------------------------------------------------

function el(tag, attrs = {}, ...children) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(attrs)) {
        if (key === "class") node.className = value;
        else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
        else node.setAttribute(key, value);
    }
    node.append(...children.filter((child) => child !== null && child !== undefined && child !== false));
    return node;
}

function extractErrorMessage(data, fallback) {
    if (data && typeof data.detail === "string") return data.detail;
    if (data && Array.isArray(data.detail) && data.detail.length > 0) {
        return data.detail.map((item) => String(item.msg || "").replace(/^Value error, /, "")).join(" | ");
    }
    return fallback;
}

async function api(path, options = {}) {
    const response = await fetch(`${API_BASE_URL}${path}`, {
        credentials: "include",
        cache: "no-store",
        ...options,
        headers: { "Content-Type": "application/json", ...CSRF_HEADERS, ...(options.headers || {}) },
    });
    if (response.status === 401) {
        window.location.replace("login.html");
        throw new Error("Please log in again.");
    }
    const data = await response.json().catch(() => null);
    if (!response.ok) throw new Error(extractErrorMessage(data, `Request failed (${response.status}).`));
    return data;
}

function showMessage(text, isError = false) {
    const box = document.getElementById("admin-msg");
    box.textContent = text;
    box.className = isError ? "is-error" : "is-ok";
}

function formatDate(iso) {
    const date = iso ? new Date(iso) : null;
    return date && !Number.isNaN(date.getTime()) ? date.toLocaleString() : "—";
}

function badge(text, kind = "gray") {
    return el("span", { class: `badge badge-${kind}` }, text);
}

function adSummary(car) {
    return [
        el("div", {}, el("strong", {}, `#${car.id} ${car.brand} ${car.model}`), ` (${car.year})`),
        el("div", { class: "muted" }, `PKR ${Number(car.price).toLocaleString()}`),
        el("div", {},
            badge(car.status, car.status === "sold" ? "blue" : car.status === "pending" ? "amber" : "green"),
            car.is_hidden ? badge("HIDDEN", "red") : null,
            car.is_deleted ? badge("DELETED BY OWNER", "gray") : null,
            car.open_reports > 0 ? badge(`${car.open_reports} open report(s)`, "amber") : null),
    ];
}

function sellerSummary(owner) {
    return [
        el("div", {}, `${owner.username} (#${owner.id})`),
        owner.is_banned ? badge("BANNED", "red") : null,
        owner.is_admin ? badge("ADMIN", "blue") : null,
    ];
}

function makeTable(headers, rows, emptyText = "Nothing here.") {
    if (rows.length === 0) return el("p", { class: "muted" }, emptyText);
    const head = el("tr", {}, ...headers.map((h) => el("th", { scope: "col" }, h)));
    const body = rows.map((cells) =>
        el("tr", {}, ...cells.map((cell) => el("td", {}, ...(Array.isArray(cell) ? cell : [cell])))));
    return el("div", { class: "table-wrap" }, el("table", {}, el("thead", {}, head), el("tbody", {}, ...body)));
}

function actionButton(label, onClick, kind = "") {
    return el("button", { type: "button", class: `abtn ${kind ? `abtn-${kind}` : ""}`.trim(), onclick: onClick }, label);
}

function selectControl(label, options, current, onChange) {
    return el("select", { "aria-label": label, onchange: (event) => onChange(event.target.value) },
        ...options.map(([value, text]) => el("option", value === current ? { value, selected: "" } : { value }, text)));
}

function searchControl(placeholder, current, onSearch) {
    const input = el("input", { type: "search", placeholder, value: current, maxlength: "80", "aria-label": placeholder });
    input.addEventListener("keydown", (event) => { if (event.key === "Enter") onSearch(input.value.trim()); });
    return [input, actionButton("Search", () => onSearch(input.value.trim()))];
}

// Admin action chalao: confirm / optional note ke baad POST, phir screen refresh
async function runAction(path, { confirmText = null, askNote = false } = {}) {
    if (confirmText && !window.confirm(confirmText)) return;
    let note = null;
    if (askNote) {
        note = window.prompt("Reason / note (optional, activity log mai save hoga):", "");
        if (note === null) return;               // Cancel
        note = note.trim().slice(0, 255) || null;
    }
    try {
        const data = await api(path, { method: "POST", body: JSON.stringify(note ? { note } : {}) });
        showMessage(data.msg);
    } catch (error) {
        showMessage(error.message, true);
    }
    await Promise.all([loadStats(), render()]);
}

// ---- Stats -----------------------------------------------------------------

async function loadStats() {
    try {
        const stats = await api("/admin/stats");
        const cards = [
            ["Users", stats.users, false],
            ["Banned users", stats.banned_users, false],
            ["Visible ads", stats.ads_visible, false],
            ["Hidden ads", stats.ads_hidden, false],
            ["Open reports", stats.open_reports, stats.open_reports > 0],
        ];
        document.getElementById("admin-stats").replaceChildren(
            ...cards.map(([label, value, alert]) =>
                el("div", { class: `stat${alert ? " alert" : ""}` }, el("strong", {}, String(value)), el("span", {}, label))));
    } catch (error) {
        showMessage(error.message, true);
    }
}

// ---- Tabs ------------------------------------------------------------------

async function renderReports() {
    const reports = await api(`/admin/reports?status=${encodeURIComponent(state.reportFilter)}`);
    const toolbar = el("div", { class: "toolbar" },
        el("label", {}, "Show: "),
        selectControl("Report status",
            [["open", "Open"], ["resolved", "Resolved"], ["dismissed", "Dismissed"], ["all", "All"]],
            state.reportFilter, (value) => { state.reportFilter = value; render(); }));

    const rows = reports.map((report) => {
        const actions = [];
        if (report.status === "open") {
            if (report.car.is_deleted) {
                // Owner ne ad delete kar di: hide/restore ki zaroorat nahi, sirf report ya seller par action
            } else if (report.car.is_hidden) {
                actions.push(actionButton("Restore ad", () => runAction(`/admin/cars/${report.car.id}/restore`, { askNote: true }), "ok"));
            } else {
                actions.push(actionButton("Hide ad", () => runAction(`/admin/cars/${report.car.id}/hide`, { askNote: true }), "danger"));
            }
            actions.push(actionButton("Dismiss report", () => runAction(`/admin/reports/${report.id}/dismiss`, { askNote: true })));
            if (!report.owner.is_banned && !report.owner.is_admin) {
                actions.push(actionButton("Ban seller", () => runAction(`/admin/users/${report.owner.id}/ban`, {
                    confirmText: `Ban ${report.owner.username}? They will be logged out and all their ads hidden.`,
                    askNote: true,
                }), "danger"));
            }
        }
        return [
            formatDate(report.created_at),
            adSummary(report.car),
            badge(REASON_LABELS[report.reason] || report.reason, "amber"),
            report.details || el("span", { class: "muted" }, "—"),
            report.reporter.username,
            sellerSummary(report.owner),
            report.status === "open" ? el("div", { class: "btn-row" }, ...actions) : badge(report.status, report.status === "resolved" ? "green" : "gray"),
        ];
    });

    return el("div", {}, toolbar,
        makeTable(["When", "Ad", "Reason", "Details", "Reported by", "Seller", "Actions"], rows,
            "No reports in this list. 🎉"));
}

async function renderAds() {
    const query = new URLSearchParams({ visibility: state.adFilter });
    if (state.adSearch) query.set("search", state.adSearch);
    const cars = await api(`/admin/cars?${query}`);

    const toolbar = el("div", { class: "toolbar" },
        selectControl("Visibility", [["all", "All ads"], ["visible", "Visible"], ["hidden", "Hidden"]],
            state.adFilter, (value) => { state.adFilter = value; render(); }),
        ...searchControl("Search brand or model", state.adSearch, (value) => { state.adSearch = value; render(); }));

    const rows = cars.map((car) => [
        adSummary(car),
        sellerSummary(car.owner),
        car.seller_phone,
        el("div", { class: "btn-row" },
            car.is_deleted
                ? el("span", { class: "muted" }, "Deleted by owner")
                : car.is_hidden
                ? actionButton("Restore", () => runAction(`/admin/cars/${car.id}/restore`, { askNote: true }), "ok")
                : actionButton("Hide", () => runAction(`/admin/cars/${car.id}/hide`, { askNote: true }), "danger")),
    ]);
    return el("div", {}, toolbar, makeTable(["Ad", "Seller", "Phone", "Actions"], rows, "No ads found."));
}

async function renderUsers() {
    const query = new URLSearchParams();
    if (state.userSearch) query.set("search", state.userSearch);
    const users = await api(`/admin/users?${query}`);

    const toolbar = el("div", { class: "toolbar" },
        ...searchControl("Search username or email", state.userSearch, (value) => { state.userSearch = value; render(); }));

    const rows = users.map((user) => {
        let action = el("span", { class: "muted" }, "—");
        if (!user.is_admin) {
            action = user.is_banned
                ? actionButton("Unban", () => runAction(`/admin/users/${user.id}/unban`, { askNote: true }), "ok")
                : actionButton("Ban", () => runAction(`/admin/users/${user.id}/ban`, {
                    confirmText: `Ban ${user.username}? They will be logged out and all their ads hidden.`,
                    askNote: true,
                }), "danger");
        }
        return [
            `#${user.id}`,
            user.username,
            user.email,
            user.email_verified ? badge("verified", "green") : badge("unverified", "amber"),
            String(user.ads),
            [user.is_admin ? badge("ADMIN", "blue") : null, user.is_banned ? badge("BANNED", "red") : null],
            action,
        ];
    });
    return el("div", {}, toolbar, makeTable(["ID", "Username", "Email", "Verified", "Ads", "Flags", "Actions"], rows, "No users found."));
}

async function renderLog() {
    const entries = await api("/admin/log");
    const rows = entries.map((entry) => [
        formatDate(entry.created_at),
        entry.admin,
        badge(entry.action, "gray"),
        `${entry.target_type} #${entry.target_id}`,
        entry.note || el("span", { class: "muted" }, "—"),
    ]);
    return makeTable(["When", "Admin", "Action", "Target", "Note"], rows, "No admin actions yet.");
}

async function render() {
    const panel = document.getElementById("tab-panel");
    document.querySelectorAll("[data-tab]").forEach((button) =>
        button.setAttribute("aria-selected", String(button.dataset.tab === state.tab)));
    const renderers = { reports: renderReports, ads: renderAds, users: renderUsers, log: renderLog };
    try {
        panel.replaceChildren(await renderers[state.tab]());
    } catch (error) {
        panel.replaceChildren(el("p", { class: "error" }, error.message));
    }
}

// ---- Start -----------------------------------------------------------------

async function boot() {
    let me = null;
    try {
        const response = await fetch(`${API_BASE_URL}/me`, { credentials: "include", cache: "no-store" });
        if (response.ok) me = await response.json();
    } catch (error) { /* server band */ }

    if (!me) { window.location.replace("login.html"); return; }
    if (!me.is_admin) { window.location.replace("index.html"); return; }

    document.querySelectorAll("[data-tab]").forEach((button) =>
        button.addEventListener("click", () => { state.tab = button.dataset.tab; render(); }));

    document.getElementById("adminLogout").addEventListener("click", async (event) => {
        event.preventDefault();
        try {
            await fetch(`${API_BASE_URL}/logout`, { method: "POST", credentials: "include", headers: CSRF_HEADERS });
        } catch (error) { /* ignore */ }
        window.location.href = "login.html";
    });

    await Promise.all([loadStats(), render()]);
}

document.addEventListener("DOMContentLoaded", boot);
