"""Where the local visualisations live (.local/visualization/, gitignored): one folder per major version, viz_<major>/,
with the final videos on top and each version's screenshots and small recordings in screens/<version>/; build files
go to work/. No dependencies, so any script can import it."""

import re
from pathlib import Path

LOCAL = Path(__file__).resolve().parents[1] / ".local" / "visualization"
WORK = LOCAL / "work"


def folder(version: str) -> Path:
    """The version's folder, by its major part: v0.4-two-phones -> viz_v0, v1 -> viz_v1."""
    major = re.match(r"v(\d+)", version)[1]
    return LOCAL / f"viz_v{major}"


def screens(version: str) -> Path:
    """The version's screenshots and small recordings: viz_<major>/screens/<version>/."""
    return folder(version) / "screens" / version


def shot(path: str) -> Path:
    """A screenshot named "<version>/<file>", for example "v0.4/01_welcome.png"."""
    version, name = path.split("/", 1)
    return screens(version) / name
