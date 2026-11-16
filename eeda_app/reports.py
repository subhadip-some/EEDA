import html
import io
import math
import unicodedata
from datetime import datetime

import numpy as np
import pandas as pd
from flask import Blueprint, request, send_file
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from werkzeug.utils import secure_filename

from .core import (
    _compute_columns,
    _get_cached_stats,
    chart_history,
    detect_outliers_iqr,
    error_response,
    find_dataset,
    original_files,
    undo_stacks,
)


blueprint = Blueprint("reports", __name__)


def _report_text(value):
    text = unicodedata.normalize("NFKC", str(value))
    text = text.encode("cp1252", errors="replace").decode("cp1252")
    text = "".join(character for character in text if ord(character) >= 32 or character in "\t\n\r")
    return html.escape(text, quote=True).replace("\n", "<br/>")


def _display(value):
    if isinstance(value, list):
        return ", ".join(_display(item) for item in value[:3]) or "Unavailable"
    if value is None or value is pd.NA:
        return "Unavailable"
    if isinstance(value, (float, np.floating)):
        if not math.isfinite(float(value)):
            return "Unavailable"
        return f"{value:,.4g}"
    return str(value)


def _table(rows, widths, styles, font_size=8):
    converted_rows = [
        [
            Paragraph(
                _report_text(value),
                styles["TableHeader"] if row_index == 0 else styles["TableCell"],
            )
            for value in row
        ]
        for row_index, row in enumerate(rows)
    ]
    table = Table(converted_rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#18324A")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("LEADING", (0, 0), (-1, -1), font_size + 2),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
            colors.white,
            colors.HexColor("#F2F6F8"),
        ]),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D7E0E5")),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def _draw_page(canvas, document):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#D7E0E5"))
    canvas.setLineWidth(0.5)
    canvas.line(0.55 * inch, 0.48 * inch, 7.95 * inch, 0.48 * inch)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#5B6B75"))
    canvas.drawString(0.55 * inch, 0.31 * inch, "EEDA  |  Exploratory Data Analysis")
    canvas.drawRightString(7.95 * inch, 0.31 * inch, f"Page {document.page}")
    canvas.restoreState()


def _feature_type(column, columns):
    if column in columns["identifier_columns"]:
        return "Identifier-like"
    if column in columns["continuous_columns"]:
        return "Continuous"
    if column in columns["discrete_columns"]:
        return "Discrete"
    if column in columns["categorical_columns"]:
        return "Categorical"
    if column in columns["numeric_columns"]:
        return "Numeric"
    return "Other"


