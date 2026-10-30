const state = {
    datasetId: null,
    page: 0,
    pageCount: 1,
    columns: [],
    numericColumns: [],
    identifierColumns: [],
    continuousColumns: [],
    discreteColumns: [],
    categoricalColumns: [],
    selectedRows: new Set(),
    selectedColumns: new Set(),
    actions: [],
};

const $ = (selector) => document.querySelector(selector);
const alertBox = $("#alert");

function trackAction(message, kind = "info") {
    state.actions.unshift({
        message,
        kind,
        time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    });
    renderActionLog();
}

function renderActionLog() {
    const list = $("#action-log-list");
    if (!list) return;
    list.replaceChildren();

    if (state.actions.length === 0) {
        const empty = document.createElement("span");
        empty.className = "action-log-empty";
        empty.textContent = "No actions yet";
        list.append(empty);
        return;
    }

    state.actions.slice(0, 30).forEach((entry) => {
        const item = document.createElement("div");
        item.className = `action-log-item ${entry.kind}`;
        const dot = document.createElement("span");
        dot.className = "action-log-dot";
        const copy = document.createElement("div");
        const message = document.createElement("span");
        message.className = "action-log-message";
        message.textContent = entry.message;
        const time = document.createElement("time");
        time.textContent = entry.time;
        copy.append(message, time);
        item.append(dot, copy);
        list.append(item);
    });
}

async function api(url, options = {}) {
    const response = await fetch(url, options);
    const contentType = response.headers.get("content-type") || "";
    if (!contentType.includes("application/json")) {
        await response.text();
        if (response.status === 404 && url.startsWith("/api/")) {
            throw new Error(
                "This Flask server does not recognize the API route. Stop it, restart with `python eda.py` from the project folder, then refresh this page."
            );
        }
        const hint = response.status >= 500
            ? " Check the Flask terminal for the underlying error."
            : " Make sure you opened the app through Flask.";
        throw new Error(`The server returned a page instead of JSON (HTTP ${response.status}).${hint}`);
    }

    let body;
    try {
        body = await response.json();
    } catch {
        throw new Error(`The server returned invalid JSON (HTTP ${response.status}). Check the Flask terminal.`);
    }
    if (!response.ok) {
        throw new Error(body.error || `Request failed (${response.status}).`);
    }
    return body;
}

function showMessage(message, kind = "error") {
    alertBox.textContent = message;
    alertBox.className = kind === "success" ? "alert success" : "alert";
    alertBox.hidden = false;
}

function clearMessage() {
    alertBox.hidden = true;
}

function setStep(activeStep) {
    const steps = ["upload", "clean", "visualize"];
    steps.forEach((name, index) => {
        const element = $(`#step-${name}`);
        element.classList.toggle("active", name === activeStep);
        element.classList.toggle("done", steps.indexOf(activeStep) > index);
    });
}

function formatNumber(value) {
    return new Intl.NumberFormat().format(value);
}

function formatStatistic(value) {
    if (value === null || value === undefined) return "—";
    if (typeof value === "number") {
        return new Intl.NumberFormat(undefined, { maximumFractionDigits: 4 }).format(value);
    }
    return String(value);
}

function renderStats(data) {
    const stats = [
        ["ROWS", formatNumber(data.row_count)],
        ["COLUMNS", formatNumber(data.column_count)],
        ["NUMERIC FEATURES", formatNumber(data.numeric_columns.length)],
        ["CATEGORICAL FEATURES", formatNumber((data.categorical_columns ?? []).length)],
    ];
    const container = $("#stats");
    container.replaceChildren();
    stats.forEach(([label, value]) => {
        const card = document.createElement("div");
        card.className = "stat-card";
        const title = document.createElement("span");
        title.className = "stat-label";
        title.textContent = label;
        const number = document.createElement("strong");
        number.className = "stat-value";
        number.textContent = value;
        card.append(title, number);
        container.append(card);
    });
}

