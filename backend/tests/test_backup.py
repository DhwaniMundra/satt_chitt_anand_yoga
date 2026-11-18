"""The GitHub backup against a fake contents API, and a restore into an empty database."""

import base64
import io
import json
import urllib.error

from sca import db
from sca.backup import GitHubBackup


class FakeGitHub:
    """Stands in for urllib.request.urlopen and keeps one file."""

    def __init__(self):
        self.content = None
        self.sha = 0
        self.calls = []

    def __call__(self, request, timeout):
        self.calls.append((request.get_method(), request.full_url, request.headers.get("Authorization")))
        if request.get_method() == "GET":
            if self.content is None:
                raise urllib.error.HTTPError(request.full_url, 404, "Not Found", {}, None)
            if request.headers.get("Accept") == "application/vnd.github.raw+json":
                return io.BytesIO(base64.b64decode(self.content))  # the file itself, at any size
            # Like GitHub's "object" reply for a file over 1 MB: the sha, but no content.
            return io.BytesIO(json.dumps({"content": "", "encoding": "none", "sha": str(self.sha)}).encode())
        body = json.loads(request.data)
        assert body.get("sha") == (str(self.sha) if self.content else None)
        self.content, self.sha = body["content"], self.sha + 1
        return io.BytesIO(b"{}")


def test_push_then_restore(tmp_path, monkeypatch):
    fake = FakeGitHub()
    monkeypatch.setattr("urllib.request.urlopen", fake)
    backup = GitHubBackup("someone/private-repo", "tok")
    assert backup.pull() is None

    source = db.connect(tmp_path / "a.sqlite3")
    source.execute(
        "INSERT INTO users (name, phone, role, status, pw_hash, created_at) VALUES ('Asha', '+919000000002', 'student', 'approved', 'x', 'now')"
    )
    source.execute("INSERT INTO tokens (token, user_id, created_at) VALUES ('secret', 1, 'now')")
    db.set_setting(source, "group_code", "ABC123")
    backup.push(db.export_rows(source))
    backup.push(db.export_rows(source))  # the second push must send the sha of the first

    saved = json.loads(base64.b64decode(fake.content))
    assert "tokens" not in saved and saved["users"][0]["name"] == "Asha"
    target = db.connect(tmp_path / "b.sqlite3")
    db.import_rows(target, backup.pull())
    assert db.get_setting(target, "group_code") == "ABC123" and not db.is_empty(target)
    assert all(url.endswith("/repos/someone/private-repo/contents/backup/sca.json") and auth == "Bearer tok" for _, url, auth in fake.calls)


def test_restore_over_settings_made_at_start_up(tmp_path):
    target = db.connect(tmp_path / "c.sqlite3")
    db.set_setting(target, "group_code", "NEW111")  # made by the first start, before any user existed
    db.import_rows(target, {"settings": [{"key": "group_code", "value": "OLD222"}]})
    assert db.get_setting(target, "group_code") == "OLD222"