def build_report_pdf(frame, dataset_name, report_data, selected_charts, actions):
    title = report_data.get("title", "").strip() or "Exploratory Data Analysis Report"
    objective = report_data.get("objective", "").strip()
    description = report_data.get("dataset_description", "").strip()
    observations = report_data.get("observations", "").strip()
    columns = _compute_columns(frame)
    statistics = _get_cached_stats(report_data["dataset_id"], frame)
    statistics_by_column = {item["column"]: item for item in statistics}
    missing_by_column = frame.isna().sum()
    missing_total = int(missing_by_column.sum())
    duplicate_count = int(frame.duplicated().sum())
    action_labels = [entry["description"] for entry in actions]

    measurement_columns = [
        column for column in columns["numeric_columns"]
        if column not in columns["identifier_columns"]
    ]
    outliers = []
    for column in measurement_columns:
        count = int(detect_outliers_iqr(frame[column]).fillna(False).sum())
        if count:
            outliers.append((str(column), count))

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="ReportTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=24,
        leading=29,
        textColor=colors.HexColor("#18324A"),
        alignment=TA_CENTER,
        spaceAfter=12,
    ))
    styles.add(ParagraphStyle(
        name="SectionHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=18,
        textColor=colors.HexColor("#18324A"),
        spaceBefore=14,
        spaceAfter=7,
        keepWithNext=True,
    ))
    styles.add(ParagraphStyle(
        name="SubHeading",
        parent=styles["Heading3"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13,
        textColor=colors.HexColor("#26516B"),
        spaceBefore=8,
        spaceAfter=5,
        keepWithNext=True,
    ))
    styles.add(ParagraphStyle(
        name="ReportBody",
        parent=styles["BodyText"],
        fontSize=9,
        leading=13,
        spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name="TableCell",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=9,
        spaceAfter=0,
    ))
    styles.add(ParagraphStyle(
        name="TableHeader",
        parent=styles["TableCell"],
        fontName="Helvetica-Bold",
        textColor=colors.white,
    ))
    styles.add(ParagraphStyle(
        name="ReportMeta",
        parent=styles["ReportBody"],
        alignment=TA_CENTER,
        textColor=colors.HexColor("#5B6B75"),
    ))

    story = [
        Spacer(1, 0.45 * inch),
        Paragraph(_report_text(title), styles["ReportTitle"]),
        Paragraph(
            f"Dataset: {_report_text(dataset_name)}"
            f" &nbsp;&nbsp; | &nbsp;&nbsp; Generated: {datetime.now():%B %d, %Y}",
            styles["ReportMeta"],
        ),
        Spacer(1, 0.3 * inch),
        Paragraph("1. Title and Introduction", styles["SectionHeading"]),
    ]
    if objective:
        story.extend([
            Paragraph("Objective", styles["SubHeading"]),
            Paragraph(_report_text(objective), styles["ReportBody"]),
        ])
    if description:
        story.extend([
            Paragraph("Dataset description", styles["SubHeading"]),
            Paragraph(_report_text(description), styles["ReportBody"]),
        ])

    story.extend([
        Paragraph("2. Dataset Overview", styles["SectionHeading"]),
        Paragraph(
            f"<b>Dataset:</b> {_report_text(dataset_name)}"
            f"<br/><b>Dimensions:</b> {len(frame):,} rows × {len(frame.columns):,} columns"
            f"<br/><b>Numerical columns:</b> {len(columns['numeric_columns'])}"
            f" &nbsp; <b>Categorical columns:</b> {len(columns['categorical_columns'])}",
            styles["ReportBody"],
        ),
    ])
    column_rows = [["Column", "Data type", "Feature type", "Non-missing", "Missing", "Missing %"]]
    for column in frame.columns:
        missing = int(missing_by_column[column])
        column_rows.append([
            str(column),
            str(frame[column].dtype),
            _feature_type(column, columns),
            f"{len(frame) - missing:,}",
            f"{missing:,}",
            f"{missing / len(frame) * 100:.2f}%" if len(frame) else "Unavailable",
        ])
    story.append(_table(
        column_rows,
        [1.35 * inch, 0.95 * inch, 1.15 * inch, 1.0 * inch, 0.75 * inch, 0.8 * inch],
        styles,
    ))

    story.extend([
        Paragraph("3. Descriptive Statistical Analysis", styles["SectionHeading"]),
        Paragraph("Numerical feature summary", styles["SubHeading"]),
    ])
    numeric_rows = [[
        "Column", "Mean", "Median", "Mode", "Min", "Max", "Std. dev.", "Variance", "Skew",
    ]]
    for column in columns["numeric_columns"]:
        statistic = statistics_by_column[str(column)]
        numeric_rows.append([
            str(column),
            _display(statistic["mean"]),
            _display(statistic["median"]),
            _display(statistic["mode"]),
            _display(statistic["min"]),
            _display(statistic["max"]),
            _display(statistic["std"]),
            _display(statistic["var"]),
            _display(statistic["skew"]),
        ])
    if len(numeric_rows) == 1:
        story.append(Paragraph("No numerical columns are available.", styles["ReportBody"]))
    else:
        story.append(_table(
            numeric_rows,
            [1.25 * inch, 0.75 * inch, 0.75 * inch, 1.1 * inch, 0.6 * inch,
             0.6 * inch, 0.75 * inch, 0.75 * inch, 0.55 * inch],
            styles,
            font_size=7,
        ))

    categorical = columns["categorical_columns"]
    if categorical:
        story.extend([
            Paragraph("Categorical feature summary", styles["SubHeading"]),
        ])
        categorical_rows = [["Column", "Distinct values", "Mode"]]
        for column in categorical:
            statistic = statistics_by_column[str(column)]
            categorical_rows.append([
                str(column),
                f"{frame[column].nunique(dropna=True):,}",
                _display(statistic["mode"]),
            ])
        story.append(_table(
            categorical_rows,
            [2.0 * inch, 1.35 * inch, 3.0 * inch],
            styles,
        ))

    story.extend([
        Paragraph("4. Data Quality Analysis", styles["SectionHeading"]),
        Paragraph(f"<b>Duplicate rows:</b> {duplicate_count:,}", styles["ReportBody"]),
        Paragraph("Missing values by column", styles["SubHeading"]),
    ])
    missing_rows = [["Column", "Missing values", "Share of rows"]]
    for column in frame.columns:
        missing = int(missing_by_column[column])
        if missing:
            missing_rows.append([
                str(column),
                f"{missing:,}",
                f"{missing / len(frame) * 100:.2f}%" if len(frame) else "Unavailable",
            ])
    if len(missing_rows) == 1:
        story.append(Paragraph("No missing values were found.", styles["ReportBody"]))
    else:
        story.append(_table(
            missing_rows,
            [2.3 * inch, 1.5 * inch, 1.6 * inch],
            styles,
        ))

    story.append(Paragraph("Outlier analysis", styles["SubHeading"]))
    if not measurement_columns:
        story.append(Paragraph(
            "Outlier analysis is unavailable because there are no numeric measurement columns.",
            styles["ReportBody"],
        ))
    elif not outliers:
        story.append(Paragraph(
            "No outliers were detected in numeric measurement columns using the 1.5× IQR rule.",
            styles["ReportBody"],
        ))
    else:
        outlier_rows = [["Column", "IQR outliers", "Share of rows"]]
        for column, count in outliers:
            outlier_rows.append([
                column,
                f"{count:,}",
                f"{count / len(frame) * 100:.2f}%" if len(frame) else "Unavailable",
            ])
        story.extend([
            Paragraph(
                "Detected using the 1.5× IQR rule; identifier-like columns are excluded.",
                styles["ReportBody"],
            ),
            _table(outlier_rows, [2.3 * inch, 1.5 * inch, 1.6 * inch], styles),
        ])

    story.append(Paragraph("5. Visual Analysis", styles["SectionHeading"]))
    if not selected_charts:
        story.append(Paragraph("No charts were selected for this report.", styles["ReportBody"]))
    for chart in selected_charts:
        story.append(Paragraph(_report_text(chart["title"]), styles["SubHeading"]))
        chart_image = Image(
            io.BytesIO(chart["image"]),
            width=6.9 * inch,
            height=4.2 * inch,
            kind="proportional",
        )
        story.extend([chart_image, Spacer(1, 5)])
        chart_observation = chart["observation"].strip()
        if chart_observation:
            story.extend([
                Paragraph("<b>Observation:</b>", styles["ReportBody"]),
                Paragraph(_report_text(chart_observation), styles["ReportBody"]),
            ])

    story.extend([
        Paragraph("6. Data Cleaning and Preprocessing", styles["SectionHeading"]),
    ])
    if action_labels:
        story.append(Paragraph(
            "The following changes are recorded for the current working dataset:",
            styles["ReportBody"],
        ))
        for action in action_labels:
            story.append(Paragraph(f"• &nbsp; {_report_text(action)}", styles["ReportBody"]))
    else:
        story.append(Paragraph(
            "No data-cleaning or preprocessing actions are recorded for this dataset.",
            styles["ReportBody"],
        ))

    story.append(Paragraph("7. Key Findings", styles["SectionHeading"]))
    findings = [
        f"The working dataset contains {len(frame):,} rows and {len(frame.columns):,} columns.",
        f"{missing_total:,} missing values occur across {int((missing_by_column > 0).sum()):,} columns.",
        f"{duplicate_count:,} duplicate rows are present.",
    ]
    if outliers:
        findings.append(
            f"{sum(count for _, count in outliers):,} IQR outlier values were detected "
            f"across {len(outliers)} numeric measurement columns."
        )
    for finding in findings:
        story.append(Paragraph(f"• &nbsp; {_report_text(finding)}", styles["ReportBody"]))
    if observations:
        story.extend([
            Paragraph("User observations and recommendations", styles["SubHeading"]),
            Paragraph(_report_text(observations), styles["ReportBody"]),
        ])

    story.append(Paragraph("8. Conclusion", styles["SectionHeading"]))
    story.append(Paragraph(
        f"This analysis describes the current working version of “{_report_text(dataset_name)}” "
        f"({len(frame):,} rows × {len(frame.columns):,} columns). "
        f"It contains {missing_total:,} missing values and {duplicate_count:,} duplicate rows. "
        "Interpret the summaries and visualizations in the context of the analysis objective "
        "and the dataset's domain.",
        styles["ReportBody"],
    ))
    if observations:
        story.append(Paragraph(
            f"<b>Recommended next steps:</b> {_report_text(observations)}",
            styles["ReportBody"],
        ))

    output = io.BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=letter,
        rightMargin=0.55 * inch,
        leftMargin=0.55 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.65 * inch,
        title=title,
        author="EEDA",
    )
    document.build(story, onFirstPage=_draw_page, onLaterPages=_draw_page)
    output.seek(0)
    return output