function renderTable(data) {
    state.page = data.page;
    state.pageCount = data.page_count;
    state.columns = data.columns;
    state.numericColumns = data.numeric_columns;
    state.identifierColumns = data.identifier_columns ?? [];
    state.continuousColumns = data.continuous_columns ?? [];
    state.discreteColumns = data.discrete_columns ?? [];
    state.categoricalColumns = data.categorical_columns ?? [];
    const undoButton = $("#undo-last-action");
    if (undoButton) {
        const count = data.undo_count ?? 0;
        undoButton.disabled = count === 0;
        undoButton.textContent = count > 0 ? `↶ Undo last action (${count})` : "↶ Undo last action";
    }
    renderStats(data);
    renderFeatures(data.columns);
    $("#table-count").textContent = `${formatNumber(data.row_count)} rows`;

    const header = $("#table-head");
    header.replaceChildren();
    const headerRow = document.createElement("tr");
    const selectHeader = document.createElement("th");
    const selectPage = document.createElement("input");
    selectPage.type = "checkbox";
    selectPage.setAttribute("aria-label", "Select all rows on this page");
    const pageIds = data.rows.map((row) => row.id);
    selectPage.checked = pageIds.length > 0 && pageIds.every((id) => state.selectedRows.has(id));
    selectPage.addEventListener("change", () => {
        pageIds.forEach((id) => {
            if (selectPage.checked) state.selectedRows.add(id);
            else state.selectedRows.delete(id);
        });
        renderTable(data);
    });
    selectHeader.append(selectPage);
    headerRow.append(selectHeader);
    data.columns.forEach((column) => {
        const cell = document.createElement("th");
        cell.textContent = column;
        headerRow.append(cell);
    });
    header.append(headerRow);

    const body = $("#table-body");
    body.replaceChildren();
    data.rows.forEach((row) => {
        const tableRow = document.createElement("tr");
        if (state.selectedRows.has(row.id)) tableRow.classList.add("selected");
        const checkboxCell = document.createElement("td");
        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.checked = state.selectedRows.has(row.id);
        checkbox.setAttribute("aria-label", `Select row ${row.id + 1}`);
        checkbox.addEventListener("change", () => {
            if (checkbox.checked) state.selectedRows.add(row.id);
            else state.selectedRows.delete(row.id);
            renderTable(data);
        });
        checkboxCell.append(checkbox);
        tableRow.append(checkboxCell);
        row.values.forEach((value) => {
            const cell = document.createElement("td");
            cell.textContent = value === null ? "—" : String(value);
            cell.title = cell.textContent;
            tableRow.append(cell);
        });
        body.append(tableRow);
    });

    const statisticsBody = $("#column-statistics-body");
    statisticsBody.replaceChildren();
    (data.column_statistics ?? []).forEach((statistic) => {
        const row = document.createElement("tr");
        const values = [
            statistic.column,
            statistic.mean,
            statistic.median,
            statistic.mode,
            statistic.min,
            statistic.max,
            statistic.std,
            statistic.var,
            statistic.skew,
        ]

        values.forEach((value) => {
            const cell = document.createElement("td");
            cell.textContent = formatStatistic(value);
            cell.title = cell.textContent;
            row.append(cell);
        });
        statisticsBody.append(row);
    });

    $("#page-caption").textContent = `Page ${data.page + 1} of ${data.page_count}`;
    $("#previous-page").disabled = data.page === 0;
    $("#next-page").disabled = data.page >= data.page_count - 1;
    $("#selection-count").textContent = `${formatNumber(state.selectedRows.size)} selected`;
    $("#delete-rows").disabled = state.selectedRows.size === 0;
    $("#keep-rows").disabled = state.selectedRows.size === 0;
    updateChartOptions();
    renderAnalysis(data);
}

