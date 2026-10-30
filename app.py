import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib
import matplotlib.pyplot as plt
import math
import uuid
import io
import base64
from scipy import stats
from flask import Flask, render_template, jsonify, request, send_file

#create chart images
#without openning a window
matplotlib.use("Agg")

app = Flask(__name__)      
app.config["MAX_CONTENT_LENGTH"] = 16*1024*1024 #upload lim:16MB

rows_per_page = 20
datasets = {}
undo_stacks = {}
original_files = {}

IDENTIFIER_KEYWORDS = (
    "zip", "postal", "postcode", "pin code", "pincode",
    "id", "identifier", "code", "no.", "number", "key",
)

def error_response(message,status = 404):
    return jsonify({"error":message}),status

def find_dataset(dataset_id):
    if not isinstance(dataset_id,str):
        return None
    else:
        return datasets.get(dataset_id)

def make_json_value(value):
    if pd.isna(value):
        return None
    if isinstance(value,np.generic):
        value = value.item()
    if isinstance(value,float) and not math.isfinite(value):
        return None
    if isinstance(value,(pd.Timestamp,pd.Timedelta)):
        return value.isoformat() 
    return value


def looks_like_identifier(name, series):
    """Heuristic: a numeric-looking column that probably holds a categorical
    identifier (zip/postal code, ID, code, key) rather than a real measurement."""
    lower = str(name).lower()
    if any(keyword in lower for keyword in IDENTIFIER_KEYWORDS):
        return True
    non_null = series.dropna()
    if len(non_null) == 0:
        return False
    if (
        len(non_null) >= 10
        and pd.api.types.is_integer_dtype(series)
        and non_null.nunique() == len(non_null)
    ):
        return True
    return False


def detect_identifier_columns(frame):
    numeric = frame.select_dtypes(include="number")
    return [str(column) for column in numeric.columns
            if looks_like_identifier(column, numeric[column])]


def classify_numeric_column(series):
    """Classify a numeric column as 'continuous', 'discrete', or None.

    Continuous: measurements with decimals, time, high-cardinality floats.
    Discrete: integer counts (headcounts, quantities), low-cardinality numerics.
    """
    non_null = series.dropna()
    if len(non_null) == 0:
        return None

    if pd.api.types.is_float_dtype(series):
        sample = non_null.head(min(1000, len(non_null)))
        has_decimals = any(float(value) % 1 != 0 for value in sample)
        if has_decimals:
            return "continuous"
        # Whole numbers stored as float: high cardinality -> measurement
        if len(non_null) >= 10 and non_null.nunique() / len(non_null) > 0.5:
            return "continuous"
        return "discrete"

    if pd.api.types.is_integer_dtype(series):
        return "discrete"

    return None


def detect_continuous_columns(frame):
    numeric = frame.select_dtypes(include="number")
    return [str(column) for column in numeric.columns
            if classify_numeric_column(numeric[column]) == "continuous"]


def detect_discrete_columns(frame):
    numeric = frame.select_dtypes(include="number")
    return [str(column) for column in numeric.columns
            if classify_numeric_column(numeric[column]) == "discrete"]


def detect_categorical_columns(frame):
    numeric = frame.select_dtypes(include="number")
    return [str(column) for column in frame.columns
            if column not in numeric.columns]

def detect_outliers_zscore(series, threshold=3.0):
    values = pd.to_numeric(series, errors="coerce")
    finite = values[np.isfinite(values)] if hasattr(values, "__len__") else values
    if len(finite) == 0:
        return pd.Series(False, index=series.index)

    std = finite.std(ddof=0)
    if not math.isfinite(float(std)) or float(std) == 0:
        return pd.Series(False, index=series.index)

    z_scores = np.abs(stats.zscore(finite.to_numpy(dtype=float), nan_policy="omit", ddof=0))
    mask = pd.Series(False, index=series.index)
    mask.loc[finite.index] = z_scores > threshold
    return mask


def detect_outliers_iqr(series, multiplier=1.5):
    values = pd.to_numeric(series, errors="coerce")
    finite = values[np.isfinite(values)]
    if len(finite) == 0:
        return pd.Series(False, index=series.index)

    q1 = finite.quantile(0.25)
    q3 = finite.quantile(0.75)
    iqr = q3 - q1
    lower_bound = q1 - multiplier * iqr
    upper_bound = q3 + multiplier * iqr
    return (values < lower_bound) | (values > upper_bound)


