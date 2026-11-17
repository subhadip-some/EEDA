import base64
import io
import uuid

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from flask import Blueprint, jsonify, request

from .core import (
    chart_history,
    detect_categorical_columns,
    detect_identifier_columns,
    error_response,
    find_dataset,
)

plt.style.use("dark_background")
sns.set_theme(style="darkgrid", rc={
    "figure.facecolor": "#0D0D0D",
    "axes.facecolor": "#111313",
    "axes.edgecolor": "#00FFFF",
    "axes.labelcolor": "#D1D5DB",
    "text.color": "#00FF00",
    "xtick.color": "#A9B5C4",
    "ytick.color": "#A9B5C4",
    "grid.color": "#00FFFF",
    "grid.alpha": 0.35,
})

blueprint = Blueprint("charts", __name__)


def _category_labels(series):
    return series.map(lambda value: "Missing" if pd.isna(value) else str(value))


def _limit_categories(plot_data, column, label, limit=15):
    counts = plot_data[column].value_counts()
    if len(counts) <= limit:
        return plot_data, ""
    categories = counts.head(limit).index
    return plot_data[plot_data[column].isin(categories)], f"Showing the {limit} most frequent categories for {label}."


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
        sns.boxplot(data=plot_data, color="#00FFFF", ax=axis)
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
            sns.histplot(x=values, bins="auto", stat="density", alpha=0.65, color="#00FF00", label="Histogram", ax=axis)
            if len(values) > 1 and np.std(values) > 0:
                sample = values
                if len(sample) > 5000:
                    sample = sample[np.linspace(0, len(sample) - 1, 5000, dtype=int)]
                sns.kdeplot(x=sample, color="#FF00FF", label="KDE", ax=axis)

            axis.set(title=f"Distribution of {column}", xlabel=column, ylabel="Density")
            axis.legend()
        elif chart_type == "violin":
            if len(values) > 10_000:
                values = values[np.linspace(0, len(values) - 1, 10_000, dtype=int)]
            sns.violinplot(y=values, inner="box", color="#00FFFF", ax=axis)
            axis.set(title=f"Distribution of {column}", ylabel=column)
        else:
            sns.boxplot(y=values, color="#00FFFF", ax=axis)
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
        sns.barplot(data=plot_data, x="label", y="count", color="#00FF00", ax=axis)
        axis.set(title=f"Value counts for {column}", xlabel=column, ylabel="Count")
        axis.tick_params(axis="x", labelrotation=45)
        figure.tight_layout()
        return figure, note

    if chart_type == "pie":
        column = data.get("column")
        if not isinstance(column, str) or column not in frame.columns:
            raise ValueError("Choose a valid column for the pie plot.")

        counts = frame[column].value_counts(dropna=False)
        if counts.empty:
            raise ValueError("This column has no values to count.")

        note = ""
        if len(counts) > 10:
            counts = counts.head(10)
            note = "Showing the 10 most frequent values."

        labels = ["Missing" if pd.isna(value) else str(value) for value in counts.index]
        values = counts.to_numpy(dtype=float)
        figure, axis = plt.subplots(figsize=(8, 6))
        _, _, autotexts = axis.pie(
            values,
            labels=labels,
            autopct="%1.1f%%",
            startangle=90,
            counterclock=False,
            wedgeprops={"edgecolor": "#0D0D0D", "linewidth": 1.2},
            colors=sns.color_palette("viridis", n_colors=len(values)),
        )
        axis.set_title(f"Share of values in {column}")
        axis.axis("equal")
        for text in autotexts:
            text.set_color("#D1D5DB")
            text.set_fontsize(9)
        figure.tight_layout()
        return figure, note

    if chart_type in ("scatter", "relationship"):
        x_column = data.get("x")
        y_column = data.get("y")
        if (
            not isinstance(x_column, str)
            or not isinstance(y_column, str)
            or x_column not in frame.columns
            or y_column not in frame.columns
        ):
            raise ValueError("Choose valid columns for the relationship plot.")

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
        sns.scatterplot(data=points, x="x", y="y", alpha=0.7, color="#00FFFF", ax=axis)
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
        sns.heatmap(correlations,annot = True,fmt=".2f", cmap="magma", vmin=-1, vmax=1, ax=axis, cbar_kws={"label": "Correlation"})
        axis.set_title("Numeric feature correlation")
        figure.tight_layout()
        return figure, note

    if chart_type == "crosstab":
        col1 = data.get("column1")
        col2 = data.get("column2")
        if not isinstance(col1, str) or not isinstance(col2, str):
            raise ValueError("Choose two valid columns for cross-tabulation.")
        if col1 not in frame.columns or col2 not in frame.columns:
            raise ValueError("Choose valid columns for cross-tabulation.")
        if col1 == col2:
            raise ValueError("Choose two different columns for cross-tabulation.")

        categorical_columns = set(detect_categorical_columns(frame))
        if col1 not in categorical_columns or col2 not in categorical_columns:
            raise ValueError("Cross-tabulation requires two categorical columns.")

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

        n_rows, n_cols = ct.shape
        fig_width = max(8, min(18, n_cols * 0.85))
        fig_height = max(6, min(14, n_rows * 0.55))

        figure, axis = plt.subplots(figsize=(fig_width, fig_height))
        sns.heatmap(ct, annot=True, fmt="d", cmap="magma", ax=axis,
                    cbar_kws={"label": "Count"})
        axis.set_title(f"Cross-tabulation: {col1} vs {col2}")
        axis.set_xlabel(col2)
        axis.set_ylabel(col1)
        axis.tick_params(axis="x", labelrotation=45)
        axis.tick_params(axis="y", labelrotation=0)
        figure.tight_layout()
        return figure, note

    if chart_type in ("stacked_bar", "grouped_bar"):
        x_column = data.get("x")
        y_column = data.get("y")
        if (
            not isinstance(x_column, str)
            or not isinstance(y_column, str)
            or x_column not in frame.columns
            or y_column not in frame.columns
        ):
            raise ValueError("Choose two valid categorical columns for the bar plot.")
        if x_column == y_column:
            raise ValueError("Choose two different categorical columns for the bar plot.")

        categorical_columns = set(detect_categorical_columns(frame))
        if x_column not in categorical_columns or y_column not in categorical_columns:
            raise ValueError("Stacked and grouped bar plots require two categorical columns.")

        plot_data = pd.DataFrame({
            "x": _category_labels(frame[x_column]),
            "y": _category_labels(frame[y_column]),
        })
        if plot_data.empty:
            raise ValueError("These columns have no values to plot.")

        notes = []
        plot_data, note = _limit_categories(plot_data, "x", x_column)
        if note:
            notes.append(note)
        plot_data, note = _limit_categories(plot_data, "y", y_column)
        if note:
            notes.append(note)
        counts = pd.crosstab(plot_data["x"], plot_data["y"])
        if counts.empty:
            raise ValueError("These columns have no values to plot.")

        figure_width = max(8, min(18, counts.shape[0] * 0.9))
        figure, axis = plt.subplots(figsize=(figure_width, 5))
        positions = np.arange(len(counts.index))
        colors = sns.color_palette("viridis", n_colors=len(counts.columns))
        if chart_type == "stacked_bar":
            bottom = np.zeros(len(counts.index))
            for category, color in zip(counts.columns, colors):
                values = counts[category].to_numpy()
                axis.bar(positions, values, bottom=bottom, color=color, label=category)
                bottom += values
            axis.set_title(f"Stacked counts of {y_column} by {x_column}")
        else:
            width = 0.8 / len(counts.columns)
            for index, (category, color) in enumerate(zip(counts.columns, colors)):
                offset = (index - (len(counts.columns) - 1) / 2) * width
                axis.bar(positions + offset, counts[category].to_numpy(), width=width, color=color, label=category)
            axis.set_title(f"Grouped counts of {y_column} by {x_column}")
        axis.set_xticks(positions, counts.index)
        axis.set_xlabel(x_column)
        axis.set_ylabel("Count")
        axis.tick_params(axis="x", labelrotation=45)
        axis.legend(title=y_column)
        figure.tight_layout()
        return figure, " ".join(notes)

    if chart_type in ("strip", "bar"):
        category_column = data.get("x")
        numeric_column = data.get("y")
        if (
            not isinstance(category_column, str)
            or not isinstance(numeric_column, str)
            or category_column not in frame.columns
            or numeric_column not in frame.columns
        ):
            raise ValueError("Choose a valid categorical column and numeric column.")
        if category_column == numeric_column:
            raise ValueError("Choose different categorical and numeric columns.")

        categorical_columns = set(detect_categorical_columns(frame))
        numeric_columns = set(frame.select_dtypes(include="number").columns)
        if category_column not in categorical_columns or numeric_column not in numeric_columns:
            raise ValueError("Strip and bar plots require one categorical column and one numeric column.")

        values = pd.to_numeric(frame[numeric_column], errors="coerce")
        plot_data = pd.DataFrame({
            "category": _category_labels(frame[category_column]),
            "value": values,
        })
        plot_data = plot_data[np.isfinite(plot_data["value"])]
        if plot_data.empty:
            raise ValueError("These columns have no numeric rows in common.")

        plot_data, note = _limit_categories(plot_data, "category", category_column, limit=20)
        figure_width = max(8, min(18, plot_data["category"].nunique() * 0.8))
        figure, axis = plt.subplots(figsize=(figure_width, 5))
        if chart_type == "strip":
            if len(plot_data) > 10_000:
                plot_data = plot_data.iloc[np.linspace(0, len(plot_data) - 1, 10_000, dtype=int)]
                sample_note = "Showing a deterministic sample of 10,000 rows."
                note = f"{note} {sample_note}".strip()
            sns.stripplot(data=plot_data, x="category", y="value", jitter=True, alpha=0.65, color="#00FFFF", ax=axis)
            axis.set_title(f"{numeric_column} by {category_column}")
        else:
            means = plot_data.groupby("category", sort=False)["value"].mean()
            axis.bar(means.index, means.to_numpy(), color="#00FF00")
            axis.set_title(f"Mean {numeric_column} by {category_column}")
        axis.set_xlabel(category_column)
        axis.set_ylabel(numeric_column)
        axis.tick_params(axis="x", labelrotation=45)
        figure.tight_layout()
        return figure, note

    if chart_type == "line":
        x_column = data.get("x")
        y1_column = data.get("y1")
        y2_column = data.get("y2")
        if (
            not isinstance(x_column, str)
            or not isinstance(y1_column, str)
            or not isinstance(y2_column, str)
            or x_column not in frame.columns
            or y1_column not in frame.columns
            or y2_column not in frame.columns
        ):
            raise ValueError("Choose valid columns for the line graph.")
        if len({x_column, y1_column, y2_column}) < 3:
            raise ValueError("Choose three different columns for the line graph.")

        plot_data = pd.DataFrame({
            "x": pd.to_numeric(frame[x_column], errors="coerce"),
            "y1": pd.to_numeric(frame[y1_column], errors="coerce"),
            "y2": pd.to_numeric(frame[y2_column], errors="coerce"),
        }).dropna()
        plot_data = plot_data[np.isfinite(plot_data).all(axis=1)]
        if plot_data.empty:
            raise ValueError("These columns have no numeric rows in common.")
        plot_data = plot_data.sort_values("x")
        if len(plot_data) > 10_000:
            plot_data = plot_data.iloc[np.linspace(0, len(plot_data) - 1, 10_000, dtype=int)]

        figure, axis = plt.subplots(figsize=(8, 4.5))
        axis.plot(plot_data["x"], plot_data["y1"], label=y1_column, color="#00FFFF", alpha=0.85)
        axis.plot(plot_data["x"], plot_data["y2"], label=y2_column, color="#FF00FF", alpha=0.85)
        axis.set(title=f"{y1_column} and {y2_column} over {x_column}", xlabel=x_column, ylabel="Value")
        axis.legend()
        axis.grid(alpha=0.2)
        figure.tight_layout()
        return figure, ""
    
    

    raise ValueError(
        "Choose histogram, violin, count, pie, box, box-all, scatter, relationship, "
        "heatmap, crosstab, stacked-bar, grouped-bar, strip, bar, or line."
    )