function renderAnalysis(data) {
    const container = $("#analysis-stats");
    container.replaceChildren();

    const stats = [
        { label: "DUPLICATE ROWS", value: data.duplicate_rows ?? 0, kind: data.duplicate_rows > 0 ? "warn" : "ok" },
        { label: "TOTAL MISSING VALUES", value: data.missing_count ?? 0, kind: data.missing_count > 0 ? "warn" : "ok" },
        { label: "NUMERIC COLS", value: (data.numeric_columns ?? []).length, kind: "ok" },
        { label: "INTEGER COLS", value: (data.integer_columns ?? []).length, kind: "ok" },
        { label: "IDENTIFIER COLS", value: (data.identifier_columns ?? []).length, kind: "ok" },
        { label: "CONTINUOUS COLS", value: (data.continuous_columns ?? []).length, kind: "ok" },
        { label: "DISCRETE COLS", value: (data.discrete_columns ?? []).length, kind: "ok" },
        { label: "CATEGORICAL COLS", value: (data.categorical_columns ?? []).length, kind: "ok" },
    ];

    stats.forEach(({ label, value, kind }) => {
        const card = document.createElement("div");
        card.className = "stat-card";
        const title = document.createElement("span");
        title.className = "stat-label";
        title.textContent = label;
        const number = document.createElement("strong");
        number.className = `stat-value ${kind === "warn" ? "high" : ""}`;
        number.textContent = formatNumber(value);
        card.append(title, number);
        container.append(card);
    });

    renderColumnTypes(data);
    renderDataQuality(data);
    renderMissingValueControls(data);
    renderOutlierControls(data);
}

function renderOutlierControls(data) {
    const columnSelect = $("#outlier-column");
    if (!columnSelect) return;

    const previous = columnSelect.value;
    const identifiers = new Set(data.identifier_columns ?? []);
    const usable = (data.numeric_columns ?? []).filter((column) => !identifiers.has(column));
    columnSelect.replaceChildren();

    if (usable.length === 0) {
        const option = document.createElement("option");
        option.value = "";
        option.textContent = "No numeric columns available";
        columnSelect.append(option);
    } else {
        usable.forEach((column) => {
            const option = document.createElement("option");
            option.value = column;
            option.textContent = column;
            columnSelect.append(option);
        });
        if (usable.includes(previous)) columnSelect.value = previous;
    }
    $("#detect-outliers").disabled = usable.length === 0;
}

function updateOutlierSettings() {
    const isZscore = $("#outlier-method").value === "zscore";
    $("#outlier-threshold-field").hidden = !isZscore;
    $("#outlier-multiplier-field").hidden = isZscore;
}

async function detectOutliers() {
    const column = $("#outlier-column").value;
    if (!column) return;

    const method = $("#outlier-method").value;
    clearMessage();
    try {
        const result = await api("/api/outliers", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                dataset_id: state.datasetId,
                column,
                method,
                threshold: $("#outlier-threshold").value,
                multiplier: $("#outlier-multiplier").value,
            }),
        });

        const container = $("#outlier-result");
        container.replaceChildren();
        const summary = document.createElement("div");
        summary.className = "outlier-summary";
        const setting = method === "zscore"
            ? `threshold ${formatNumber(result.settings.threshold)}`
            : `IQR multiplier ${formatNumber(result.settings.multiplier)}`;
        summary.innerHTML = `<strong>${formatNumber(result.outlier_count)}</strong> outlier${result.outlier_count === 1 ? "" : "s"} found in <strong>${result.column}</strong> using ${method === "zscore" ? "Z-score" : "IQR"} (${setting}).`;
        container.append(summary);

        if (result.outlier_count > 0) {
            const list = document.createElement("div");
            list.className = "outlier-list";
            result.outliers.forEach((outlier) => {
                const item = document.createElement("span");
                item.className = "outlier-chip";
                item.textContent = `Row ${outlier.row_number ?? outlier.row_id}: ${formatStatistic(outlier.value)}`;
                list.append(item);
            });
            container.append(list);
            if (result.truncated) {
                const note = document.createElement("span");
                note.className = "outlier-empty";
                note.textContent = "Showing the first 100 outliers.";
                container.append(note);
            }
        } else {
            const empty = document.createElement("span");
            empty.className = "outlier-empty";
            empty.textContent = "No outliers detected with the current settings.";
            container.append(empty);
        }
        trackAction(`Detected ${result.outlier_count} outlier${result.outlier_count === 1 ? "" : "s"} in ${column} using ${method === "zscore" ? "Z-score" : "IQR"}`, "info");
    } catch (error) {
        showMessage(error.message);
    }
}

