"""Point-in-time snapshots and the artifact mirror."""
from __future__ import annotations

import json

import pytest

from app import artifacts, snapshots
from tests.test_associations import make, noise
from tests.test_paper_tax_committee import D, N


@pytest.fixture()
def book():
    return make({"A": noise(1), "B": noise(2), "C": noise(3)})


def run_doc(d, sym, action="BUY", consensus=0.75, quorum_ok=True):
    return {"id": f"{d}:{sym}", "date": d, "symbol": sym, "decision": action, "action": action, "gate": "passed", "quorum_ok": quorum_ok, "answered": 9, "ceo": {"consensus": consensus}, "agents": []}


# ------------------------------------------------------------------- snapshots --


def test_snapshot_holds_what_was_known_that_day_and_only_that(book):
    d = D[400]
    doc = snapshots.build(book, d, [run_doc(d, "A", "SELL"), run_doc(D[399], "B", "BUY")])
    a = doc["symbols"]["A"]
    assert a["close"] == pytest.approx(book.close["A"][d]) and a["signal"] in ("BUY", "SELL", "HOLD")
    assert a["committee"] == "SELL" and a["consensus"] == 0.75 and a["committee_gate"] == "passed"
    assert "committee" not in doc["symbols"]["B"]  # B's review was yesterday, not today
    assert doc["cohesion"]["value"] is not None and set(doc["symbols"]) == {"A", "B", "C"}
    # nothing from the future can be in it: building on a truncated history gives the same numbers
    early = snapshots.build(book, D[300], [])
    assert early["symbols"]["A"]["close"] == pytest.approx(book.close["A"][D[300]])
    assert early["symbols"]["A"]["risk_score"] == snapshots.build(book, D[300], [])["symbols"]["A"]["risk_score"]


def test_low_quorum_call_is_recorded_without_an_action(book):
    d = D[400]
    doc = snapshots.build(book, d, [run_doc(d, "A", "BUY", quorum_ok=False) | {"action": None}])
    assert doc["symbols"]["A"]["committee"] is None and doc["symbols"]["A"]["committee_vote"] == "BUY"


def test_a_symbol_with_no_bar_that_day_is_left_out(book):
    book.close["C"].pop(D[400])
    assert "C" not in snapshots.build(book, D[400], [])["symbols"]


def test_take_is_idempotent_and_matrices_come_back_labelled(real_db, book):
    for i in (398, 399, 400):
        snapshots.take(book, D[i])
    snapshots.take(book, D[400])  # again: replaces, does not duplicate
    assert [s["date"] for s in real_db.list_snapshots()] == [D[398], D[399], D[400]]
    m = snapshots.matrix("close")
    assert m["dates"] == [D[398], D[399], D[400]] and m["symbols"] == ["A", "B", "C"]
    arr = snapshots.as_array(m)
    assert arr.shape == (3, 3) and arr[2, 0] == pytest.approx(book.close["A"][D[400]])
    s = snapshots.series("signal", "A")
    assert s["dates"] and set(s["values"]) <= {-1.0, 0.0, 1.0}
    assert snapshots.series("close", "NOPE")["values"] == []
    with pytest.raises(KeyError):
        snapshots.matrix("nope")


def test_committee_and_risk_codes_in_the_matrix(real_db, book, monkeypatch):
    d = D[400]
    monkeypatch.setattr(real_db, "list_all_committee_runs", lambda: [run_doc(d, "A", "SELL"), run_doc(d, "B", "BUY")])
    snapshots.take(book, d)
    m = snapshots.matrix("committee")
    row = dict(zip(m["symbols"], m["values"][0]))
    assert row == {"A": -1.0, "B": 1.0, "C": None}
    assert set(v for v in snapshots.matrix("risk_level")["values"][0] if v is not None) <= {0.0, 1.0, 2.0}
    assert snapshots.cohesion_history()["value"][0] is not None


