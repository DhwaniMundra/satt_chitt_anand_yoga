"""Records fastapi.json: scenario.json played against the FastAPI server at a frozen moment (18 Nov 2026, 03:00 UTC).

The record was made on 18 Nov 2026 from the FastAPI backend of the on-device branch (commit 4013877, which has the
routes for Gemma on the phone), with that backend unpacked next to this file as ./backend:

    git archive origin/feature/on-device-gemma backend | tar -x -C appsscript/test/parity
    backend/.venv/bin/python appsscript/test/parity/record_fastapi.py

The FastAPI server is being retired; parity.test.mjs keeps replaying the record against the Apps Script backend.
"""
import json
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "backend"))

from fastapi.testclient import TestClient  # noqa: E402

from sca import db, studio  # noqa: E402
from sca.app import Config, create_app  # noqa: E402

FIXED = datetime(2026, 11, 18, 3, 0, 0, tzinfo=UTC)
db.now = lambda: FIXED
studio.now = lambda: FIXED


def main() -> None:
    steps = json.loads((HERE / "scenario.json").read_text())
    out = []
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "t.sqlite3"
        config = Config(db_path=path, gemma="off", model_path=Path(tmp) / "none", cache_dir=Path(tmp), teacher_code="TEACH123")
        with TestClient(create_app(config)) as client:
            db.set_setting(db.connect(path), "group_code", "GRP234")
            tokens = {}
            for step in steps:
                if "do" in step:
                    act(path, step)
                    continue
                method, route, *rest = step["call"]
                query = rest[0] if len(rest) > 0 else {}
                body = rest[1] if len(rest) > 1 else None
                who = rest[2] if len(rest) > 2 else None
                headers = {"Authorization": "Bearer " + tokens.get(who, who)} if who else {}
                r = client.request(method, route, params=query, json=body, headers=headers)
                payload = r.json()
                if "save" in step and r.status_code == 200:
                    tokens[step["save"]] = payload["token"]
                for key in ["token"] + step.get("normalize", []):  # random each run
                    if isinstance(payload, dict) and key in payload:
                        payload[key] = "<varies>"
                out.append({"status": r.status_code, "body": payload})
    lines = ",\n".join(json.dumps(c, ensure_ascii=False) for c in out)
    (HERE / "fastapi.json").write_text("[\n" + lines + "\n]\n")
    print(len(out), "calls recorded")


def act(path: Path, step: dict) -> None:
    """The rows the Python tests write straight into SQLite: class_started() and attend()."""
    conn = db.connect(path)
    if step["do"] == "class_started":
        conn.execute("INSERT INTO class_sessions (class_key, starts_at, duration_min, updated_at) VALUES ('hatha', ?, 55, ?)",
                     (db.iso(db.now() - timedelta(minutes=step["minutes"])), db.iso(db.now())))
    else:
        start = (db.now() - timedelta(days=step["days"])).replace(second=0, microsecond=0)
        conn.execute("INSERT OR IGNORE INTO class_sessions (class_key, starts_at, duration_min, updated_at) VALUES (?, ?, 55, ?)",
                     (step["class"], db.iso(start), db.iso(start)))
        sid = conn.execute("SELECT id FROM class_sessions WHERE starts_at = ?", (db.iso(start),)).fetchone()[0]
        conn.execute("INSERT INTO checkins VALUES (?, ?, 'before', ?, ?)", (step["user"], sid, step["before"], db.iso(start)))
        if step["after"] is not None:
            conn.execute("INSERT INTO checkins VALUES (?, ?, 'after', ?, ?)", (step["user"], sid, step["after"], db.iso(start)))
    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