function renderMissingValueControls(data) {
    const columnSelect = $("#missing-column");
    const actionSelect = $("#missing-action");
    if (!columnSelect || !actionSelect) return;

    const previousColumn = columnSelect.value;
    const missing = data.missing_per_column ?? {};
    const columns = Object.keys(missing);
    columnSelect.replaceChildren();

    if (columns.length === 0) {
        const option = document.createElement("option");
        option.textContent = "No missing values";
        option.value = "";
        columnSelect.append(option);
    } else {
        columns.forEach((column) => {
            const option = document.createElement("option");
            option.value = column;
            option.textContent = `${column} (${formatNumber(missing[column])} missing)`;
            columnSelect.append(option);
        });
        if (columns.includes(previousColumn)) columnSelect.value = previousColumn;
    }

    $("#apply-missing-value").disabled = columns.length === 0;
    updateMissingActions();
}

function updateMissingActions() {
    const column = $("#missing-column").value;
    const actionSelect = $("#missing-action");
    const previousAction = actionSelect.value;
    const isNumeric = state.numericColumns.includes(column);
    actionSelect.replaceChildren();

    const actions = isNumeric
        ? [["mean", "Mean"], ["median", "Median"], ["mode", "Mode"], ["constant", "Constant"], ["remove_rows", "Remove rows"]]
        : [["mode", "Mode"], ["constant", "Constant"], ["remove_rows", "Remove rows"]];

    actions.forEach(([value, label]) => {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = label;
        actionSelect.append(option);
    });
    if (actions.some(([value]) => value === previousAction)) actionSelect.value = previousAction;
    updateMissingConstantField();
}

function updateMissingConstantField() {
    const constantField = $("#missing-constant-field");
    constantField.hidden = $("#missing-action").value !== "constant";
}

async function applyMissingValueAction() {
    if (!state.datasetId) return;
    const column = $("#missing-column").value;
    const action = $("#missing-action").value;
    if (!column) return;

    clearMessage();
    try {
        const data = await api("/api/missing-values", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                dataset_id: state.datasetId,
                column,
                action,
                constant: $("#missing-constant").value,
            }),
        });
        $("#missing-constant").value = "";
        renderTable(data);
        const description = action === "remove_rows"
            ? `Removed rows with missing values in ${column}`
            : action === "constant"
                ? `Filled missing values in ${column} with constant value`
                : `Filled missing values in ${column} using ${action}`;
        trackAction(description, "success");
        showMessage(data.message || "Missing values handled.", "success");
    } catch (error) {
        showMessage(error.message);
    }
}

