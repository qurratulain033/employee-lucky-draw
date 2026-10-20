# Employee Lucky Draw

Streamlit app that imports employees from Excel, runs 5 rounds of 2 unique winners,
saves results in SQLite, and exports winners to CSV/Excel.
Uses FICTIONAL sample data by default.

## Run it
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run app.py
```
Browser opens at http://localhost:8501

## Try it
1. Click **Use 1,200 sample (fictional) employees** in the sidebar (or upload `sample_employees.xlsx`).
2. Click **Draw Round 1** ... up to Round 5.
3. Refresh the page or restart the app: winners are still there (saved in `data/lucky_draw.db`).
4. Open the **Export** tab to download winners.

## Files
| File | Job |
|---|---|
| app.py | Screen / buttons (Streamlit) |
| db.py | SQLite: sessions, rounds, winners, atomic save |
| draw.py | Secure random selection |
| validation.py | Checks the uploaded Excel file |
| generate_data.py | Makes `sample_employees.xlsx` (1,200 fake employees) |
| config.py | Rounds, winners per round, required columns |
| tests/test_logic.py | Acceptance tests (`python -m pytest -q` after `pip install pytest`) |

## Photos (optional)
Put images in `photos/` named by employee ID (e.g. `EMP0001.jpg`) and fill the `Photo`
column with that filename. Without photos, initials avatars are shown.
