# EEDA — Easy Exploratory Data Analysis

EEDA is a browser-based tool that helps students explore a dataset without
having to write analysis code. Upload a CSV, inspect its columns and summary
statistics, create visualizations, and download a modified copy—all from a
simple interface.

The goal is to make exploratory data analysis more approachable so students
can spend less time on code and more time asking questions, understanding the
math, and interpreting what the data shows.



## What you can do for now
 we are gonna update this section as we add more feature, it is still in development

- **Load a dataset:** Upload a CSV file up to 16 MB.
- **Review the data:** Browse the table, move between pages, and see dataset
  size, column types, missing values, duplicate rows, and column statistics.
- **Spot identifier-like columns:** See which numeric-looking columns
  (zip/postal codes, IDs, codes) are flagged as categorical identifiers rather
  than real measurements.
- **Classify columns by type:** Numeric columns are split into continuous (measurements, decimals, time), discrete (counts, quantities, headcounts), and identifier-like (IDs, zip/postal codes). Categorical columns (text, labels, categories) are shown in a separate box.
- **Choose features:** Keep selected columns or remove selected columns from
  the working dataset.
- **Handle missing values:** handle missing values based on numeric column and categorical column
- **Explore visually:** Create a histogram with a KDE curve, violin plot, box
  plot, count plot, scatter plot, or correlation heatmap.
- **Save your work:** Download the current working dataset as a CSV.



EEDA does not require students to write Python or statistical code to use
these features. Students still choose what to inspect and interpret the
results; the tool is intended to support analysis, not replace it.

## Getting started

### Requirements

- Python 3
- A modern web browser

### Install and run

1. Clone or download this repository, then open a terminal in the project
   folder.
2. Create and activate a virtual environment.

   **Windows PowerShell**

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   **macOS or Linux**

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. Install the dependencies and start the app:

   ```bash
   python -m pip install -r requirements.txt
   python app.py
   ```

   On macOS or Linux, use `python3` instead of `python` if that is how Python
   is installed on your system.

4. Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.
5. Choose a CSV file to begin exploring.

To stop the app, press `Ctrl+C` in the terminal where it is running.

## A student workflow

1. **Start with a question.** For example: What does this variable's
   distribution look like? Do two measurements appear related?
2. **Upload your CSV** and review the dataset profile. Check the row and
   column counts, missing values, duplicates, and detected numeric columns.
3. **Inspect the preview and statistics.** The table displays 20 rows per
   page. Column summaries include mean, median, mode, minimum, maximum,
   standard deviation, variance, and skewness where applicable.
4. **Choose features** to keep or remove from the working dataset.
5. **Create a chart** and select the relevant column or columns. Compare the
   visualization with the summary statistics and your expectations.
6. **Download the modified CSV** if you want to keep the version with your
   selected columns.

## Available visualizations

| Visualization | Useful for |
| --- | --- |
| Histogram + KDE | Exploring the shape and spread of a numeric variable |
| Violin plot | Seeing a numeric distribution's shape and spread |
| Box plot | Summarizing a numeric distribution and spotting potential outliers |
| Count plot | Comparing how often values occur in a column |
| Scatter plot | Exploring the relationship between two numeric columns |
| Correlation heatmap | Comparing pairwise correlations across numeric columns |

Charts are exploratory aids. In particular, correlation does not establish
causation, and patterns should be interpreted in the context of how the data
was collected.

## CSV notes and session behavior

- Upload a `.csv` file with column names in its first row.
- Files larger than 16 MB are not accepted.
- Your uploaded data and edits are held in the running app's memory. They are
  not saved to disk by EEDA and will be lost when the app process stops.
- The app reads the CSV on upload and exports the current working dataset as
  UTF-8 CSV when you download it. The original file on your computer is not
  changed.
- Identifier-like detection is a heuristic: a numeric column is flagged when its
  name mentions zip/postal/postcode, id, code, number, or key, or when it is an
  all-unique integer column. It is a suggestion, not a guarantee — you decide
  how to treat each column.
- Continuous / discrete classification uses column dtype and value patterns:
  float columns with fractional parts are continuous; integer columns and
  low-cardinality whole-number columns are discrete. High-cardinality float
  columns without decimals are treated as continuous measurements.

## Built with

EEDA is a Python Flask application. It uses pandas and NumPy to work with
tabular data, and Matplotlib and Seaborn to create charts. The interface is
built with HTML, CSS, and JavaScript.

## Project structure

```text
.
├── app.py                 # Flask app and data/plot endpoints
├── requirements.txt       # Python dependencies
├── templates/
│   └── index.html         # Main application page
└── static/
    ├── app.js             # Browser-side interactions
    └── style.css          # Application styles
```