def make_dataset_response(dataset_id,frame,page=0):
    page_count = max(1,(len(frame) + rows_per_page-1) // rows_per_page)
    page = min(max(page,0),page_count -1)
    first_row = page * rows_per_page
    page_of_rows = frame.iloc[first_row : first_row + rows_per_page]

    rows = []
    for row_id,row in page_of_rows.iterrows():
        rows.append({
            "id" : int(row_id),
            "values": [make_json_value(value) for value in row.tolist()],
        })

    numeric_columns = frame.select_dtypes(include = "number").columns.tolist()
    integer_columns = frame.select_dtypes(include = "integer").columns.tolist()
    identifier_columns = detect_identifier_columns(frame)
    continuous_columns = detect_continuous_columns(frame)
    discrete_columns = detect_discrete_columns(frame)
    categorical_columns = detect_categorical_columns(frame)
    missing_per_column = {
        str(column): int(count)
        for column, count in frame.isna().sum().items()
        if count > 0
    }
    duplicate_rows = int(frame.duplicated().sum())
    return {
        "dataset_id" : dataset_id,
        "columns" : [str(column) for column in frame.columns],
        "column_statistics": data_describe(frame),
        "numeric_columns": [str(column) for column in numeric_columns],
        "integer_columns": [str(column) for column in integer_columns],
        "identifier_columns": [str(column) for column in identifier_columns],
        "continuous_columns": [str(column) for column in continuous_columns],
        "discrete_columns": [str(column) for column in discrete_columns],
        "categorical_columns": [str(column) for column in categorical_columns],
        "rows": rows,
        "row_count" : len(frame),
        "column_count":len(frame.columns),
        "missing_count":int(frame.isna().sum().sum()),
        "missing_per_column": missing_per_column,
        "duplicate_rows": duplicate_rows,
        "page":page,
        "page_count":page_count,
        "page_size": rows_per_page,
        "undo_available": bool(undo_stacks.get(dataset_id)),
        "undo_count": len(undo_stacks.get(dataset_id, [])),
    }

def data_describe(frame):
    numeric_columns = set(frame.select_dtypes(include="number").columns)
    identifier_columns = set(detect_identifier_columns(frame))
    continuous_columns = set(detect_continuous_columns(frame))
    discrete_columns = set(detect_discrete_columns(frame))
    categorical_columns = set(detect_categorical_columns(frame))
    statistics = []
    for column in frame.columns:
        values = frame[column]
        is_numeric = column in numeric_columns
        is_identifier = column in identifier_columns
        is_continuous = column in continuous_columns
        is_discrete = column in discrete_columns
        is_categorical = column in categorical_columns
        modes = values.mode(dropna=True).tolist()
        statistics.append({
            "column": str(column),
            "is_identifier": is_identifier,
            "is_continuous": is_continuous,
            "is_discrete": is_discrete,
            "is_categorical": is_categorical,
            "mean": make_json_value(values.mean()) if is_numeric else None,
            "median": make_json_value(values.median()) if is_numeric else None,
            "mode": [make_json_value(value) for value in modes],
            "min":[make_json_value(values.min() if is_numeric else None)],
            "max":[make_json_value(values.max() if is_numeric else None)],
            "std": [make_json_value(values.std() if is_numeric else None)],
            "var": [make_json_value(values.var() if is_numeric else None)],
            "skew": [make_json_value(values.skew() if is_numeric else None)],
        })
    return statistics


def push_undo_action(dataset_id, description, before_frame):
    if dataset_id not in undo_stacks:
        undo_stacks[dataset_id] = []
    undo_stacks[dataset_id].append({
        "description": description,
        "before": before_frame.copy(),
    })


@app.post("/api/missing-values")
def handling_missing_values():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error_response("A JSON missing-value request is required.")

    dataset_id = data.get("dataset_id")
    frame = find_dataset(dataset_id)
    if frame is None:
        return error_response("Dataset not found. Upload it again to continue.", 404)

    column = data.get("column")
    action = data.get("action")
    if not isinstance(column, str) or column not in frame.columns:
        return error_response("Choose a valid column.")
    if frame[column].isna().sum() == 0:
        return error_response("This column has no missing values to handle.")

    is_numeric = pd.api.types.is_numeric_dtype(frame[column])
    valid_actions = ("mean", "median", "mode", "constant", "remove_rows") if is_numeric else ("mode", "constant", "remove_rows")
    if action not in valid_actions:
        return error_response("Choose a valid action for this column type.")

    updated_frame = frame.copy()
    missing_count = int(updated_frame[column].isna().sum())

    if action == "remove_rows":
        updated_frame = updated_frame.loc[updated_frame[column].notna()].copy()
    else:
        if action == "mean":
            replacement = pd.to_numeric(updated_frame[column], errors="coerce").mean()
        elif action == "median":
            replacement = pd.to_numeric(updated_frame[column], errors="coerce").median()
        elif action == "mode":
            modes = updated_frame[column].mode(dropna=True)
            if modes.empty:
                return error_response("The column has no non-missing value to use as its mode.")
            replacement = modes.iloc[0]
        else:
            constant = data.get("constant")
            if constant is None or (isinstance(constant, str) and constant.strip() == ""):
                return error_response("Enter a constant value.")
            if is_numeric:
                try:
                    replacement = float(constant)
                    if not math.isfinite(replacement):
                        raise ValueError
                except (TypeError, ValueError):
                    return error_response("The constant must be a valid number for this numeric column.")
            else:
                replacement = str(constant)

        if pd.isna(replacement):
            return error_response("There is no valid replacement value for this column.")
        updated_frame[column] = updated_frame[column].fillna(replacement)

    if action == "remove_rows":
        description = f"Removed rows with missing values in {column}"
    elif action == "constant":
        description = f"Filled missing values in {column} with a constant"
    else:
        description = f"Filled missing values in {column} using {action}"
    push_undo_action(dataset_id, description, frame)
    datasets[dataset_id] = updated_frame
    response = make_dataset_response(dataset_id, updated_frame)
    response["message"] = f"Handled {missing_count} missing value{'s' if missing_count != 1 else ''} in {column}."
    return jsonify(response)

# @app.post("/api.duplicate-values")
# def handling_duplicate_values():
#     data = request.get_json(silent = True)

#     if not isinstance(data,dict):
#         return error_response("A JSON duplicate value request is required")

#     dataset_id = data.get("dataset_id")
#     frame = find_dataset(dataset_id)

#     if frame is None:
#         return error_response("Dataset not found, upload it again and continue",404)

#     column = data.get("column")
#     action = data.get("action")
#     updated_frame = frame.copy()
#     duplicate_counts = int(updated_frame[column].duplicated().sum())

#     if action == "keep_duplicates":
#         #keep first occurence
#     else:
#         #ewmove duplicate


#     datasets[dataset_id] = updated_frame
#     response = make_dataset_response(dataset_id, updated_frame)
#     response["message"] = f"Handled {missing_count} missing value{'s' if missing_count != 1 else ''} in {column}."
#     return jsonify(response)
    

@app.get("/")
def home():
    return render_template("index.html")

@app.post("/api/upload")
def upload_csv():
    uploaded_file = request.files.get("file")
    if uploaded_file is None or not uploaded_file.filename:
        return error_response("Choose a CSV file to upload.")
    if not uploaded_file.filename.lower().endswith(".csv"):
        return error_response("The uploaded file must have a .csv extension.")

    try:
        raw = uploaded_file.stream.read()
        encodings = ["utf-8","utf-8-sig","latin-1","cp1252"]

        for encoding in encodings:
            try:
                frame = pd.read_csv(io.BytesIO(raw), encoding = encoding)
            except UnicodeDecodeError:
                continue
    except (pd.errors.ParseError, pd.errors.EmptyDataError,UnicodeDecodeError,ValueError) as error:
        return error_response(f"could not read this file:{error}")

    dataset_id = uuid.uuid4().hex
    datasets[dataset_id] = frame
    undo_stacks[dataset_id] = []
    original_files[dataset_id] = (uploaded_file.filename, raw)
    return jsonify(make_dataset_response(dataset_id,frame))

@app.get("/api/download/<dataset_id>")
def download_csv(dataset_id):
    if dataset_id not in datasets:
        return error_response("Dataset not found. Upload it again to continue.", 404)
    frame = datasets[dataset_id]
    csv_bytes = frame.to_csv(index=False).encode("utf-8")
    filename = original_files[dataset_id][0] if dataset_id in original_files else "modified.csv"
    return send_file(
        io.BytesIO(csv_bytes),
        mimetype="text/csv",
        as_attachment=True,
        download_name=filename,
    )


@app.get("/api/data")
def get_data():
    dataset_id = request.args.get("dataset_id")
    frame = find_dataset(dataset_id)

    if frame is None:
        return error_response("File not found,try upload that again.",404)

    try:
        page = int(request.args.get("page","0"))
    except ValueError:
        return error_response("Page must be a whole number")
    
    return jsonify(make_dataset_response(dataset_id,frame,page))

@app.post("/api/columns")
def edit_columns():
    data = request.get_json()
    if not isinstance(data,dict):
        return error_response("it is not json,need json")

    dataset_id = data.get("dataset_id")
    frame = find_dataset(dataset_id)
    if frame is None:
            return error_response("File not found,try upload that again.",404)

    action = data.get("action")
    columns = data.get("columns")

    if action not in ("keep", "delete"):
        return error_response("Choose either keep or delete as the column action.")
    if not isinstance(columns, list) or not columns:
        return error_response("Select at least one column first.")
    if any(not isinstance(column, str) for column in columns):
        return error_response("Selected column names are invalid.")

    selected_columns = set(columns).intersection(frame.columns)

    if action == "keep":
        remaining_columns = []
        for column in frame.columns:
            if column in selected_columns:
                remaining_columns.append(column)

    else:
        remaining_columns = []
        for column in frame.columns:
            if column not in selected_columns:
                remaining_columns.append(column)

    if not remaining_columns:
        return error_response("This action would remove every column. Keep at least one feature.")

    updated_frame = frame[remaining_columns]
    affected = sorted(selected_columns, key=str)
    description = (
        f"Kept columns: {', '.join(affected)}"
        if action == "keep"
        else f"Deleted columns: {', '.join(affected)}"
    )
    push_undo_action(dataset_id, description, frame)
    datasets[dataset_id] = updated_frame
    return jsonify(make_dataset_response(dataset_id, updated_frame))


@app.post("/api/rows")
def edit_rows():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error_response("A JSON row request is required.")

    dataset_id = data.get("dataset_id")
    frame = find_dataset(dataset_id)
    if frame is None:
        return error_response("Dataset not found. Upload it again to continue.", 404)

    action = data.get("action")
    row_ids = data.get("row_ids")
    if action not in ("keep", "delete"):
        return error_response("Choose either keep or delete as the row action.")
    if not isinstance(row_ids, list) or not row_ids:
        return error_response("Select at least one row first.")

    try:
        selected_ids = {int(row_id) for row_id in row_ids}
    except (TypeError, ValueError):
        return error_response("Selected row IDs are invalid.")

    selected = frame.index.isin(selected_ids)
    if not selected.any():
        return error_response("The selected rows are not in this dataset.")

    if action == "keep":
        updated_frame = frame.loc[selected].copy()
        description = f"Kept {selected.sum()} selected row{'s' if selected.sum() != 1 else ''}"
    else:
        updated_frame = frame.loc[~selected].copy()
        description = f"Deleted {selected.sum()} selected row{'s' if selected.sum() != 1 else ''}"

    if updated_frame.empty:
        return error_response("This action would remove every row.")

    push_undo_action(dataset_id, description, frame)
    datasets[dataset_id] = updated_frame
    return jsonify(make_dataset_response(dataset_id, updated_frame))


@app.post("/api/outliers")
def detect_outliers():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error_response("A JSON outlier request is required.")

    dataset_id = data.get("dataset_id")
    frame = find_dataset(dataset_id)
    if frame is None:
        return error_response("Dataset not found. Upload it again to continue.", 404)

    column = data.get("column")
    method = data.get("method", "zscore")
    if not isinstance(column, str) or column not in frame.columns:
        return error_response("Choose a valid column.")
    if not pd.api.types.is_numeric_dtype(frame[column]):
        return error_response("Outlier detection is only available for numeric columns.")
    if method not in ("zscore", "iqr"):
        return error_response("Choose either zscore or iqr as the detection method.")

    try:
        if method == "zscore":
            threshold = float(data.get("threshold", 3.0))
            if not math.isfinite(threshold) or threshold <= 0:
                raise ValueError
            mask = detect_outliers_zscore(frame[column], threshold)
            settings = {"threshold": threshold}
        else:
            multiplier = float(data.get("multiplier", 1.5))
            if not math.isfinite(multiplier) or multiplier <= 0:
                raise ValueError
            mask = detect_outliers_iqr(frame[column], multiplier)
            settings = {"multiplier": multiplier}
    except (TypeError, ValueError):
        return error_response("The method setting must be a positive number.")

    numeric_values = pd.to_numeric(frame[column], errors="coerce")
    outlier_indexes = frame.index[mask.fillna(False)].tolist()
    outliers = []
    for row_index in outlier_indexes[:100]:
        value = numeric_values.loc[row_index]
        outliers.append({
            "row_id": int(row_index) if isinstance(row_index, (int, np.integer)) else str(row_index),
            "row_number": frame.index.get_loc(row_index) + 1 if isinstance(row_index, (int, np.integer)) else None,
            "value": make_json_value(value),
        })

    valid_count = int(numeric_values.notna().sum())
    return jsonify({
        "column": column,
        "method": method,
        "settings": settings,
        "valid_count": valid_count,
        "outlier_count": int(mask.fillna(False).sum()),
        "outliers": outliers,
        "truncated": int(mask.fillna(False).sum()) > 100,
    })


@app.post("/api/undo")
def undo_last_action():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error_response("A JSON undo request is required.")

    dataset_id = data.get("dataset_id")
    frame = find_dataset(dataset_id)
    if frame is None:
        return error_response("Dataset not found. Upload it again to continue.", 404)

    stack = undo_stacks.get(dataset_id, [])
    if not stack:
        return error_response("There is no action to undo.", 409)

    entry = stack.pop()
    datasets[dataset_id] = entry["before"].copy()
    response = make_dataset_response(dataset_id, datasets[dataset_id])
    response["message"] = f"Undid: {entry['description']}"
    response["undone_action"] = entry["description"]
    return jsonify(response)


def make_chart(frame, data):
    chart_type = data.get("type")

    if chart_type == "box_all":
        numeric_data = frame.select_dtypes(include="number").copy()
        identifier_columns = set(detect_identifier_columns(frame))
        numeric_data = numeric_data.drop(columns=list(identifier_columns), errors="ignore")

        if numeric_data.shape[1] == 0:
            raise ValueError("There are no numeric measurement columns to plot.")

        plot_data = numeric_data.apply(pd.to_numeric, errors="coerce")
        plot_data = plot_data.replace([np.inf, -np.inf], np.nan)
        plot_data = plot_data.dropna(axis=1, how="all")
        if plot_data.shape[1] == 0:
            raise ValueError("There are no numeric values to plot.")

        note = ""
        if plot_data.shape[1] > 25:
            plot_data = plot_data.iloc[:, :25]
            note = "Showing the first 25 numeric measurement columns."

        figure_width = max(8, min(20, plot_data.shape[1] * 0.75))
        figure, axis = plt.subplots(figsize=(figure_width, 5.5))
        sns.boxplot(data=plot_data, color="#d8d5ff", ax=axis)
        axis.set_title("Box plots for all numeric columns")
        axis.set_xlabel("Column")
        axis.set_ylabel("Value")
        axis.tick_params(axis="x", labelrotation=45)
        figure.tight_layout()
        return figure, note

    if chart_type in ("histogram", "violin", "box"):
        column = data.get("column")
        if not isinstance(column, str) or column not in frame.columns:
            raise ValueError(f"Choose a valid column for the {chart_type} plot.")

        values = pd.to_numeric(frame[column], errors="coerce").dropna().to_numpy(dtype=float)
        values = values[np.isfinite(values)]
        if len(values) == 0:
            raise ValueError("This column has no numeric values to plot.")
        if chart_type == "violin" and (len(values) < 2 or np.ptp(values) == 0):
            raise ValueError("A violin plot needs at least two different numeric values.")

        figure, axis = plt.subplots(figsize=(8, 4.5))
        if chart_type == "histogram":
            sns.histplot(x=values, bins="auto", stat="density", alpha=0.65, label="Histogram", ax=axis)
            if len(values) > 1 and np.std(values) > 0:
                sample = values
                if len(sample) > 5000:
                    sample = sample[np.linspace(0, len(sample) - 1, 5000, dtype=int)]
                sns.kdeplot(x=sample, color="#f08c52", label="KDE", ax=axis)

            axis.set(title=f"Distribution of {column}", xlabel=column, ylabel="Density")
            axis.legend()
        elif chart_type == "violin":
            if len(values) > 10_000:
                values = values[np.linspace(0, len(values) - 1, 10_000, dtype=int)]
            sns.violinplot(y=values, inner="box", color="#d8d5ff", ax=axis)
            axis.set(title=f"Distribution of {column}", ylabel=column)
        else:
            sns.boxplot(y=values, color="#d8d5ff", ax=axis)
            axis.set(title=f"Box plot of {column}", ylabel=column)
        figure.tight_layout()
        return figure, ""

    if chart_type == "count":
        column = data.get("column")
        if not isinstance(column, str) or column not in frame.columns:
            raise ValueError("Choose a valid column for the count plot.")

        counts = frame[column].value_counts(dropna=False)
        if counts.empty:
            raise ValueError("This column has no values to count.")

        note = ""
        if len(counts) > 30:
            counts = counts.head(30)
            note = "Showing the 30 most frequent values."
        plot_data = pd.DataFrame({
            "label": ["Missing" if pd.isna(value) else str(value) for value in counts.index],
            "count": counts.to_numpy(),
        })
        figure, axis = plt.subplots(figsize=(8, 4.5))
        sns.barplot(data=plot_data, x="label", y="count", color="#6258e8", ax=axis)
        axis.set(title=f"Value counts for {column}", xlabel=column, ylabel="Count")
        axis.tick_params(axis="x", labelrotation=45)
        figure.tight_layout()
        return figure, note

    if chart_type == "scatter":
        x_column = data.get("x")
        y_column = data.get("y")
        if (
            not isinstance(x_column, str)
            or not isinstance(y_column, str)
            or x_column not in frame.columns
            or y_column not in frame.columns
        ):
            raise ValueError("Choose valid columns for the scatter plot.")

        points = pd.DataFrame({
            "x": pd.to_numeric(frame[x_column], errors="coerce"),
            "y": pd.to_numeric(frame[y_column], errors="coerce"),
        }).dropna()
        points = points[np.isfinite(points).all(axis=1)]
        if points.empty:
            raise ValueError("These columns have no numeric rows in common.")
        if len(points) > 10_000:
            points = points.iloc[np.linspace(0, len(points) - 1, 10_000, dtype=int)]

        figure, axis = plt.subplots(figsize=(8, 4.5))
        sns.scatterplot(data=points, x="x", y="y", alpha=0.7, color="#6258e8", ax=axis)
        axis.set(title=f"{y_column} vs {x_column}", xlabel=x_column, ylabel=y_column)
        axis.grid(alpha=0.2)
        figure.tight_layout()
        return figure, ""

    if chart_type == "heatmap":
        numeric_data = frame.select_dtypes(include="number")
        if numeric_data.shape[1] < 2:
            raise ValueError("A correlation heatmap needs at least two numeric columns.")

        note = ""
        if numeric_data.shape[1] > 25:
            numeric_data = numeric_data.iloc[:, :25]
            note = "Showing the first 25 numeric columns."

        correlations = numeric_data.corr()
        figure, axis = plt.subplots(figsize=(8, 6))
        sns.heatmap(correlations,annot = True,fmt=".2f", cmap="coolwarm", vmin=-1, vmax=1, ax=axis, cbar_kws={"label": "Correlation"})
        axis.set_title("Numeric feature correlation")
        figure.tight_layout()
        return figure, note

    raise ValueError("Choose histogram, violin, count, box, box-all, scatter, or heatmap.")




@app.post("/api/plot")
def create_plot():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error_response("A JSON chart request is required.")

    dataset_id = data.get("dataset_id")
    frame = find_dataset(dataset_id)
    if frame is None:
        return error_response("Dataset not found. Upload it again to continue.", 404)

    try:
        figure, note = make_chart(frame, data)
        image_buffer = io.BytesIO()
        figure.savefig(image_buffer, format="png", dpi=140, bbox_inches="tight")
        plt.close(figure)
    except ValueError as error:
        return error_response(str(error))

    encoded_image = base64.b64encode(image_buffer.getvalue()).decode("ascii")
    return jsonify({
        "image": f"data:image/png;base64,{encoded_image}",
        "note": note,
    })

if __name__ == "__main__":
    app.run(debug=True)