@blueprint.post("/api/plot")
def create_plot():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error_response("A JSON chart request is required.")

    dataset_id = data.get("dataset_id")
    frame = find_dataset(dataset_id)
    if frame is None:
        return error_response("Dataset not found. Upload it again to continue.", 404)

    figure = None
    try:
        figure, note = make_chart(frame, data)
        image_buffer = io.BytesIO()
        figure.savefig(image_buffer, format="png", dpi=140, bbox_inches="tight")
    except ValueError as error:
        return error_response(str(error))
    finally:
        if figure is not None:
            plt.close(figure)

    image_bytes = image_buffer.getvalue()
    chart_id = uuid.uuid4().hex
    chart_label = _chart_label(data)
    chart_history.setdefault(dataset_id, []).append({
        "id": chart_id,
        "label": chart_label,
        "image": image_bytes,
    })
    encoded_image = base64.b64encode(image_bytes).decode("ascii")
    return jsonify({
        "image": f"data:image/png;base64,{encoded_image}",
        "chart_id": chart_id,
        "chart_label": chart_label,
        "note": note,
    })


def _chart_label(data):
    chart_type = data.get("type", "Chart")
    labels = {
        "histogram": "Histogram + KDE",
        "violin": "Violin plot",
        "count": "Count plot",
        "pie": "Pie plot",
        "box": "Box plot",
        "box_all": "Box plots for all numeric columns",
        "scatter": "Scatter plot",
        "relationship": "Relationship chart",
        "heatmap": "Correlation heatmap",
        "crosstab": "Cross-tabulation",
        "line": "Line graph",
        "stacked_bar": "Stacked bar plot",
        "grouped_bar": "Grouped bar plot",
        "strip": "Strip plot",
        "bar": "Bar plot",
    }
    label = labels.get(chart_type, "Chart")
    column = data.get("column")
    if isinstance(column, str):
        return f"{label}: {column}"
    x_column = data.get("x")
    y_column = data.get("y")
    if isinstance(x_column, str) and isinstance(y_column, str):
        if data.get("type") == "bar":
            return f"{label}: {y_column} by {x_column}"
        return f"{label}: {y_column} vs {x_column}"
    column1 = data.get("column1")
    column2 = data.get("column2")
    if isinstance(column1, str) and isinstance(column2, str):
        return f"{label}: {column1} vs {column2}"
    y1_column = data.get("y1")
    y2_column = data.get("y2")
    if all(isinstance(value, str) for value in (x_column, y1_column, y2_column)):
        return f"{label}: {y1_column} and {y2_column} over {x_column}"
    return label