@blueprint.post("/api/report")
def generate_report():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error_response("A JSON report request is required.", 400)

    dataset_id = data.get("dataset_id")
    frame = find_dataset(dataset_id)
    if frame is None:
        return error_response("Dataset not found. Upload it again to continue.", 404)

    text_fields = ("title", "objective", "dataset_description", "observations")
    for field in text_fields:
        value = data.get(field, "")
        if not isinstance(value, str):
            return error_response(f"{field.replace('_', ' ').capitalize()} must be text.", 400)
        if len(value) > 10_000:
            return error_response(f"{field.replace('_', ' ').capitalize()} is too long.", 400)

    selected = data.get("charts", [])
    if not isinstance(selected, list) or len(selected) > 50:
        return error_response("Select no more than 50 charts for a report.", 400)
    available_charts = {
        chart["id"]: chart for chart in chart_history.get(dataset_id, [])
    }
    selected_charts = []
    selected_ids = set()
    for chart in selected:
        if not isinstance(chart, dict):
            return error_response("Selected chart information is invalid.", 400)
        chart_id = chart.get("id")
        if not isinstance(chart_id, str) or chart_id not in available_charts:
            return error_response("A selected chart is no longer available. Create it again.", 400)
        if chart_id in selected_ids:
            return error_response("A chart may only be selected once.", 400)
        selected_ids.add(chart_id)
        title = chart.get("title", "")
        observation = chart.get("observation", "")
        if not isinstance(title, str) or not isinstance(observation, str):
            return error_response("Chart titles and observations must be text.", 400)
        if len(title) > 500 or len(observation) > 10_000:
            return error_response("A chart title or observation is too long.", 400)
        source_chart = available_charts[chart_id]
        selected_charts.append({
            "title": title.strip() or source_chart["label"],
            "observation": observation,
            "image": source_chart["image"],
        })

    dataset_name = original_files.get(dataset_id, ("Dataset", b""))[0]
    report_data = dict(data)
    report_data["dataset_id"] = dataset_id
    pdf = build_report_pdf(
        frame,
        dataset_name,
        report_data,
        selected_charts,
        undo_stacks.get(dataset_id, []),
    )
    filename = secure_filename(data.get("title", "").strip()) or "eeda-report"
    return send_file(
        pdf,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"{filename}.pdf",
    )
