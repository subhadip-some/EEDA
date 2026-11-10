# EEDA — Easy Exploratory Data Analysis

EEDA is an open-source, browser-based Exploratory Data Analysis (EDA) tool designed to help students explore, understand, and prepare datasets without writing repetitive Python or statistical code.

Upload a CSV file, inspect its structure, explore statistical summaries, create visualizations, handle missing values and outliers, and download your modified dataset—all through an interactive interface.

The goal is simple: spend less time writing analysis code and more time understanding the mathematics, asking meaningful questions, and interpreting what the data reveals.

**Project Status:** 🚧 Actively under development. Features, improvements, and documentation are continuously evolving.

---

## Features

- **Dataset loading:** Upload CSV files up to 16 MB.
- **Data inspection:** View shape, column names, types, missing values, duplicate rows, and summary statistics.
- **Column classification:** Detect identifier-like, continuous, discrete, and categorical fields.
- **Data preparation:** Filter columns, handle missing values, and apply encoding options.
- **Action tracking:** Undo edits, compare states, and reset the working dataset.
- **Visualization tools:** Generate histograms, KDE plots, violin plots, box plots, count plots, scatter plots, line charts, and correlation heatmaps.
- **Outlier handling:** Detect and treat outliers using common statistical methods.
- **Export:** Download the processed dataset as a CSV file.

### Typical workflow

1. Start with a question about the dataset.
2. Upload a CSV file and review the overview.
3. Inspect column types and summary statistics.
4. Clean and prepare the data as needed.
5. Explore relationships and distributions with charts.
6. Interpret the results and export the cleaned dataset.

---

## Getting Started

### Requirements

- Python 3
- Git
- A modern web browser

### Installation

1. Clone the repository:

```bash
git clone <repository-url>
```

2. Change into the project directory:

```bash
cd EEDA
```

3. Create and activate a virtual environment:

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

4. Install dependencies:

```bash
python -m pip install -r requirements.txt
```

5. Run the application:

```bash
python app.py
```

6. Open the app in your browser:

```text
http://127.0.0.1:5000
```

To stop the app, press `Ctrl + C` in the terminal.

---

## Project Structure

```text
EEDA/
├── app.py                  # Development and WSGI entry point
├── eeda_app/
│   ├── __init__.py         # Flask app factory and blueprint registration
│   ├── core.py             # Dataset state and dataframe helpers
│   ├── datasets.py         # Upload, download, and data retrieval
│   ├── edits.py            # Data edits and undo
│   ├── analysis.py         # Outlier operations and cross-tabulation
│   └── charts.py           # Chart generation
├── requirements.txt        # Python dependencies
├── templates/
│   └── index.html          # Main application interface
├── static/
│   ├── app.js              # Frontend interactions
│   └── style.css           # Application styling
└── README.md               # Project documentation
```

---

## Available Visualizations

| Visualization       | Purpose                                                 |
| ------------------- | ------------------------------------------------------- |
| Histogram + KDE     | Explore the distribution and shape of numerical data    |
| Violin Plot         | Understand distribution shape and density               |
| Box Plot            | Summarize distributions and identify potential outliers |
| Count Plot          | Compare category frequencies                            |
| Scatter Plot        | Explore relationships between two numerical variables   |
| Relationship Chart  | Investigate how two variables change together           |
| Line Graph          | Examine changes in numerical variables over time        |
| Correlation Heatmap | Compare pairwise correlations between numerical columns |

Charts are exploratory aids. Correlation does not imply causation, and visual patterns should always be interpreted in context.

---

## CSV Handling and Session Behavior

- Uploaded files must be CSV files with column names in the first row.
- Files larger than 16 MB are not accepted.
- Uploaded data is kept in memory for the active session only.
- Data and changes are lost when the application stops.
- Downloading exports the current working dataset as UTF-8 CSV.
- The original file on your computer is never modified.
- Column classifications are heuristic-based and should be reviewed before analysis.

---

## Contributing

Contributions from developers, students, and data enthusiasts are welcome!

EEDA is an evolving project, and there is plenty of room for improvements, new visualizations, statistical methods, data-cleaning techniques, and interface enhancements.

If you want to contribute, follow these steps:

### 1. Fork the repository

Fork the EEDA repository to your GitHub account.

### 2. Clone your fork

```bash
git clone https://github.com/<your-username>/EEDA.git
cd EEDA
```

### 3. Create a new branch

Create a separate branch for your contribution.

```bash
git checkout -b feature/your-feature-name
```

For bug fixes:

```bash
git checkout -b fix/your-fix-name
```

### 4. Set up the development environment

Follow the installation instructions in the Getting Started section.

### 5. Make your changes

You can contribute by:

- Adding new statistical analysis methods.
- Implementing additional visualization techniques.
- Improving missing-value and outlier handling.
- Optimizing existing Python or JavaScript code.
- Improving the user interface and experience.
- Fixing bugs and improving error handling.
- Improving documentation.

Please keep your changes focused and avoid modifying unrelated parts of the application.

### 6. Commit your changes

Use clear and descriptive commit messages.

```bash
git add .
git commit -m "Add new visualization feature"
```

### 7. Push your branch

```bash
git push origin feature/your-feature-name
```

### 8. Open a Pull Request

Go to your fork on GitHub and create a Pull Request against the original EEDA repository.

In your Pull Request, briefly explain:

- What you changed.
- Why the change is useful.
- How the feature or fix works.
- Any relevant screenshots, if applicable.

Please make sure your changes work locally before submitting a Pull Request.

### Reporting Bugs

If you encounter a bug, open a GitHub Issue and include:

- A clear description of the problem.
- Steps to reproduce it.
- Expected behavior.
- Actual behavior.
- Relevant error messages or screenshots.

---
