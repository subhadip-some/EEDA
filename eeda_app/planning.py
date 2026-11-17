import uuid
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request

from .core import (
    _compute_columns,
    _get_cached_stats,
    detect_outliers_iqr,
    datasets,
    error_response,
    find_dataset,
)

blueprint = Blueprint("planning", __name__)

plans = {}  # dataset_id -> {"items": {item_id: {...}}}


def _empty_plan():
    return {"items": {}}


def _get_plan(dataset_id):
    return plans.setdefault(dataset_id, _empty_plan())


def _progress(plan):
    items = list(plan["items"].values())
    done = sum(1 for item in items if item["done"])
    total = len(items)
    return {
        "done": done,
        "total": total,
        "percent": round((done / total * 100) if total else 0),
    }


@blueprint.get("/api/planning/<dataset_id>")
def get_plan(dataset_id):
    if find_dataset(dataset_id) is None:
        return error_response("Dataset not found. Upload it again to continue.", 404)
    plan = _get_plan(dataset_id)
    return jsonify({
        "dataset_id": dataset_id,
        "items": list(plan["items"].values()),
        "progress": _progress(plan),
    })


@blueprint.post("/api/planning/<dataset_id>")
def add_item(dataset_id):
    if find_dataset(dataset_id) is None:
        return error_response("Dataset not found. Upload it again to continue.", 404)
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error_response("A JSON planning request is required.", 400)

    text = str(data.get("text", "")).strip()
    kind = data.get("kind", "custom")
    if kind not in ("recommendation", "custom"):
        kind = "custom"
    if not text:
        return error_response("Plan item text is required.", 400)

    plan = _get_plan(dataset_id)
    item_id = uuid.uuid4().hex
    plan["items"][item_id] = {
        "id": item_id,
        "text": text,
        "kind": kind,
        "done": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    return jsonify({"item": plan["items"][item_id]})


@blueprint.post("/api/planning/<dataset_id>/items/<item_id>/toggle")
def toggle_item(dataset_id, item_id):
    if find_dataset(dataset_id) is None:
        return error_response("Dataset not found. Upload it again to continue.", 404)
    plan = _get_plan(dataset_id)
    item = plan["items"].get(item_id)
    if not item:
        return error_response("Plan item not found.", 404)
    item["done"] = not item["done"]
    return jsonify({"item": item})


@blueprint.delete("/api/planning/<dataset_id>/items/<item_id>")
def delete_item(dataset_id, item_id):
    if find_dataset(dataset_id) is None:
        return error_response("Dataset not found. Upload it again to continue.", 404)
    plan = _get_plan(dataset_id)
    if item_id not in plan["items"]:
        return error_response("Plan item not found.", 404)
    del plan["items"][item_id]
    return jsonify({"deleted": item_id})


@blueprint.post("/api/planning/<dataset_id>/recommendations")
def generate_recommendations(dataset_id):
    frame = find_dataset(dataset_id)
    if frame is None:
        return error_response("Dataset not found. Upload it again to continue.", 404)

    cols = _compute_columns(frame)
    stats = _get_cached_stats(dataset_id, frame)
    missing_per_column = frame.isna().sum()

    plan = _get_plan(dataset_id)
    existing_texts = {item["text"].lower() for item in plan["items"].values()}
    new_items = []

    def add(text):
        if text.lower() in existing_texts:
            return
        item_id = uuid.uuid4().hex
        plan["items"][item_id] = {
            "id": item_id,
            "text": text,
            "kind": "recommendation",
            "done": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        new_items.append(plan["items"][item_id])
        existing_texts.add(text.lower())

    # Missing values
    for column in frame.columns:
        missing = int(missing_per_column[column])
        if missing > 0:
            add(f"Handle missing values in '{column}' ({missing} missing)")

    # Outliers
    numeric_cols = [c for c in cols["numeric_columns"] if c not in cols["identifier_columns"]]
    for column in numeric_cols:
        outlier_count = int(detect_outliers_iqr(frame[column]).fillna(False).sum())
        if outlier_count > 0:
            add(f"Check outliers in '{column}' ({outlier_count} detected)")

    # Categorical encoding
    if cols["categorical_columns"]:
        add("Encode categorical columns")

    # Distribution charts
    if numeric_cols:
        add("Create distribution charts for numeric columns")

    # Correlation exploration
    measurement_cols = [c for c in numeric_cols if c not in cols["identifier_columns"]]
    if len(measurement_cols) >= 2:
        add("Explore correlations between numeric columns")

    return jsonify({
        "added": new_items,
        "progress": _progress(plan),
    })
