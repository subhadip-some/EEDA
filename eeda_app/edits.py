import math

import pandas as pd
from flask import Blueprint, jsonify, request

from .core import (
    _invalidate_column_cache,
    _invalidate_stats_cache,
    datasets,
    error_response,
    find_dataset,
    make_dataset_response,
    push_undo_action,
    undo_stacks,
)


blueprint = Blueprint("edits", __name__)


@blueprint.post("/api/missing-values")
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
    _invalidate_column_cache(dataset_id)
    _invalidate_stats_cache(dataset_id)
    response = make_dataset_response(dataset_id, updated_frame)
    response["message"] = f"Handled {missing_count} missing value{'s' if missing_count != 1 else ''} in {column}."
    return jsonify(response)

@blueprint.post("/api/columns")
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
    _invalidate_column_cache(dataset_id)
    _invalidate_stats_cache(dataset_id)
    return jsonify(make_dataset_response(dataset_id, updated_frame))

@blueprint.post("/api/rows")
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
    _invalidate_column_cache(dataset_id)
    _invalidate_stats_cache(dataset_id)
    return jsonify(make_dataset_response(dataset_id, updated_frame))

@blueprint.post("/api/undo")
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
    _invalidate_column_cache(dataset_id)
    _invalidate_stats_cache(dataset_id)
    response = make_dataset_response(dataset_id, datasets[dataset_id])
    response["message"] = f"Undid: {entry['description']}"
    response["undone_action"] = entry["description"]
    return jsonify(response)
