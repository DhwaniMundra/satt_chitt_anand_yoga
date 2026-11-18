"""Drives the app on the emulator through adb, by the text on screen: tap, type, screenshot, record.

Used by capture_tour.py to take the same screenshots after every iteration. Needs `source scripts/env.sh` first
(for the project's adb) and a running emulator.
"""

import re
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path

PACKAGE = "com.sattchittanand.yoga"


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
    escaped = "".join("\\" + ch if ch in "()&;<>|*'\"$`!?#~\\" else ch for ch in value)  # the phone's shell reads it
    adb("shell", "input", "text", escaped.replace(" ", "%s"))
    time.sleep(0.4)


def back() -> None:
    adb("shell", "input", "keyevent", "KEYCODE_BACK")
    time.sleep(0.6)


def hide_keyboard() -> None:
    if "mInputShown=true" in adb("shell", "dumpsys", "input_method"):
        back()


def scroll_down() -> None:
    adb("shell", "input", "swipe", "540", "1800", "540", "700", "400")
    time.sleep(0.8)


def screenshot(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(subprocess.run(["adb", "exec-out", "screencap", "-p"], check=True, capture_output=True).stdout)


def launch(clear: bool = False) -> None:
    if clear:
        adb("shell", "pm", "clear", PACKAGE)
    adb("shell", "am", "force-stop", PACKAGE)
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