function renderColumnTypes(data) {
    const numericList = $("#numeric-columns-list");
    const categoricalList = $("#categorical-columns-list");
    numericList.replaceChildren();
    categoricalList.replaceChildren();

    const continuous = (data.continuous_columns ?? []).map(name => ({
        name, type: "continuous",
    }));
    const discrete = (data.discrete_columns ?? []).map(name => ({
        name, type: "discrete",
    }));
    const identifier = (data.identifier_columns ?? []).map(name => ({
        name, type: "identifier",
    }));

    function renderGroup(list, title, items, emptyText, chipType) {
        const section = document.createElement("div");
        section.className = "column-type-group";

        const heading = document.createElement("div");
        heading.className = "column-type-heading";
        heading.textContent = title;
        section.append(heading);

        const chips = document.createElement("div");
        chips.className = "column-chips";

        if (items.length === 0) {
            const empty = document.createElement("span");
            empty.className = "column-chip " + chipType;
            empty.textContent = emptyText;
            chips.append(empty);
        } else {
            items.forEach(({ name, type }) => {
                const chip = document.createElement("span");
                chip.className = `column-chip ${type}`;
                chip.title = name;
                const nameSpan = document.createElement("span");
                nameSpan.className = "chip-name";
                nameSpan.textContent = name;
                chip.append(nameSpan);
                chips.append(chip);
            });
        }

        section.append(chips);
        list.append(section);
    }

    renderGroup(numericList, "Continuous (measurements, decimals, time)", continuous,
        "No continuous columns detected.", "continuous");
    renderGroup(numericList, "Discrete (counts, quantities, headcounts)", discrete,
        "No discrete columns detected.", "discrete");
    renderGroup(numericList, "Identifier-like (IDs, zip/postal codes)", identifier,
        "No identifier-like columns detected.", "identifier");

    const categorical = (data.categorical_columns ?? []).map(name => ({
        name, type: "categorical",
    }));
    renderGroup(categoricalList, "Categorical (text, labels, categories)", categorical,
        "No categorical columns detected.", "categorical");

    const allEmpty = numericList.children.length === 0 && categoricalList.children.length === 0;
    if (allEmpty) {
        const empty = document.createElement("span");
        empty.className = "column-chip numeric";
        empty.textContent = "No columns detected.";
        numericList.append(empty);
    }
}

function renderDataQuality(data) {
    const list = $("#data-quality-list");
    list.replaceChildren();

    const items = [];

    if ((data.duplicate_rows ?? 0) > 0) {
        items.push({
            label: "Duplicate rows",
            value: formatNumber(data.duplicate_rows),
            kind: "high",
            badge: "dup",
            badgeText: `${formatNumber(data.duplicate_rows)} duplicate rows`,
        });
    }

    const missing = data.missing_per_column ?? {};
    Object.entries(missing).forEach(([column, count]) => {
        items.push({
            label: column,
            value: formatNumber(count),
            kind: "warn",
            badge: "missing",
            badgeText: `${formatNumber(count)} missing`,
        });
    });

    if (items.length === 0) {
        const item = document.createElement("div");
        item.className = "quality-item";
        item.style.justifyContent = "center";
        item.style.gap = "12px";
        item.innerHTML = '<span class="label">No issues detected</span><span class="value ok">Clean</span>';
        list.append(item);
        return;
    }

    items.forEach(({ label, badge, badgeText }) => {
        const item = document.createElement("div");
        item.className = "quality-item";
        item.style.justifyContent = "center";
        item.style.gap = "0";

        const chip = document.createElement("span");
        chip.className = `column-chip ${badge}`;

        const nameSpan = document.createElement("span");
        nameSpan.className = "chip-name";
        nameSpan.textContent = label;

        const countSpan = document.createElement("span");
        countSpan.className = "chip-count";
        countSpan.textContent = badgeText;

        chip.append(nameSpan, countSpan);
        item.append(chip);
        list.append(item);
    });
}

function renderFeatures(columns) {
    const list = $("#feature-list");
    list.replaceChildren();
    columns.forEach((column) => {
        const label = document.createElement("label");
        label.className = "feature-option";
        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.checked = state.selectedColumns.has(column);
        checkbox.addEventListener("change", () => {
            if (checkbox.checked) state.selectedColumns.add(column);
            else state.selectedColumns.delete(column);
            updateColumnActions();
        });
        const name = document.createElement("span");
        name.textContent = column;
        name.title = column;
        label.append(checkbox, name);
        list.append(label);
    });
    updateColumnActions();
}

function updateColumnActions() {
    const count = state.selectedColumns.size;
    $("#column-selection-count").textContent = `${formatNumber(count)} selected`;
    $("#remove-columns").disabled = count === 0;
    $("#keep-columns").disabled = count === 0;
}

async function loadPage(page) {
    const data = await api(`/api/data?dataset_id=${encodeURIComponent(state.datasetId)}&page=${page}`);
    renderTable(data);
}

