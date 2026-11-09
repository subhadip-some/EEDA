import math

import numpy as np
import pandas as pd
from flask import jsonify
from scipy import stats

rows_per_page = 20

datasets = {}

undo_stacks = {}

original_files = {}

_column_cache = {}   # dataset_id -> precomputed column classifications + statistics

IDENTIFIER_KEYWORDS = (
    "zip", "postal", "postcode", "pin code", "pincode",
    "id", "identifier", "code", "no.", "number", "key",
)

_stats_cache = {}   # dataset_id -> precomputed data_describe statistics

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
        sample = non_null.head(min(1000, len(non_null))).to_numpy(dtype=float)
        has_decimals = bool(np.any(sample % 1 != 0))
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

def _get_numeric_frame(frame):
    """Return the numeric subset of a frame."""
    return frame.select_dtypes(include="number")

def _compute_columns(frame):
    """Compute all column classifications in a single pass over the frame."""
    numeric = _get_numeric_frame(frame)
    numeric_columns = [str(c) for c in numeric.columns]
    integer_columns = [str(c) for c in frame.select_dtypes(include="integer").columns]
    identifier_columns = detect_identifier_columns(frame)
    continuous_columns = detect_continuous_columns(frame)
    discrete_columns = detect_discrete_columns(frame)
    categorical_columns = detect_categorical_columns(frame)
    return {
        "numeric_columns": numeric_columns,
        "integer_columns": integer_columns,
        "identifier_columns": identifier_columns,
        "continuous_columns": continuous_columns,
        "discrete_columns": discrete_columns,
        "categorical_columns": categorical_columns,
    }

def _get_cached_columns(dataset_id, frame):
    """Cache column classifications per dataset so repeated API responses
    don't recompute select_dtypes and heuristics for every request."""
    cached = _column_cache.get(dataset_id)
    if cached is not None:
        return cached
    cached = _compute_columns(frame)
    _column_cache[dataset_id] = cached
    return cached

def _invalidate_column_cache(dataset_id):
    _column_cache.pop(dataset_id, None)

def _invalidate_stats_cache(dataset_id):
    _stats_cache.pop(dataset_id, None)

def _get_cached_stats(dataset_id, frame):
    cached = _stats_cache.get(dataset_id)
    if cached is not None:
        return cached
    stats = data_describe(frame, _compute_columns(frame))
    _stats_cache[dataset_id] = stats
    return stats

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

def get_outlier_bounds(series, method="zscore", threshold=3.0, multiplier=1.5):
    values = pd.to_numeric(series, errors="coerce")
    finite = values[np.isfinite(values)]
    if len(finite) == 0:
        return None, None

    if method == "zscore":
        mean = finite.mean()
        std = finite.std(ddof=0)
        if not math.isfinite(float(std)) or float(std) == 0:
            return None, None
        return mean - threshold * std, mean + threshold * std

    q1 = finite.quantile(0.25)
    q3 = finite.quantile(0.75)
    iqr = q3 - q1
    return q1 - multiplier * iqr, q3 + multiplier * iqr

def make_dataset_response(dataset_id,frame,page=0):
    page_count = max(1,(len(frame) + rows_per_page-1) // rows_per_page)
    page = min(max(page,0),page_count -1)
    first_row = page * rows_per_page
    page_of_rows = frame.iloc[first_row : first_row + rows_per_page]

    # Vectorized row rendering (avoids per-row Series creation in iterrows)
    row_index = page_of_rows.index.tolist()
    row_values = page_of_rows.values.tolist()
    rows = [
        {"id": int(row_id), "values": [make_json_value(v) for v in row_vals]}
        for row_id, row_vals in zip(row_index, row_values)
    ]

    cols = _get_cached_columns(dataset_id, frame)
    missing_per_column = {
        str(column): int(count)
        for column, count in frame.isna().sum().items()
        if count > 0
    }
    duplicate_rows = int(frame.duplicated().sum())
    stats = _get_cached_stats(dataset_id, frame)
    return {
        "dataset_id" : dataset_id,
        "columns" : [str(column) for column in frame.columns],
        "column_statistics": stats,
        "numeric_columns": [str(column) for column in cols["numeric_columns"]],
        "integer_columns": [str(column) for column in cols["integer_columns"]],
        "identifier_columns": [str(column) for column in cols["identifier_columns"]],
        "continuous_columns": [str(column) for column in cols["continuous_columns"]],
        "discrete_columns": [str(column) for column in cols["discrete_columns"]],
        "categorical_columns": [str(column) for column in cols["categorical_columns"]],
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

def data_describe(frame, cols=None):
    if cols is None:
        cols = _compute_columns(frame)
    numeric_columns = set(cols["numeric_columns"])
    identifier_columns = set(cols["identifier_columns"])
    continuous_columns = set(cols["continuous_columns"])
    discrete_columns = set(cols["discrete_columns"])
    categorical_columns = set(cols["categorical_columns"])
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
