"""Employee Lucky Draw  -  the Streamlit user interface.

Run with:  streamlit run app.py
"""
import base64
import html
import io
import time
from functools import lru_cache
from pathlib import Path

import pandas as pd
import streamlit as st

import db
import draw
from config import PHOTOS_DIR, DEFAULT_ROUNDS, DEFAULT_WINNERS_PER_ROUND
from generate_data import generate
from validation import validate_employees

st.set_page_config(page_title="Employee Lucky Draw", layout="wide")
db.init_db()

# ---------------------------------------------------------------- styling
st.markdown("""
<style>
.emp-card{border:1px solid rgba(128,128,128,.35);border-radius:14px;padding:14px 10px;
  text-align:center;margin-bottom:12px;background:rgba(128,128,128,.07);}
.emp-card.winner{border:2px solid #f5b301;background:rgba(245,179,1,.12);}
.emp-card.big{padding:22px 14px;}
.avatar{width:72px;height:72px;border-radius:50%;margin:0 auto 8px auto;display:flex;
  align-items:center;justify-content:center;color:#fff;font-weight:700;font-size:26px;
  object-fit:cover;}
.big .avatar{width:110px;height:110px;font-size:40px;}
.emp-name{font-weight:700;font-size:16px;margin:2px 0;}
.big .emp-name{font-size:22px;}
.emp-meta{font-size:13px;opacity:.8;}
.badge{display:inline-block;margin-top:6px;padding:2px 10px;border-radius:999px;
  background:#f5b301;color:#222;font-size:12px;font-weight:700;}
.countdown{font-size:96px;font-weight:800;text-align:center;padding:10px;}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------- helpers
@lru_cache(maxsize=512)
def photo_data_uri(photo: str):
    """Return an embeddable image for a photo filename, or None if not found."""
    if not photo:
        return None
    path = PHOTOS_DIR / Path(photo).name        # .name blocks '../' tricks
    if not path.is_file():
        return None
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


def initials(name: str) -> str:
    parts = name.split()
    return "".join(p[0] for p in parts[:2]).upper() or "?"


def avatar_html(name: str, photo: str) -> str:
    uri = photo_data_uri(photo or "")
    if uri:
        return f'<img class="avatar" src="{uri}">'
    hue = sum(ord(c) for c in name) * 7 % 360
    return (f'<div class="avatar" style="background:hsl({hue},55%,42%)">'
            f'{html.escape(initials(name))}</div>')


def card_html(row, winner=False, big=False, label=None) -> str:
    classes = "emp-card" + (" winner" if winner else "") + (" big" if big else "")
    badge = f'<div class="badge">{html.escape(label)}</div>' if label else ""
    # NOTE: kept on one line - indented HTML can be mistaken for code by markdown
    return (f'<div class="{classes}">{avatar_html(row["name"], row["photo_path"])}'
            f'<div class="emp-name">{html.escape(row["name"])}</div>'
            f'<div class="emp-meta">{html.escape(row["employee_id"])}</div>'
            f'<div class="emp-meta">{html.escape(row["designation"])}</div>'
            f'<div class="emp-meta">{html.escape(row["department"])}</div>{badge}</div>')


def flash(kind: str, message: str):
    st.session_state["flash"] = (kind, message)

def read_employee_file(uploaded) -> pd.DataFrame:
    """Read an uploaded .xlsx or .csv file into a table of text values."""
    name = uploaded.name.lower()
    if name.endswith(".csv"):
        try:
            # utf-8-sig also handles CSVs saved from Excel (they start with a hidden BOM mark)
            return pd.read_csv(uploaded, dtype=str, keep_default_na=False, encoding="utf-8-sig")
        except UnicodeDecodeError:
            uploaded.seek(0)                      # rewind the file and try another encoding
            return pd.read_csv(uploaded, dtype=str, keep_default_na=False, encoding="latin-1")
    return pd.read_excel(uploaded, dtype=str, engine="openpyxl")


def import_dataframe(raw: pd.DataFrame, source: str, rounds: int, winners_each: int):
    clean, errors = validate_employees(raw)
    if not errors and rounds * winners_each > len(clean):
        errors.append(f"{rounds} rounds x {winners_each} winners = {rounds * winners_each} winners, "
                      f"but the file only has {len(clean)} employees.")
    if errors:
        st.sidebar.error(f"❌ {source} was not imported:")
        for e in errors:
            st.sidebar.write(f"• {e}")
        return
    db.create_session(clean, total_rounds=rounds, winners_per_round=winners_each)
    flash("success", f"Imported {len(clean):,} employees from {source}. "
                     f"Draw: {rounds} round(s) x {winners_each} winner(s). Ready!")
    st.rerun()


# ---------------------------------------------------------------- state
session = db.get_active_session()
done = db.rounds_completed(session["session_id"]) if session else 0
total_rounds = session["total_rounds"] if session else DEFAULT_ROUNDS
per_round = session["winners_per_round"] if session else DEFAULT_WINNERS_PER_ROUND

# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("1️⃣ Draw settings")
    locked = bool(session) and done > 0
    rounds_in = int(st.number_input("Number of rounds", min_value=1, max_value=100,
                                    value=int(total_rounds), step=1, disabled=locked))
    winners_in = int(st.number_input("Winners per round", min_value=1, max_value=50,
                                     value=int(per_round), step=1, disabled=locked))
    st.caption(f"Total winners: {rounds_in * winners_in}")
    if locked:
        st.caption("🔒 Locked while a draw is in progress. Use 'Reset draw' below to change.")
    elif session and (rounds_in != total_rounds or winners_in != per_round):
        if st.button("Save settings"):
            try:
                if rounds_in * winners_in > session["initial_count"]:
                    raise ValueError(f"{rounds_in} x {winners_in} = {rounds_in * winners_in} winners, "
                                     f"but there are only {session['initial_count']} employees.")
                db.update_settings(session["session_id"], rounds_in, winners_in)
            except ValueError as exc:
                st.error(str(exc))
            else:
                flash("success", f"Settings saved: {rounds_in} round(s) x {winners_in} winner(s).")
                st.rerun()
    st.divider()

    st.header("2️⃣ Load employees")

    replace_ok = True
    if session and done > 0:
        st.warning("A draw is in progress. Importing will start a NEW draw.")
        replace_ok = st.checkbox("I understand — start a new draw")

    uploaded = st.file_uploader("Upload employee file (.xlsx or .csv)", type=["xlsx", "csv"])
    st.caption("Required columns: Employee_ID, Name, Designation, Department. "
               "Optional: Photo (file name, e.g. EMP0001.jpg).")

    if st.button("Import uploaded file", disabled=(uploaded is None or not replace_ok)):
        try:
            raw = read_employee_file(uploaded)
        except Exception as exc:
            st.error(f"Could not read this file: {exc}")
        else:
            import_dataframe(raw, f"'{uploaded.name}'", rounds_in, winners_in)

    st.divider()
    if st.button("Use 1,200 sample (fictional) employees", disabled=not replace_ok):
        import_dataframe(generate(), "the sample data", rounds_in, winners_in)

    if session:
        st.divider()
        with st.expander("⚠️ Reset draw"):
            st.caption("Deletes all winners and rounds. The employee list stays. "
                       "Only do this if your event procedure allows it.")
            sure = st.checkbox("Yes, I am authorised to reset this draw")
            if st.button("Reset draw", disabled=not sure):
                db.reset_session(session["session_id"])
                flash("success", f"Draw reset. All {session['initial_count']:,} employees are eligible again.")
                st.rerun()

# ---------------------------------------------------------------- header
st.title("🎉 Employee Lucky Draw")

if "flash" in st.session_state:
    kind, msg = st.session_state.pop("flash")
    (st.success if kind == "success" else st.error)(msg)

if not session:
    st.info("👋 Welcome! Start by loading employees from the sidebar — either upload your "
            "Excel file or click **Use sample employees** to try the app.")
    st.stop()

sid = session["session_id"]
employees = db.get_employees(sid)
eligible = db.get_eligible_ids(sid)
winners = db.get_winners(sid)
winner_ids = set(winners["Employee_ID"]) if not winners.empty else set()

# ---------------------------------------------------------------- counters
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total employees", f"{len(employees):,}")
c2.metric("Eligible remaining", f"{len(eligible):,}")
c3.metric("Winners selected", len(winner_ids))
c4.metric("Rounds completed", f"{done} / {total_rounds}")

# ---------------------------------------------------------------- draw action
if done >= total_rounds:
    st.success(f"✅ All {total_rounds} rounds are complete — {len(winner_ids)} winners selected.")
elif len(eligible) < per_round:
    st.warning(f"Not enough eligible employees left (need {per_round}, "
               f"have {len(eligible)}). The draw is disabled.")
else:
    if st.button(f"🎲 Draw Round {done + 1}", type="primary"):
        try:
            # Re-read the eligible list right now (not the one from page load)
            fresh = db.get_eligible_ids(sid)
            picked = draw.pick_winners(fresh, per_round)
            db.save_round(sid, picked)            # winners are SAVED before the animation
        except Exception as exc:
            st.error(f"The draw failed and nothing was saved: {exc}")
        else:
            box = st.empty()                      # animation only *shows* saved winners
            for n in (3, 2, 1):
                box.markdown(f'<div class="countdown">{n}</div>', unsafe_allow_html=True)
                time.sleep(0.8)
            box.empty()
            st.session_state["celebrate"] = True
            st.rerun()

if st.session_state.pop("celebrate", False):
    st.balloons()

# ---------------------------------------------------------------- latest winners
if not winners.empty:
    latest = int(winners["Round"].max())
    st.subheader(f"🏆 Round {latest} winners")
    latest_rows = winners[winners["Round"] == latest].rename(columns={
        "Employee_ID": "employee_id", "Name": "name", "Designation": "designation",
        "Department": "department", "Photo": "photo_path"})
    cards = [r for _, r in latest_rows.iterrows()]
    for i in range(0, len(cards), 4):
        cols = st.columns(min(len(cards), 4))
        for col, row in zip(cols, cards[i:i + 4]):
            col.markdown(card_html(row, winner=True, big=True, label=f"WINNER • ROUND {latest}"),
                         unsafe_allow_html=True)

# ---------------------------------------------------------------- tabs
tab_roster, tab_history, tab_export = st.tabs(["👥 Roster", "🏆 Winner history", "⬇️ Export"])

with tab_roster:
    f1, f2, f3 = st.columns([3, 2, 2])
    query = f1.text_input("Search name or ID", placeholder="e.g. Aisha or EMP0042")
    depts = ["All departments"] + sorted(employees["department"].unique())
    dept = f2.selectbox("Department", depts)
    only_eligible = f3.checkbox("Only eligible employees", value=False)

    view = employees
    if query:
        q = query.lower()
        view = view[view["name"].str.lower().str.contains(q, regex=False)
                    | view["employee_id"].str.lower().str.contains(q, regex=False)]
    if dept != "All departments":
        view = view[view["department"] == dept]
    if only_eligible:
        view = view[~view["employee_id"].isin(winner_ids)]

    PAGE = 24
    pages = max(1, -(-len(view) // PAGE))
    page = st.number_input("Page", 1, pages, 1) if pages > 1 else 1
    st.caption(f"{len(view):,} employees match • page {page} of {pages}")

    chunk = view.iloc[(page - 1) * PAGE: page * PAGE]
    rows = [r for _, r in chunk.iterrows()]
    for i in range(0, len(rows), 4):
        cols = st.columns(4)
        for col, row in zip(cols, rows[i:i + 4]):
            won = row["employee_id"] in winner_ids
            col.markdown(card_html(row, winner=won, label="🏆 Winner" if won else None),
                         unsafe_allow_html=True)

with tab_history:
    if winners.empty:
        st.info("No winners yet. Run the first round!")
    else:
        st.dataframe(winners.drop(columns=["Photo"]), hide_index=True)

with tab_export:
    if winners.empty:
        st.info("Nothing to export yet.")
    else:
        if done < total_rounds:
            st.caption(f"Only {done} of {total_rounds} rounds are complete — this export is partial.")
        export_df = winners.drop(columns=["Photo"])
        st.download_button("⬇️ Download CSV", export_df.to_csv(index=False).encode("utf-8"),
                           file_name="lucky_draw_winners.csv", mime="text/csv")
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            export_df.to_excel(writer, index=False, sheet_name="Winners")
        st.download_button("⬇️ Download Excel", buf.getvalue(),
                           file_name="lucky_draw_winners.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