function updateChartOptions() {
    const primary = $("#primary-column");
    const secondary = $("#secondary-column");
    const values = $("#chart-type").value === "count"
        ? state.columns
        : (state.numericColumns.length ? state.numericColumns : state.columns);
    [primary, secondary].forEach((select) => {
        const previous = select.value;
        select.replaceChildren();
        values.forEach((column) => {
            const option = document.createElement("option");
            option.value = column;
            option.textContent = column;
            select.append(option);
        });
        if (values.includes(previous)) select.value = previous;
    });
    if (secondary.options.length > 1 && secondary.value === primary.value) {
        secondary.selectedIndex = 1;
    }
}

function updateChartControls() {
    const type = $("#chart-type").value;
    $("#field-primary").hidden = type === "heatmap" || type === "box_all";
    $("#field-secondary").hidden = type !== "scatter";
    $("#primary-label").textContent = type === "scatter" ? "X AXIS" : "COLUMN";
    updateChartOptions();
}

async function uploadFile(file) {
    if (!file) return;
    clearMessage();
    const formData = new FormData();
    formData.append("file", file);
    try {
        const data = await api("/api/upload", { method: "POST", body: formData });
        state.datasetId = data.dataset_id;
        state.selectedRows.clear();
        state.selectedColumns.clear();
        state.actions = [];
        $("#data-panel").hidden = false;
        $("#analysis-panel").hidden = false;
        $("#chart-panel").hidden = false;
        renderTable(data);
        updateChartControls();
        setStep("clean");
        $("#chart-result").innerHTML = '<div class="chart-empty"><div class="chart-empty-icon" aria-hidden="true">⌁</div><strong>Your next insight starts here</strong><span>Pick a chart and create a visualization.</span></div>';
        trackAction(`Uploaded ${file.name} — ${formatNumber(data.row_count)} rows, ${formatNumber(data.column_count)} columns`, "info");
        showMessage(`Loaded ${formatNumber(data.row_count)} rows and ${formatNumber(data.column_count)} columns.`, "success");
    } catch (error) {
        showMessage(error.message);
    }
}

async function downloadModifiedCSV() {
    if (!state.datasetId) return;
    clearMessage();
    try {
        const response = await fetch(`/api/download/${encodeURIComponent(state.datasetId)}`);
        if (!response.ok) {
            const body = await response.json().catch(() => ({}));
            throw new Error(body.error || `Download failed (${response.status}).`);
        }
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const disposition = response.headers.get("content-disposition") || "";
        const match = disposition.match(/filename="?([^";]+)"?/);
        const a = document.createElement("a");
        a.href = url;
        a.download = match ? match[1] : "modified.csv";
        document.body.append(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
        trackAction("Downloaded the modified CSV", "info");
        showMessage("Modified CSV downloaded.", "success");
    } catch (error) {
        showMessage(error.message);
    }
}

async function changeRows(action) {
    if (!state.selectedRows.size) return;
    const ids = [...state.selectedRows];
    const prompt = action === "keep"
        ? `Keep these ${ids.length} selected rows and remove every other row from the working dataset?`
        : `Delete these ${ids.length} selected rows from the working dataset?`;
    if (!window.confirm(prompt)) return;

    clearMessage();
    try {
        const data = await api("/api/rows", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ dataset_id: state.datasetId, action, row_ids: ids }),
        });
        state.selectedRows.clear();
        renderTable(data);
        trackAction(action === "keep" ? `Kept ${ids.length} selected row${ids.length === 1 ? "" : "s"}` : `Deleted ${ids.length} selected row${ids.length === 1 ? "" : "s"}`, "success");
        showMessage(action === "keep" ? "Kept the selected rows." : "Deleted the selected rows.", "success");
    } catch (error) {
        showMessage(error.message);
    }
}