def test_missing_dates_finds_days_the_pipeline_skipped(real_db, book):
    snapshots.take(book, D[598])
    snapshots.take(book, D[599])
    missing = snapshots.missing_dates(book, days=5)
    assert missing == D[595:598] and D[599] not in missing


def test_a_failing_association_step_still_yields_a_snapshot(book, monkeypatch):
    monkeypatch.setattr(snapshots.associations, "cohesion", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    doc = snapshots.build(book, D[400], [])
    assert doc["cohesion"] is None and doc["symbols"]


# -------------------------------------------------------------------- artifacts --


@pytest.fixture()
def dirs(tmp_path, monkeypatch):
    tr, fd = tmp_path / "training_results", tmp_path / "free_data"
    tr.mkdir()
    (fd / "fundamentals").mkdir(parents=True)
    monkeypatch.setattr(artifacts, "roots", lambda: {"training_results": tr, "free_data": fd})
    (tr / "AAPL.json").write_text(json.dumps({"fast_ma": 20}))
    (fd / "macro.json").write_text(json.dumps({"treasury": []}))
    (fd / "fundamentals" / "AAPL.json").write_text(json.dumps({"concepts": {}}))
    return tr, fd


def test_mirror_writes_only_what_changed(real_db, dirs):
    tr, fd = dirs
    first = artifacts.mirror()
    assert first["written"] == 3 and first["unchanged"] == 0 and not first["skipped"]
    assert set(real_db.list_blob_meta()) == {"training_results/AAPL.json", "free_data/macro.json", "free_data/fundamentals/AAPL.json"}
    again = artifacts.mirror()
    assert again["written"] == 0 and again["unchanged"] == 3
    (tr / "AAPL.json").write_text(json.dumps({"fast_ma": 30}))
    third = artifacts.mirror()
    assert third["written"] == 1 and json.loads(real_db.get_blob("training_results/AAPL.json")["content"]) == {"fast_ma": 30}


def test_mirror_never_lets_a_corrupt_or_oversized_file_replace_a_good_copy(real_db, dirs, monkeypatch):
    tr, _ = dirs
    artifacts.mirror()
    (tr / "AAPL.json").write_text('{"fast_ma": 3')  # half-written
    out = artifacts.mirror()
    assert out["written"] == 0 and out["skipped"][0]["name"] == "training_results/AAPL.json"
    assert json.loads(real_db.get_blob("training_results/AAPL.json")["content"]) == {"fast_ma": 20}
    monkeypatch.setattr(artifacts, "MAX_FILE_BYTES", 5)
    assert all("exceeds" in s["why"] for s in artifacts.mirror()["skipped"])


def test_restore_puts_back_missing_files_and_never_overwrites(real_db, dirs):
    tr, fd = dirs
    artifacts.mirror()
    (tr / "AAPL.json").unlink()
    (fd / "macro.json").write_text(json.dumps({"treasury": ["newer local"]}))
    out = artifacts.restore_missing()
    assert out["restored"] == ["training_results/AAPL.json"]
    assert json.loads((tr / "AAPL.json").read_text()) == {"fast_ma": 20}
    assert json.loads((fd / "macro.json").read_text()) == {"treasury": ["newer local"]}  # untouched
    assert artifacts.restore_missing()["restored"] == []


def test_restore_refuses_names_that_escape_the_storage_directories(real_db, dirs):
    real_db.put_blob("free_data/../../evil.json", "{}", "x", "now")
    real_db.put_blob("elsewhere/x.json", "{}", "x", "now")
    real_db.put_blob("/abs.json", "{}", "x", "now")
    out = artifacts.restore_missing()
    assert out["restored"] == [] and len(out["skipped"]) == 3


def test_missing_directories_are_not_an_error(real_db, tmp_path, monkeypatch):
    monkeypatch.setattr(artifacts, "roots", lambda: {"training_results": tmp_path / "nope", "free_data": tmp_path / "nada"})
    assert artifacts.mirror() == {"written": 0, "unchanged": 0, "skipped": [], "bytes": 0}
