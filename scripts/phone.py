"""Drives the app on the emulator through adb, by the text on screen: tap, type, screenshot, record; and runs the dev
backend the app talks to, with the data a tour needs.

Used by capture_tour.py and two_phone_test.py. Needs `source scripts/env.sh` first (for the project's adb and node)
and a running emulator.
"""

import contextlib
import json
import os
import re
import subprocess
import time
import urllib.request
import xml.etree.ElementTree as ET
from typing import Callable
from pathlib import Path

PACKAGE = "com.sattchittanand.yoga"
ROOT = Path(__file__).resolve().parents[1]
TEACHER_NAME = json.loads((ROOT / "content" / "studio.json").read_text(encoding="utf-8"))["teacher"]["short"]["en"]
BACKEND = "http://localhost:8000"  # the dev backend as this laptop sees it; the emulator reaches it at 10.0.2.2:8000


@contextlib.contextmanager
def dev_backend(data: Path, demo: bool, teacher_code: str = ""):
    """The dev backend on port 8000 with a new data file: the synthetic demo (scripts/seed_demo.mjs) or, without
    `demo`, an empty Sheet whose teacher signs up with `teacher_code`. Stopped on leaving."""
    try:
        urllib.request.urlopen(BACKEND, timeout=2)
        raise SystemExit("something already answers on port 8000: stop it first (scripts/demo.sh stop)")
    except OSError:
        pass
    data.unlink(missing_ok=True)
    if demo:
        subprocess.run(["node", ROOT / "scripts" / "seed_demo.mjs", data], check=True)
    env = dict(os.environ, SCA_TEACHER_CODE=teacher_code)
    server = subprocess.Popen(["node", ROOT / "scripts" / "dev_backend.mjs", data], env=env, stdout=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                urllib.request.urlopen(BACKEND, timeout=1)
                break
            except OSError:
                time.sleep(0.2)
        yield
    finally:
        server.terminate()
        server.wait(timeout=10)


def call(method: str, path: str, token: str = "", body: dict | None = None) -> dict:
    """One call to the dev backend through the envelope, as the app makes it (urllib follows the 302 with a GET).

    Raises:
        RuntimeError: if the answer's status is not 200.
    """
    envelope = json.dumps({"method": method, "path": path, "token": token, "body": body}).encode()
    request = urllib.request.Request(BACKEND, data=envelope, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as answer:
        reply = json.load(answer)
    if reply["status"] != 200:
        raise RuntimeError(f"{method} {path}: {reply}")
    return reply["body"]


def add_class(batch: str, minutes_from_now: int) -> int:
    """A 55-minute class of `batch` starting at that time (negative: under way), so the check-ins are open whatever the
    hour."""
    body = json.dumps({"batch": batch, "minutes_from_now": minutes_from_now}).encode()
    with urllib.request.urlopen(urllib.request.Request(BACKEND + "/dev/class", data=body), timeout=10) as answer:
        return json.load(answer)["id"]


def adb(*args: str, capture: bool = True) -> str:
    return subprocess.run(["adb", *args], check=True, capture_output=capture, text=True).stdout if capture else ""


def nodes() -> list[tuple[ET.Element, bool]]:
    """Every element on screen, from the accessibility tree, with whether it or a parent can be tapped."""
    adb("shell", "uiautomator", "dump", "/sdcard/ui.xml")
    xml = adb("exec-out", "cat", "/sdcard/ui.xml")
    found = []

    def walk(node: ET.Element, tappable: bool) -> None:
        tappable = tappable or node.get("clickable") == "true"
        found.append((node, tappable))
        for child in node:
            walk(child, tappable)

    walk(ET.fromstring(xml[xml.index("<"):]), False)
    return found


def center(node: ET.Element) -> tuple[int, int]:
    x1, y1, x2, y2 = map(int, re.findall(r"\d+", node.get("bounds")))
    return (x1 + x2) // 2, (y1 + y2) // 2


def find(text: str, timeout: float = 15, exact: bool = False, last: bool = False) -> ET.Element:
    """The first (or with `last`, the lowest) element whose text or description contains `text`, waiting for it
    to appear. Tappable elements win over plain text with the same words.

    Raises:
        TimeoutError: if it does not appear in time.
    """
    end = time.time() + timeout
    while True:
        matches = []
        for node, tappable in nodes():
            label = node.get("text") or node.get("content-desc") or ""
            if (label == text) if exact else (text in label):
                matches.append((tappable, node))
        if matches:
            best = [node for tappable, node in matches if tappable] or [node for _, node in matches]
            return best[-1] if last else best[0]
        if time.time() > end:
            raise TimeoutError(f"'{text}' not on screen")
        time.sleep(0.7)


def tap(text: str, exact: bool = False, timeout: float = 15, last: bool = False) -> None:
    x, y = center(find(text, timeout, exact, last))
    adb("shell", "input", "tap", str(x), str(y))
    time.sleep(0.8)


def tap_xy(x: int, y: int) -> None:
    adb("shell", "input", "tap", str(x), str(y))
    time.sleep(0.8)


def type_into(field_label: str, value: str) -> None:
    """Taps the field labelled `field_label` and types `value` (ASCII; adb cannot type Devanagari). Closes the
    keyboard and scrolls down first if the field is hidden, as a person would."""
    hide_keyboard()
    try:
        find(field_label, timeout=2)
    except TimeoutError:
        scroll_down()
    tap(field_label)
    type_text(value)


def type_text(value: str) -> None:
    """Types `value` (ASCII) into the field that has the focus."""
    escaped = "".join("\\" + ch if ch in "()&;<>|*'\"$`!?#~\\" else ch for ch in value)  # the phone's shell reads it
    adb("shell", "input", "text", escaped.replace(" ", "%s"))
    time.sleep(0.4)


def tap_under(anchor: str, label: str) -> None:
    """Taps the first `label` below the element containing `anchor` (a reaction on one item's card, say), scrolling a
    little at a time until both are on screen."""
    tap_xy(*center(under(anchor, lambda n: (n.get("text") or n.get("content-desc")) == label, label)))


def type_under(anchor: str, value: str) -> None:
    """Types `value` into the first text box below the element containing `anchor`, then closes the keyboard."""
    tap_xy(*center(under(anchor, lambda n: n.get("class") == "android.widget.EditText", "a text box")))
    type_text(value)
    hide_keyboard()


def under(anchor: str, wanted: Callable[[ET.Element], bool], what: str) -> ET.Element:
    """The first element below the one containing `anchor` that is `wanted`, scrolling a little at a time."""
    for _ in range(12):
        found = nodes()
        tops = [center(n)[1] for n, _ in found if anchor in (n.get("text") or "")]
        below = [(center(n)[1], n) for n, _ in found if tops and wanted(n) and center(n)[1] > tops[0]]
        if below:
            return min(below, key=lambda pair: pair[0])[1]
        adb("shell", "input", "swipe", "540", "1500", "540", "1000", "400")
        time.sleep(0.8)
    raise TimeoutError(f"{what} under '{anchor}' not on screen")


def back() -> None:
    adb("shell", "input", "keyevent", "KEYCODE_BACK")
    time.sleep(0.6)


def hide_keyboard() -> None:
    if "mInputShown=true" in adb("shell", "dumpsys", "input_method"):
        back()


def scroll_down() -> None:
    adb("shell", "input", "swipe", "540", "1800", "540", "700", "400")
    time.sleep(0.8)


def scroll_to_top() -> None:
    for _ in range(6):
        adb("shell", "input", "swipe", "540", "700", "540", "1900", "150")
    time.sleep(0.8)


def screenshot(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(subprocess.run(["adb", "exec-out", "screencap", "-p"], check=True, capture_output=True).stdout)


def launch(fresh: bool = False) -> None:
    """Starts the app; with `fresh`, signed out and with no chat or health notes, as on a new phone. Gemma's download
    stays: `pm clear` would delete the 2.6 GB model."""
    adb("shell", "am", "force-stop", PACKAGE)
    if fresh:
        adb("shell", "run-as", PACKAGE, "rm", "-rf", "shared_prefs/sca.xml", "files/companion")
    adb("shell", "am", "start", "-n", f"{PACKAGE}/.MainActivity")
    time.sleep(3)


def demo_mode() -> None:
    """A clean status bar for screenshots: fixed clock, full battery, no notifications."""
    adb("shell", "settings", "put", "global", "sysui_demo_allowed", "1")
    for command in (["clock", "-e", "hhmm", "0750"], ["battery", "-e", "level", "100", "-e", "plugged", "false"],
                    ["network", "-e", "wifi", "show", "-e", "level", "4"], ["notifications", "-e", "visible", "false"]):
        adb("shell", "am", "broadcast", "-a", "com.android.systemui.demo", "-e", "command", *command)


class Recording:
    """adb screenrecord in the background on the current phone; stop() pulls the mp4 to `path`."""

    def __init__(self, path: Path, remote: str = "/sdcard/tour.mp4") -> None:
        self.path, self.remote = path, remote
        self.proc = subprocess.Popen(["adb", "shell", "screenrecord", "--bit-rate", "6000000", remote])

    def stop(self) -> None:
        adb("shell", "pkill", "-INT", "screenrecord")
        self.proc.wait(timeout=20)
        time.sleep(1.5)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        adb("pull", self.remote, str(self.path))
