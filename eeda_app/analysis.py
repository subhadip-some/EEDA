import math
import numpy as np
import pandas as pd
from flask import Blueprint, jsonify, request

from .core import (
    _invalidate_column_cache,
    _invalidate_stats_cache,
    datasets,
    detect_outliers_iqr,
    detect_outliers_zscore,
    error_response,
    find_dataset,
    get_outlier_bounds,
    make_dataset_response,
    make_json_value,
    push_undo_action,
)


blueprint = Blueprint("analysis", __name__)


@blueprint.post("/api/outliers")
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

@blueprint.post("/api/handle-outliers")
def handle_outliers():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error_response("A JSON outlier request is required.")

    dataset_id = data.get("dataset_id")
    frame = find_dataset(dataset_id)
    if frame is None:
        return error_response("Dataset not found. Upload it again to continue.", 404)

    column = data.get("column")
    method = data.get("method", "zscore")
    action = data.get("action")
    if not isinstance(column, str) or column not in frame.columns:
        return error_response("Choose a valid column.")
    if not pd.api.types.is_numeric_dtype(frame[column]):
        return error_response("Outlier handling is only available for numeric columns.")
    if method not in ("zscore", "iqr"):
        return error_response("Choose either zscore or iqr as the detection method.")
    if action not in ("mean", "median", "mode", "winsorize", "remove_rows"):
        return error_response("Choose a valid outlier handling action.")

    try:
        if method == "zscore":
            threshold = float(data.get("threshold", 3.0))
            if not math.isfinite(threshold) or threshold <= 0:
                raise ValueError
            mask = detect_outliers_zscore(frame[column], threshold)
            lower_bound, upper_bound = get_outlier_bounds(
                frame[column], method="zscore", threshold=threshold
            )
            method_setting = f"Z-score threshold {threshold}"
        else:
            multiplier = float(data.get("multiplier", 1.5))
            if not math.isfinite(multiplier) or multiplier <= 0:
                raise ValueError
            mask = detect_outliers_iqr(frame[column], multiplier)
            lower_bound, upper_bound = get_outlier_bounds(
                frame[column], method="iqr", multiplier=multiplier
            )
            method_setting = f"IQR multiplier {multiplier}"
    except (TypeError, ValueError):
        return error_response("The method setting must be a positive number.")

    mask = mask.fillna(False)
    outlier_count = int(mask.sum())
    if outlier_count == 0:
        return error_response("No outliers were found in this column. Detection must find values before they can be handled.")

    updated_frame = frame.copy()
    if action == "remove_rows":
        updated_frame = updated_frame.loc[~mask].copy()
        if updated_frame.empty:
            return error_response("This action would remove every row.")
        description = f"Removed {outlier_count} outlier row{'s' if outlier_count != 1 else ''} in {column}"
        message = f"Removed {outlier_count} outlier row{'s' if outlier_count != 1 else ''} from {column}."
    else:
        values = pd.to_numeric(updated_frame[column], errors="coerce")
        updated_frame[column] = values.astype(float)
        values = updated_frame[column]
        if action == "mean":
            non_outlier_values = values.loc[~mask & np.isfinite(values)]
            replacement = non_outlier_values.mean() if len(non_outlier_values) else values.mean()
            if not math.isfinite(float(replacement)):
                return error_response("There is no valid replacement value for this column.")
            updated_frame.loc[mask, column] = replacement
            description = f"Replaced outliers in {column} with mean"
            message = f"Replaced {outlier_count} outlier{'s' if outlier_count != 1 else ''} in {column} with the mean."
        elif action == "median":
            non_outlier_values = values.loc[~mask & np.isfinite(values)]
            replacement = non_outlier_values.median() if len(non_outlier_values) else values.median()
            if not math.isfinite(float(replacement)):
                return error_response("There is no valid replacement value for this column.")
            updated_frame.loc[mask, column] = replacement
            description = f"Replaced outliers in {column} with median"
            message = f"Replaced {outlier_count} outlier{'s' if outlier_count != 1 else ''} in {column} with the median."
        elif action == "mode":
            non_outlier_values = values.loc[~mask & np.isfinite(values)]
            source_values = non_outlier_values if len(non_outlier_values) else values
            modes = source_values.mode(dropna=True)
            if modes.empty:
                return error_response("There is no valid replacement value for this column.")
            replacement = modes.iloc[0]
            if not math.isfinite(float(replacement)):
                return error_response("There is no valid replacement value for this column.")
            updated_frame.loc[mask, column] = replacement
            description = f"Replaced outliers in {column} with mode"
            message = f"Replaced {outlier_count} outlier{'s' if outlier_count != 1 else ''} in {column} with the mode."
        else:
            if lower_bound is None or upper_bound is None:
                return error_response("Winsorization is unavailable because the column has no valid variance or bounds.")
            updated_frame.loc[mask & (values < lower_bound), column] = lower_bound
            updated_frame.loc[mask & (values > upper_bound), column] = upper_bound
            description = f"Winsorized outliers in {column}"
            message = f"Winsorized {outlier_count} outlier{'s' if outlier_count != 1 else ''} in {column}."

    push_undo_action(dataset_id, f"{description} ({method_setting})", frame)
    datasets[dataset_id] = updated_frame
    _invalidate_column_cache(dataset_id)
    _invalidate_stats_cache(dataset_id)
    response = make_dataset_response(dataset_id, updated_frame)
    response["message"] = message
    return jsonify(response)


@blueprint.post("/api/crosstab")
def get_crosstab():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error_response("A JSON crosstab request is required.")

    dataset_id = data.get("dataset_id")
    frame = find_dataset(dataset_id)
    if frame is None:
        return error_response("Dataset not found. Upload it again to continue.", 404)

    col1 = data.get("column1")
    col2 = data.get("column2")
    if not isinstance(col1, str) or not isinstance(col2, str):
        return error_response("Choose two valid columns for cross-tabulation.")
    if col1 not in frame.columns or col2 not in frame.columns:
        return error_response("Choose valid columns for cross-tabulation.")
    if col1 == col2:
        return error_response("Choose two different columns for cross-tabulation.")

    numeric_columns = frame.select_dtypes(include="number").columns.tolist()
    if col1 in numeric_columns or col2 in numeric_columns:
        return error_response("Cross-tabulation requires two categorical columns.")

    ct = pd.crosstab(frame[col1], frame[col2])

    note = ""
    max_size = 15
    if ct.shape[0] > max_size:
        row_sums = ct.sum(axis=1).sort_values(ascending=False)
        top_rows = row_sums.head(max_size).index
        ct = ct.loc[top_rows]
        note += f"Showing top {max_size} row categories by frequency. "

    if ct.shape[1] > max_size:
        col_sums = ct.sum(axis=0).sort_values(ascending=False)
        top_cols = col_sums.head(max_size).index
        ct = ct[top_cols]
        note += f"Showing top {max_size} column categories by frequency."

    return jsonify({
        "column1": col1,
        "column2": col2,
        "row_labels": [str(v) for v in ct.index.tolist()],
        "col_labels": [str(v) for v in ct.columns.tolist()],
        "data": [[int(v) for v in row] for row in ct.values.tolist()],
        "note": note.strip(),
    })
