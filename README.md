# DataPilot

DataPilot is a private, session-based workspace for turning messy CSV files into analysis-ready data. Upload a dataset, inspect its quality, clean it with previews and undo, explore it with charts and plain-language insights, then export the result.

## Features

- Upload CSV files up to 20 MB and inspect a data profile and row preview
- Clean missing values, duplicates, empty rows and columns, text, data types, and outliers
- Preview cleaning operations, undo the last change, and review a cleaning log
- Search and sort rows in the data explorer
- Review data quality, summary statistics, correlations, and categorical values
- Build charts and download cleaned CSV or Excel reports
- Keep uploaded data in an in-memory session that expires after one hour

## Requirements

- Python 3.10 or newer
- pip

## Run locally on Windows

From the repository root in PowerShell:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
Set-Location backend
uvicorn main:app --reload
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) and upload `sample_data/messy_sales.csv` to try the app. The interactive API documentation is at [http://127.0.0.1:8000/api/docs](http://127.0.0.1:8000/api/docs).

## Enable local CSV chat

Install [Ollama](https://ollama.com/download), then pull the local model once:

```powershell
ollama pull llama3.2
```

Keep Ollama running while DataPilot is open, then start the FastAPI app as above. Open **Chat with CSV** after uploading a dataset. The app calls Ollama on `http://127.0.0.1:11434`; no cloud API key is used. The model can answer questions with read-only data tools and cannot change the uploaded dataset.

To use a different locally installed model or Ollama server, set `OLLAMA_MODEL` or `OLLAMA_URL` in the environment before starting FastAPI. The defaults are `llama3.2` and `http://127.0.0.1:11434`.

## Run locally on macOS or Linux

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
cd backend
uvicorn main:app --reload
```

## Run tests

From the repository root with the virtual environment activated:

```bash
python -m pytest tests -q
```

## Project structure

```text
backend/       FastAPI routes, cleaning operations, and analytics
frontend/      Single-page web interface (HTML, CSS, and JavaScript)
sample_data/   Small CSV dataset for trying the app
tests/         Backend and API tests
reports/       Generated reports (kept out of Git)
```

## Data and security notes

- Only `.csv` files are accepted, with a 20 MB upload limit.
- Uploaded datasets are held in server memory and associated with a random session ID; sessions expire after one hour.
- Data does not persist across server restarts.
- CSV and Excel exports neutralize values that could be interpreted as spreadsheet formulas.
- Do not expose this development server publicly without adding production authentication, HTTPS, and deployment hardening.

## Current scope

PDF reports, pivot tables, calculated columns, dataset comparison, range filters, and a settings page are not currently included.
