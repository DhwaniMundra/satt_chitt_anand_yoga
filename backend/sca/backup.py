"""Backup of the database to one JSON file in a private GitHub repository, through GitHub's contents API.

Free, versioned (every backup is a commit) and readable by the teacher. Login tokens are never backed up, so a
restore signs everyone out but keeps their accounts. Set SCA_BACKUP_REPO (owner/name) and SCA_GITHUB_TOKEN, a
fine-grained token with read and write access to that one repository's contents.
"""

import base64
import json
import urllib.error
import urllib.request

API = "https://api.github.com/repos/{repo}/contents/{path}"
JSON, RAW, OBJECT = "application/vnd.github+json", "application/vnd.github.raw+json", "application/vnd.github.object+json"


class GitHubBackup:
    def __init__(self, repo: str, token: str, path: str = "backup/sca.json") -> None:
        self.url = API.format(repo=repo, path=path)
        self.headers = {
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "sca-backend",
        }

    def _request(self, method: str, accept: str, body: dict | None = None) -> bytes | None:
        """The reply's body, or None for 404 (no backup yet)."""
        data = None if body is None else json.dumps(body).encode()
        headers = {**self.headers, "Accept": accept}
        request = urllib.request.Request(self.url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None
            raise

    def pull(self) -> dict | None:
        """The last backup, or None if there is none. Asks for the raw file: the default JSON reply leaves the
        content out once a file passes 1 MB."""
        raw = self._request("GET", RAW)
        return None if raw is None else json.loads(raw)

    def push(self, data: dict) -> None:
        """Writes `data` as a new commit, replacing the previous backup. The "object" reply gives the previous
        version's sha for files up to 100 MB."""
        meta = self._request("GET", OBJECT)
        found = None if meta is None else json.loads(meta)
        body = {
            "message": "Backup",
            "content": base64.b64encode(json.dumps(data, ensure_ascii=False, indent=1).encode()).decode(),
        }
        if found is not None:
            body["sha"] = found["sha"]
        self._request("PUT", JSON, body)
