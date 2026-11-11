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


class GitHubBackup:
    def __init__(self, repo: str, token: str, path: str = "backup/sca.json") -> None:
        self.url = API.format(repo=repo, path=path)
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "sca-backend",
        }

    def _request(self, method: str, body: dict | None = None) -> dict | None:
        """The JSON reply, or None for 404 (no backup yet)."""
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(self.url, data=data, headers=self.headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None
            raise

    def pull(self) -> dict | None:
        """The last backup, or None if there is none."""
        found = self._request("GET")
        return None if found is None else json.loads(base64.b64decode(found["content"]))

    def push(self, data: dict) -> None:
        """Writes `data` as a new commit, replacing the previous backup."""
        found = self._request("GET")
        body = {
            "message": "Backup",
            "content": base64.b64encode(json.dumps(data, ensure_ascii=False, indent=1).encode()).decode(),
        }
        if found is not None:
            body["sha"] = found["sha"]
        self._request("PUT", body)
