"""Where the local visualisations live (.local/visualization/, gitignored): one folder per major version, viz_<major>/,
with each version's screenshots in screens/<version>/ and its recordings and videos in tours/; build files go to work/.
No dependencies, so any script can import it."""

import re
import shutil
from pathlib import Path

LOCAL = Path(__file__).resolve().parents[1] / ".local" / "visualization"
WORK = LOCAL / "work"


def folder(version: str) -> Path:
    """The version's folder, by its major part: v0.4-two-phones -> viz_v0, v1 -> viz_v1."""
    major = re.match(r"v(\d+)", version)[1]
    return LOCAL / f"viz_v{major}"


def tours(version: str) -> Path:
    """The version's screen recordings and the videos made from them: viz_<major>/tours/."""
    return folder(version) / "tours"


def screens(version: str) -> Path:
    """The version's screenshots and small recordings: viz_<major>/screens/<version>/."""
    return folder(version) / "screens" / version


def shot(path: str) -> Path:
    """A screenshot named "<version>/<file>", for example "v0.4/01_welcome.png"."""
    version, name = path.split("/", 1)
    return screens(version) / name


def fresh_screens(version: str) -> Path:
    """An empty folder beside screens/<version>/ to shoot into, so a run never leaves that set half-made; keep_screens()
    swaps it in once the run has succeeded."""
    new = screens(version).with_name(version + ".new")
    shutil.rmtree(new, ignore_errors=True)
    new.mkdir(parents=True)
    return new


def keep_screens(version: str) -> None:
    """Swaps the run's screens in for the set before, carrying over that set's files the run did not make (the
    release's screens, say). A failed run never gets here, and the set before stays as it was."""
    old = screens(version)
    new = old.with_name(version + ".new")
    if old.exists():
        for file in old.iterdir():
            if not (new / file.name).exists():
                shutil.copy2(file, new / file.name)
        aside = old.with_name(version + ".old")
        shutil.rmtree(aside, ignore_errors=True)
        old.rename(aside)
        new.rename(old)
        shutil.rmtree(aside)
    else:
        new.rename(old)
