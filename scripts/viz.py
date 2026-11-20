"""Where the local visualisations live (.local/visualization/, gitignored): viz_v0/ for the prototypes (v0.1 to v0.7)
and viz_v0.9/ for the practice tracker (v0.9 on), each with every version's screenshots in screens/<version>/ and its
recordings and videos in tours/; build files go to work/. No dependencies, so any script can import it."""

import re
import shutil
from pathlib import Path
from typing import Callable

LOCAL = Path(__file__).resolve().parents[1] / ".local" / "visualization"
WORK = LOCAL / "work"
TRACKER = (0, 9)  # the version the practice tracker began with


def folder(version: str) -> Path:
    """The version's folder: v0, v0.4 and v0.4-two-phones -> viz_v0; v0.9, v0.9_first-two-phones and v0.9.1-two-phones
    -> viz_v0.9."""
    number = re.match(r"v(\d+)(?:\.(\d+))?", version)
    return LOCAL / ("viz_v0.9" if (int(number[1]), int(number[2] or 0)) >= TRACKER else "viz_v0")


def tours(version: str) -> Path:
    """The version's screen recordings and the videos made from them: <its folder>/tours/."""
    return folder(version) / "tours"


def screens(version: str) -> Path:
    """The version's screenshots and small recordings: <its folder>/screens/<version>/."""
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


def keep_screens(version: str, carry: Callable[[str], bool] = lambda name: True) -> None:
    """Swaps the run's screens in for the set before, carrying over that set's files the run did not make and `carry`
    accepts by name (the release's screens, say). A failed run never gets here, and the set before stays as it was."""
    old = screens(version)
    new = old.with_name(version + ".new")
    if old.exists():
        for file in old.iterdir():
            if not (new / file.name).exists() and carry(file.name):
                shutil.copy2(file, new / file.name)
        aside = old.with_name(version + ".old")
        shutil.rmtree(aside, ignore_errors=True)
        old.rename(aside)
        new.rename(old)
        shutil.rmtree(aside)
    else:
        new.rename(old)
