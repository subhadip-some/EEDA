# EEDA — Easy Exploratory Data Analysis

EEDA is an open-source, browser-based Exploratory Data Analysis (EDA) tool designed to help students explore, understand, and prepare datasets without writing repetitive Python or statistical code.

Upload a CSV file, inspect its structure, explore statistical summaries, create visualizations, handle missing values and outliers, and download your modified dataset—all through an interactive interface.

The goal is simple: spend less time writing analysis code and more time understanding the mathematics, asking meaningful questions, and interpreting what the data reveals.

**Project Status:** 🚧 Actively under development. Features, improvements, and documentation are continuously evolving.

---

## Features

### Available Features

- **Load a dataset:** Upload CSV files up to 16 MB.
- **Dataset overview:** Inspect dataset shape, column names, data types, missing values, duplicate rows, and statistical summaries.
- **Identifier-like column detection:** Identify numeric-looking columns such as IDs, ZIP/postal codes, and other codes that should be treated as categorical identifiers.
- **Column classification:** Organize columns into continuous, discrete, identifier-like, and categorical types.
- **Statistical summaries:** Calculate mean, median, mode, minimum, maximum, standard deviation, variance, and skewness where applicable.
- **Feature selection:** Keep selected columns or remove unwanted columns from the working dataset.
- **Missing-value handling:** Handle missing values in numeric and categorical columns.
- **Action history:** Track data modifications, undo individual actions, and reset changes to experiment with datasets.
- **Data visualization:** Generate histograms with KDE, violin plots, box plots, count plots, scatter plots, relationship charts, line graphs, and correlation heatmaps.
- **Outlier detection:** Identify potential outliers using Z-score and IQR methods, supported by box plots.
- **Outlier handling:** Apply mean, median, or mode replacement, winsorization, or outlier removal.
- **Export dataset:** Download the modified working dataset as a CSV file.

### Upcoming Features

This section will be updated as development progresses.

- [ ] Additional statistical analysis techniques.
- [ ] More visualization options.
- [ ] Advanced data-cleaning operations.
- [ ] Improved dataset insights and interpretation.
- [ ] Further performance and UI/UX improvements.

---

## How EEDA Works

EEDA follows a manual, learning-oriented approach to exploratory data analysis.

Instead of automatically performing every analysis, users decide:

1. What they want to investigate.
2. Which columns are relevant.
3. Which statistical methods or visualizations to apply.
4. How to interpret the results.
5. Which data-cleaning operations are appropriate.

EEDA provides the tools to make these processes easier while keeping the actual analytical decisions in the user's hands.

---

## Getting Started

Follow these instructions to set up EEDA locally for development or personal use.

### Requirements

- Python 3
- Git
- A modern web browser

### Installation

**1. Clone the repository**

```bash
git clone <repository-url>
```

**2. Navigate to the project directory**

```bash
cd EEDA
```

**3. Create a virtual environment**

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

**4. Install dependencies**

```bash
python -m pip install -r requirements.txt
```

**5. Run the application**

```bash
python app.py
```

**6. Open EEDA in your browser**

Visit:

```text
http://127.0.0.1:5000
```

You can now upload a CSV file and start exploring your dataset.

To stop the application, press `Ctrl + C` in the terminal.

---

## A Typical Student Workflow

1. **Start with a question:** Decide what you want to investigate in your dataset.
2. **Upload a dataset:** Inspect the dataset overview and identify potential data-quality issues.
3. **Explore columns:** Review column classifications and statistical summaries.
4. **Prepare the data:** Handle missing values, duplicates, unwanted columns, and outliers as needed.
5. **Visualize:** Select appropriate charts to investigate distributions and relationships.
6. **Interpret:** Compare visual patterns with statistical summaries and draw conclusions.
7. **Export:** Download the modified dataset for further analysis.

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

**Chart Guide:** EEDA includes an in-app guide explaining what each visualization represents, when to use it, and which variable types it supports.

Charts are exploratory aids. Correlation does not establish causation, and visual patterns should always be interpreted in context.

---

## Project Structure

```text
EEDA/
│
├── app.py                  # Flask application and backend logic
├── requirements.txt        # Python dependencies
│
├── templates/
│   └── index.html          # Main application interface
│
└── static/
    ├── app.js              # Frontend interactions
    └── style.css           # Application styling
```

---

## Technology Stack

| Technology | Purpose                           |
| ---------- | --------------------------------- |
| Python     | Backend development               |
| Flask      | Web framework and API endpoints   |
| Pandas     | Dataset manipulation and analysis |
| NumPy      | Numerical operations              |
| Matplotlib | Data visualization                |
| Seaborn    | Statistical visualization         |
| HTML       | Application structure             |
| CSS        | Interface styling                 |
| JavaScript | Frontend interactions             |

---

## CSV Handling and Session Behavior

- Uploaded files must be CSV files with column names in the first row.
- Files larger than 16 MB are not accepted.
- Uploaded datasets and modifications are held in the running application's memory.
- EEDA does not permanently save uploaded datasets to disk.
- Data and modifications are lost when the application process stops.
- Downloading exports the current working dataset as UTF-8 CSV.
- The original CSV file on your computer is never modified.

### Column Classification

Identifier-like detection is heuristic-based. Columns may be flagged based on their names or value patterns. These classifications are suggestions, not guarantees.

Continuous and discrete classification uses data types and value patterns. Users should verify the classifications before performing statistical analysis.

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

## Development Notes

- EEDA is designed primarily as a learning-oriented EDA platform.
- Users should remain in control of their analytical decisions.
- New features should prioritize statistical correctness, usability, and educational value.
- Contributions should maintain consistency with the existing project architecture.
- The project is continuously evolving, so some features and implementation details may change.

---

## License

If you plan to distribute EEDA as an open-source project, add your chosen license here and include the corresponding `LICENSE` file in the repository.

---

**Want to contribute?** Fork the repository, explore the code, and help make exploratory data analysis more accessible to students.