async function changeColumns(action) {
    if (!state.selectedColumns.size) return;
    const columns = [...state.selectedColumns];
    const question = action === "keep"
        ? `Keep only these ${columns.length} selected columns?`
        : `Remove these ${columns.length} selected columns?`;
    if (!window.confirm(question)) return;

    clearMessage();
    try {
        const data = await api("/api/columns", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ dataset_id: state.datasetId, action, columns }),
        });
        state.selectedColumns.clear();
        renderTable(data);
        trackAction(action === "keep" ? `Kept columns: ${columns.join(", ")}` : `Deleted columns: ${columns.join(", ")}`, "success");
        showMessage(action === "keep" ? "Kept the selected columns." : "Removed the selected columns.", "success");
    } catch (error) {
        showMessage(error.message);
    }
}

async function createChart() {
    clearMessage();
    const type = $("#chart-type").value;
    const payload = { dataset_id: state.datasetId, type };
    if (["histogram", "violin", "count", "box"].includes(type)) {
        payload.column = $("#primary-column").value;
    }
    if (type === "scatter") {
        payload.x = $("#primary-column").value;
        payload.y = $("#secondary-column").value;
    }
    const button = $("#plot-button");
    button.disabled = true;
    button.textContent = "Working…";
    try {
        const result = await api("/api/plot", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        const container = $("#chart-result");
        container.replaceChildren();
        const image = document.createElement("img");
        image.src = result.image;
        image.alt = `${type} chart`;
        container.append(image);
        if (result.note) {
            const note = document.createElement("p");
            note.className = "chart-note";
            note.textContent = result.note;
            container.append(note);
        }
        setStep("visualize");
        trackAction(`Created ${type} chart${payload.column ? ` for ${payload.column}` : ""}${payload.x && payload.y ? ` (${payload.x} vs ${payload.y})` : ""}`, "info");
    } catch (error) {
        showMessage(error.message);
    } finally {
        button.disabled = false;
        button.innerHTML = '<span aria-hidden="true">✳</span> Create chart';
    }
}

$("#upload-form").addEventListener("submit", (event) => event.preventDefault());
$("#file-input").addEventListener("change", (event) => uploadFile(event.target.files[0]));
$("#replace-dataset").addEventListener("click", () => $("#file-input").click());
$("#download-csv").addEventListener("click", downloadModifiedCSV);
async function undoLastAction() {
    if (!state.datasetId) return;
    clearMessage();
    try {
        const data = await api("/api/undo", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ dataset_id: state.datasetId }),
        });
        state.selectedRows.clear();
        state.selectedColumns.clear();
        renderTable(data);
        trackAction(data.undone_action ? `Undid: ${data.undone_action}` : "Undid last action", "info");
        showMessage(data.message || "Undid the last action.", "success");
    } catch (error) {
        showMessage(error.message);
    }
}

$("#clear-action-log").addEventListener("click", () => {
    state.actions = [];
    renderActionLog();
});
$("#undo-last-action").addEventListener("click", undoLastAction);
$("#previous-page").addEventListener("click", async () => {
    try { await loadPage(state.page - 1); } catch (error) { showMessage(error.message); }
});
$("#next-page").addEventListener("click", async () => {
    try { await loadPage(state.page + 1); } catch (error) { showMessage(error.message); }
});
$("#delete-rows").addEventListener("click", () => changeRows("delete"));
$("#keep-rows").addEventListener("click", () => changeRows("keep"));
$("#remove-columns").addEventListener("click", () => changeColumns("delete"));
$("#keep-columns").addEventListener("click", () => changeColumns("keep"));
$("#missing-column").addEventListener("change", updateMissingActions);
$("#missing-action").addEventListener("change", updateMissingConstantField);
$("#apply-missing-value").addEventListener("click", applyMissingValueAction);
$("#outlier-method").addEventListener("change", updateOutlierSettings);
$("#detect-outliers").addEventListener("click", detectOutliers);
$("#chart-type").addEventListener("change", updateChartControls);
$("#plot-button").addEventListener("click", createChart);
