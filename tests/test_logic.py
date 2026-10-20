"""Automated checks for the PRD acceptance tests.  Run with:  python -m pytest -q"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import db
import draw
from generate_data import generate
from validation import validate_employees


@pytest.fixture
def dbpath(tmp_path):
    p = tmp_path / "test.db"
    db.init_db(p)
    return p


def test_sample_data_is_valid_and_1200():
    clean, errors = validate_employees(generate())
    assert errors == [] and len(clean) == 1200


def test_missing_column_rejected():
    _, errors = validate_employees(generate().drop(columns=["Department"]))
    assert errors and "Department" in errors[0]


def test_duplicate_ids_rejected():
    df = generate()
    df.loc[1, "Employee_ID"] = df.loc[0, "Employee_ID"]
    _, errors = validate_employees(df)
    assert any("duplicate" in e.lower() for e in errors)


def test_blank_values_rejected():
    df = generate()
    df.loc[5, "Name"] = ""
    _, errors = validate_employees(df)
    assert any("blank" in e.lower() for e in errors)


def test_five_rounds_ten_unique_winners(dbpath):
    clean, _ = validate_employees(generate())
    sid = db.create_session(clean, dbpath)
    expected = 1200
    for n in range(1, 6):
        picked = draw.pick_winners(db.get_eligible_ids(sid, dbpath), 2)
        assert db.save_round(sid, picked, dbpath) == n
        expected -= 2
        assert len(db.get_eligible_ids(sid, dbpath)) == expected
    w = db.get_winners(sid, dbpath)
    assert len(w) == 10 and w["Employee_ID"].nunique() == 10
    assert expected == 1190
    with pytest.raises(ValueError):                       # round 6 not allowed
        db.save_round(sid, draw.pick_winners(db.get_eligible_ids(sid, dbpath), 2), dbpath)


def test_state_survives_reconnect(dbpath):
    clean, _ = validate_employees(generate())
    sid = db.create_session(clean, dbpath)
    for _ in range(2):
        db.save_round(sid, draw.pick_winners(db.get_eligible_ids(sid, dbpath), 2), dbpath)
    assert db.get_active_session(dbpath)["session_id"] == sid
    assert len(db.get_winners(sid, dbpath)) == 4
    assert len(db.get_eligible_ids(sid, dbpath)) == 1196


def test_failed_save_leaves_nothing_behind(dbpath):
    clean, _ = validate_employees(generate())
    sid = db.create_session(clean, dbpath)
    db.save_round(sid, ["EMP0001", "EMP0002"], dbpath)
    with pytest.raises(Exception):                        # EMP0001 already won
        db.save_round(sid, ["EMP0003", "EMP0001"], dbpath)
    assert db.rounds_completed(sid, dbpath) == 1          # no partial round
    assert len(db.get_winners(sid, dbpath)) == 2
    assert "EMP0003" in db.get_eligible_ids(sid, dbpath)


def test_cannot_draw_with_one_left():
    with pytest.raises(ValueError):
        draw.pick_winners(["EMP0001"], 2)


def test_reset_restores_pool(dbpath):
    clean, _ = validate_employees(generate())
    sid = db.create_session(clean, dbpath)
    db.save_round(sid, ["EMP0001", "EMP0002"], dbpath)
    db.reset_session(sid, dbpath)
    assert len(db.get_eligible_ids(sid, dbpath)) == 1200
