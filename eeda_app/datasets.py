import io
import uuid

import pandas as pd
from flask import Blueprint, jsonify, render_template, request, send_file

from .core import (
    _invalidate_column_cache,
    _invalidate_stats_cache,
    datasets,
    error_response,
    find_dataset,
    make_dataset_response,
    original_files,
    undo_stacks,
)


blueprint = Blueprint("datasets", __name__)


@blueprint.get("/")
def home():
    return render_template("index.html")

@blueprint.get("/guide.txt")
def quick_guide():
    return (
        "EEDA Quick Guide\n"
        "================\n"
        "Upload a CSV, then choose a chart from the visualization panel.\n"
        "Use the Chart guide toggle below the chart controls to see what each chart does.\n"
        "Charts: Histogram + KDE, Violin, Box plot, Count plot, Scatter plot,\n"
        "Relationship chart, Line graph, Correlation heatmap, Cross-tabulation,\n"
        "Box plot (all numeric).\n",
        200,
        {"Content-Type": "text/plain; charset=utf-8"},
    )

@blueprint.post("/api/upload")
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
    _invalidate_column_cache(dataset_id)
    _invalidate_stats_cache(dataset_id)
    return jsonify(make_dataset_response(dataset_id,frame))

@blueprint.get("/api/download/<dataset_id>")
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

@blueprint.get("/api/data")
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
