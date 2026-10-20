"""Checks an uploaded employee table before it is allowed into the draw."""
import pandas as pd
from config import REQUIRED_COLUMNS, OPTIONAL_COLUMNS


def validate_employees(df: pd.DataFrame):
    """Return (clean_df, errors). If errors is non-empty, do NOT start the draw."""
    errors = []

    # 1. required columns must exist
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        errors.append(f"Missing required column(s): {', '.join(missing)}. "
                      f"Your file has: {', '.join(map(str, df.columns))}.")
        return None, errors

    keep = REQUIRED_COLUMNS + [c for c in OPTIONAL_COLUMNS if c in df.columns]
    df = df[keep].copy()

    # 2. tidy text: strip spaces, turn NaN into ""
    for col in df.columns:
        df[col] = df[col].fillna("").astype(str).str.strip()

    if df.empty:
        errors.append("The file has no employee rows.")
        return None, errors

    # 3. blank values in required columns
    for col in REQUIRED_COLUMNS:
        blank_rows = df.index[df[col] == ""].tolist()
        if blank_rows:
            excel_rows = [r + 2 for r in blank_rows[:10]]  # +2: header row + 1-based
            more = " ..." if len(blank_rows) > 10 else ""
            errors.append(f"Column '{col}' has {len(blank_rows)} blank value(s) "
                          f"(Excel rows {excel_rows}{more}).")

    # 4. duplicate IDs
    dupes = df.loc[df["Employee_ID"].duplicated(keep=False) & (df["Employee_ID"] != ""),
                   "Employee_ID"].unique().tolist()
    if dupes:
        shown = ", ".join(dupes[:10]) + (" ..." if len(dupes) > 10 else "")
        errors.append(f"{len(dupes)} duplicate Employee_ID value(s): {shown}.")

    if "Photo" not in df.columns:
        df["Photo"] = ""

    return (None if errors else df.reset_index(drop=True)), errors
