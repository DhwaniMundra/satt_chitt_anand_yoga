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


class DevBackend:
    """The dev backend on port 8000, serving its Sheet from `data`, which it saves after every change: stopped and
    started again, it goes on where it was (and the Sheet can be edited by hand in between)."""

    def __init__(self, data: Path, teacher_code: str) -> None:
        self.data = data
        self.env = dict(os.environ, SCA_TEACHER_CODE=teacher_code)
        self.server: subprocess.Popen | None = None

    def start(self) -> None:
        self.server = subprocess.Popen(["node", ROOT / "scripts" / "dev_backend.mjs", self.data], env=self.env, stdout=subprocess.DEVNULL)
        for _ in range(50):
            try:
                urllib.request.urlopen(BACKEND, timeout=1)
                return
            except OSError:
                time.sleep(0.2)

    def stop(self) -> None:
        if self.server:
            self.server.terminate()
            self.server.wait(timeout=10)
            self.server = None


@contextlib.contextmanager
def dev_backend(data: Path, demo: bool, teacher_code: str = ""):
    """The dev backend on port 8000 with a new data file: the synthetic demo (scripts/seed_demo.mjs) or, without
    `demo`, an empty Sheet whose teacher signs up with `teacher_code`. Gives the DevBackend; stopped on leaving."""
    try:
        urllib.request.urlopen(BACKEND, timeout=2)
        raise SystemExit("something already answers on port 8000: stop it first (scripts/demo.sh stop)")
    except OSError:
        pass
    data.unlink(missing_ok=True)
    if demo:
        subprocess.run(["node", ROOT / "scripts" / "seed_demo.mjs", data], check=True)
    backend = DevBackend(data, teacher_code)
    backend.start()
    try:
        yield backend
    finally:
        backend.stop()


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


def join_class(phone: str, starts_at: str, mood: int) -> int:
    """Has the student with this number join their batch's class that began at `starts_at` (ISO, UTC), as if they had
    checked in before it with `mood`, so they can say how it went."""
    body = json.dumps({"phone": phone, "starts_at": starts_at, "mood": mood}).encode()
    with urllib.request.urlopen(urllib.request.Request(BACKEND + "/dev/joined", data=body), timeout=10) as answer:
        return json.load(answer)["session_id"]


def trouble(path: str | None = None, times: int = 1, **kind) -> None:
    """The next `times` calls to `path` ("*": any) meet trouble on the dev backend: drop=True, the call runs but its
    answer is lost; status=503, html=True, an error page instead, the call not run; refuse="unknown_item", the server's
    refusal (a 400 with that detail), the call not run; delay_ms=3000, a slow answer. With no path, the troubles still
    waiting go."""
    body = json.dumps({"path": path, "times": times, **kind} if path else {}).encode()
    urllib.request.urlopen(urllib.request.Request(BACKEND + "/dev/trouble", data=body), timeout=10).read()


def adb(*args: str, capture: bool = True) -> str:
    return subprocess.run(["adb", *args], check=True, capture_output=capture, text=True).stdout if capture else ""


def hierarchy() -> str:
    """The screen's accessibility tree as uiautomator dumps it: every element in view, with its bounds clipped to what
    shows."""
    adb("shell", "uiautomator", "dump", "/sdcard/ui.xml")
    xml = adb("exec-out", "cat", "/sdcard/ui.xml")
    return xml[xml.index("<"):]


def nodes() -> list[tuple[ET.Element, bool]]:
    """Every element on screen, from the accessibility tree, with whether it or a parent can be tapped."""
    found = []

    def walk(node: ET.Element, tappable: bool) -> None:
        tappable = tappable or node.get("clickable") == "true"
        found.append((node, tappable))
        for child in node:
            walk(child, tappable)

    walk(ET.fromstring(hierarchy()), False)
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


def find_scrolling(text: str, exact: bool = False) -> ET.Element:
    """The element showing `text`, scrolling down until it is on screen. The keyboard closes first, as the swipe would
    land on it.

    Raises:
        TimeoutError: if it is not there by the end of the page.
    """
    for _ in range(12):
        try:
            return find(text, timeout=1.5, exact=exact)
        except TimeoutError:
            hide_keyboard()
            scroll_down()
    raise TimeoutError(f"'{text}' not on screen")


def tap_scrolling(text: str, exact: bool = False) -> None:
    """Taps `text`, scrolling down until it is on screen."""
    find_scrolling(text, exact)
    tap(text, exact=exact)


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


# ---- a scrolling list, framed so that its edges cut through nothing ----

GAP = 31  # the lists' 12 dp between items, at the phone's 2.625 pixels to the dp
SLOP = 21  # Compose takes the first 8 dp of a drag to start it, so a swipe moves the list that much less


def bounds(node: ET.Element) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = map(int, re.findall(r"\d+", node.get("bounds")))
    return x1, y1, x2, y2


def label(node: ET.Element) -> str:
    return node.get("text") or node.get("content-desc") or ""


def scroller(root: ET.Element) -> ET.Element | None:
    """The scrolling list on screen, the tallest if there are more than one."""
    lists = [n for n in root.iter() if n.get("scrollable") == "true"]
    return max(lists, key=lambda n: bounds(n)[3] - bounds(n)[1]) if lists else None


def parts(view: ET.Element) -> list[tuple[ET.Element, ET.Element, ET.Element]]:
    """What is in the list, as (element, item, row): `item` is the list's child it is in (a card, a heading), and `row`
    the outermost tappable element in that item holding it, or else the item."""
    found = []

    def walk(node: ET.Element, item: ET.Element, row: ET.Element) -> None:
        if row is item and node is not item and node.get("clickable") == "true":
            row = node
        found.append((node, item, row))
        for child in node:
            walk(child, item, row)

    for item in view:
        walk(item, item, item)
    return found


def is_card(node: ET.Element, item: ET.Element) -> bool:
    """A card is one of the list's items that is a box (a View), with its words in it or merged into it; a heading or
    a line of text is a TextView."""
    return node is item and node.get("class") == "android.view.View"


TOUCH, PAD = 126, 21  # 48 dp, the least a tappable element takes; a chip or a text button draws 8 dp inside it


def drawn(node: ET.Element, y1: int, y2: int, top: int = -1, bottom: int = 1 << 20) -> tuple[int, int] | None:
    """What shows of an element, top to bottom, given its bounds (clipped at `top` or `bottom` in a dump): a tappable box
    with no words of its own (a chip, a button) draws 8 dp inside the 48 dp it takes for a finger; a taller one is a
    row, whose words and buttons count instead (None)."""
    if node.get("clickable") != "true" or label(node) or node.get("class") != "android.view.View":
        return y1, y2
    words = [bounds(n) for n in node.iter() if label(n)]
    if y2 >= bottom and y2 - y1 < TOUCH:  # cut: a box is the finger's 48 dp, its words in the middle; a row's start at its top
        return None if words and words[0][1] - y1 < 25 else (y1 + PAD, y1 + TOUCH - PAD)
    if y1 <= top and y2 - y1 < TOUCH:
        return None if words and y2 - words[-1][3] < 25 else (y2 - TOUCH + PAD, y2 - PAD)
    if abs(y2 - y1 - TOUCH) <= 3:
        return y1 + PAD, y2 - PAD
    return None if y2 - y1 > TOUCH else (y1, y2)


def cut_at_edges(xml: str) -> list[str]:
    """What the edges of the scrolling list in `xml` (a dump) cut through, under the status bar and above the tab bar: at
    the top, an item (a card, a heading) or anything in one; at the bottom, anything but a card, which may go on below.
    A cut element shows in the dump clipped to the edge. One line for each row cut."""
    view = scroller(ET.fromstring(xml))
    if view is None:
        return []
    _, top, _, bottom = bounds(view)
    cut = {}
    for node, item, row in parts(view):
        _, y1, _, y2 = bounds(node)
        if node is not item:
            shows = drawn(node, y1, y2, top, bottom)
            if shows is None:
                continue
            y1, y2 = shows
        if y1 <= top < y2 or (y1 < bottom <= y2 and not is_card(node, item)):
            words = next((label(n) for n in row.iter() if label(n)), "")
            cut.setdefault(id(row), f"the {'top' if y1 <= top else 'bottom'} edge cuts {row.get('class').split('.')[-1]} "
                                    f"{row.get('bounds')} '{words[:40]}'")
    return list(cut.values())


def drag(move: int) -> None:
    """Moves the list on screen up by `move` pixels (down, if negative), as a finger would: fast for a long way, which
    may carry on a little, and slowly for a short one, which stops where the finger does. The finger goes down in the
    list's margin, beside the cards, so it never lands on a field or a button."""
    while move:
        step = max(-1600, min(1600, move))
        move -= step
        finger = step + (SLOP if step > 0 else -SLOP)
        duration = abs(step) * 3 if abs(step) > 300 else max(1500, abs(step) * 12)
        adb("shell", "input", "swipe", "75", str(1130 + finger // 2), "75", str(1130 - finger // 2), str(duration))
        time.sleep(1)


class Layout:
    """The scrolling list on screen, put together from dumps at different places in it, at heights in the list: 0 is
    where the top edge was at the first dump. Items are its cards and headings; elements, everything else in it."""

    def __init__(self) -> None:
        self.items: list[list[int]] = []  # [y1, y2, x1, x2], each the union of its parts seen
        self.elements: list[dict] = []
        self.scrolls: list[int] = []  # where the top edge was at each dump
        self.height = 0

    def add(self, expect: int) -> int:
        """Dumps the screen, works out where in the list the top edge is (near `expect`) from what it has seen before,
        and adds what is in view. Returns where the top edge is."""
        view = scroller(ET.fromstring(hierarchy()))
        _, top, _, bottom = bounds(view)
        self.height = bottom - top
        seen = []
        for node, item, _ in parts(view):
            x1, y1, x2, y2 = bounds(node)
            seen.append(dict(key=(node.get("class"), label(node), x1, x2), x1=x1, x2=x2, y1=y1 - top, y2=y2 - top,
                             whole=top < y1 and y2 < bottom, card=is_card(node, item), item=node is item,
                             tap=node.get("clickable") == "true", node=node))
        at = self.locate(seen, expect) if self.elements else expect
        self.scrolls.append(at)
        for e in seen:
            e["y1"] += at
            e["y2"] += at
            if e["item"]:
                same = [i for i in self.items if i[2:] == [e["x1"], e["x2"]] and i[0] <= e["y2"] and e["y1"] <= i[1]]
                if same:
                    same[0][0], same[0][1] = min(same[0][0], e["y1"]), max(same[0][1], e["y2"])
                else:
                    self.items.append([e["y1"], e["y2"], e["x1"], e["x2"]])
            if not e["card"]:
                same = [o for o in self.elements if o["key"] == e["key"] and o["y1"] <= e["y2"] and e["y1"] <= o["y2"]]
                if same:
                    same[0]["y1"], same[0]["y2"] = min(same[0]["y1"], e["y1"]), max(same[0]["y2"], e["y2"])
                else:
                    self.elements.append(e)
        return at

    def locate(self, seen: list[dict], expect: int) -> int:
        """Where the top edge is: the place most of the labelled elements in view agree on, from where they were seen.
        Only words that show once, in view and in all seen so far (a name, not a "See all" on every card), count."""
        def once(entries: list[dict]) -> dict:
            keys = [e["key"] for e in entries]
            return {e["key"]: e for e in entries if e["key"][1] and keys.count(e["key"]) == 1}

        known = once(self.elements)
        votes: dict[int, int] = {}
        for key, e in once([e for e in seen if e["whole"]]).items():
            if key in known:
                at = known[key]["y1"] - e["y1"]
                votes[at] = votes.get(at, 0) + 1
        if not votes:  # only words shown more than once: the places near where the list should be
            for e in seen:
                for o in self.elements:
                    if e["whole"] and e["key"][1] and o["key"] == e["key"] and abs(o["y1"] - e["y1"] - expect) <= 400:
                        votes[o["y1"] - e["y1"]] = votes.get(o["y1"] - e["y1"], 0) + 1
        if not votes:
            raise RuntimeError("nothing in view was seen before")
        near = lambda at: sum(n for other, n in votes.items() if abs(other - at) <= 2)  # noqa: E731
        return max(votes, key=lambda at: (near(at), -abs(at - expect)))

    def place(self, start: str | None, through: str) -> int:
        """Where the top edge should be: see frame()."""
        labelled = sorted((e for e in self.elements if e["key"][1]), key=lambda e: e["y1"])
        if start is None:
            head = min(i[0] for i in self.items)
            prefer = min(self.scrolls)
        else:
            text = next(e for e in labelled if start in e["key"][1])
            head = next(i[0] for i in self.items if i[0] <= text["y1"] and text["y2"] <= i[1])
            above = [i[1] for i in self.items if i[1] <= head]
            prefer = head - min(GAP, head - max(above)) if above else head - GAP
        last = next((e for e in labelled if through in e["key"][1] and e["y1"] >= head), None)
        if last is None:
            print(f"frame: '{through}' not found below '{start}'")
            return prefer
        rows = [e for e in self.elements if e["tap"] and e["y1"] <= last["y1"] and last["y2"] <= e["y2"] and e["y1"] >= head
                and e["x1"] <= last["x1"] and last["x2"] <= e["x2"]]
        item = next((i for i in self.items if i[0] <= last["y1"] and last["y2"] <= i[1]), [last["y1"], last["y2"]])
        begin, end = (min(e["y1"] for e in rows), max(e["y2"] for e in rows)) if rows else (item[0], item[1])
        h = self.height

        shows = [drawn(e["node"], e["y1"], e["y2"]) for e in self.elements]
        shows = [extent for extent in shows if extent]

        def clean(s: int) -> bool:
            return not any(i[0] < s < i[1] for i in self.items) and not any(y1 < s + h < y2 for y1, y2 in shows)

        span = range(min(self.scrolls), max(self.scrolls) + 1)
        ok = {s: clean(s) for s in span}
        for keep_head in (True, False):  # the start in view if it can be, else only the row
            # Clean a few pixels either side as well if it can be, since the list may stop a pixel or two off.
            for room in (4, 3, 2, 1, 0):
                fits = [s for s in span if s + h >= end and s <= (head if keep_head else begin)
                        and all(ok.get(t, True) for t in range(s - room, s + room + 1))]
                if fits:
                    return min(fits, key=lambda s: (abs(s - prefer), s))
        print(f"frame: no place for '{start}' to '{through}' with clean edges")
        return prefer


def frame(start: str | None, through: str) -> None:
    """Scrolls the list on screen so it begins with the item (a card, a heading) holding `start`, one list gap below
    the top edge (with no `start`, at the top of the list), and shows everything down to the row holding `through`
    (the tappable element holding it, else its item). Where an edge would cut through something there, it scrolls the
    least it must so that neither does: the top edge falls between items, the bottom one between elements, a card
    going on below it. If no such place keeps the start in view, it gives up the start before the row.

    It measures the list around there (a dump here, a screenful above and one below), then moves in swipes, measuring
    again and correcting."""
    scroll_to_top()
    if start is not None:
        for _ in range(12):
            try:
                find(start, timeout=1.5)
                break
            except TimeoutError:
                scroll_down()
        drag(center(find(start))[1] - 400)
    layout = Layout()
    at = layout.add(0)
    if start is not None:
        drag(-1000)
        at = layout.add(at - 1000)
    drag(1200 - at)  # a screenful below the first dump, overlapping it
    at = layout.add(1200)
    target = layout.place(start, through)
    for _ in range(5):
        if abs(at - target) <= 1:
            return
        drag(target - at)
        at = layout.add(target)
    print(f"frame: '{start}' to '{through}' stopped {at - target} px from its place")


def screenshot(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(subprocess.run(["adb", "exec-out", "screencap", "-p"], check=True, capture_output=True).stdout)


def launch(fresh: bool = False) -> None:
    """Starts the app; with `fresh`, signed out and with no chat or health notes, as on a new phone. A debug build
    keeps Gemma's download: `pm clear` would delete the 2.6 GB model. A release build lets no one in with run-as, so
    it is cleared whole."""
    adb("shell", "am", "force-stop", PACKAGE)
    if fresh and debuggable():
        adb("shell", "run-as", PACKAGE, "rm", "-rf", "shared_prefs/sca.xml", "files/companion")
    elif fresh:
        adb("shell", "pm", "clear", PACKAGE)
    adb("shell", "am", "start", "-n", f"{PACKAGE}/.MainActivity")
    time.sleep(3)


def debuggable() -> bool:
    """Whether the app on the phone is a debug build."""
    return "DEBUGGABLE" in adb("shell", "dumpsys", "package", PACKAGE)


def install(apk: Path) -> None:
    """Installs `apk` over the app on the phone, or in its place when the one there is signed with another key (a
    release build after a debug one, say)."""
    done = subprocess.run(["adb", "install", "-r", str(apk)], capture_output=True, text=True)
    if "INSTALL_FAILED_UPDATE_INCOMPATIBLE" in done.stdout + done.stderr:
        adb("uninstall", PACKAGE)
        adb("install", str(apk))
    elif done.returncode:
        raise RuntimeError(f"adb install {apk}: {done.stdout}{done.stderr}")


def resumed() -> str:
    """The activity in front, as package/.Class: the app's com.sattchittanand.yoga/.MainActivity, Android's share sheet
    (com.android.intentresolver/...), Chrome."""
    found = re.search(r"topResumedActivity=ActivityRecord\{\S+ \S+ (\S+)", adb("shell", "dumpsys", "activity", "activities"))
    return found[1] if found else ""


def clear_log() -> None:
    adb("logcat", "-c")


def opened() -> list[str]:
    """The links the phone has opened since clear_log(), as Android logs them: the scheme and host, and "..." for the
    rest, which it keeps out of the log ("https://meet.google.com/...")."""
    return re.findall(r"act=android\.intent\.action\.VIEW dat=(\S+)", adb("logcat", "-d", "-s", "ActivityTaskManager:I"))


def demo_mode() -> None:
    """A clean status bar for screenshots: a fixed clock, a full battery, full Wi-Fi with no "!" (an emulator's network
    counts as unvalidated), no mobile signal and no notifications."""
    adb("shell", "settings", "put", "global", "sysui_demo_allowed", "1")
    for command in (["exit"], ["enter"]):  # afresh; the bar takes a moment to enter demo mode, or it drops what follows
        adb("shell", "am", "broadcast", "-a", "com.android.systemui.demo", "-e", "command", *command)
        time.sleep(1)
    for command in (["clock", "-e", "hhmm", "0750"], ["battery", "-e", "level", "100", "-e", "plugged", "false"],
                    ["network", "-e", "wifi", "show", "-e", "level", "4", "-e", "fully", "true"], ["network", "-e", "mobile", "hide"],
                    ["notifications", "-e", "visible", "false"]):
        adb("shell", "am", "broadcast", "-a", "com.android.systemui.demo", "-e", "command", *command)


class Recording:
    """adb screenrecord in the background on the current phone; stop() pulls the mp4 to `path`."""

    def __init__(self, path: Path, remote: str = "/sdcard/tour.mp4") -> None:
        self.path, self.remote = path, remote
        self.proc = subprocess.Popen(["adb", "shell", "screenrecord", "--bit-rate", "6000000", remote])

    def stop(self) -> None:
        # Not checked: screenrecord ends by itself after 3 minutes, and a longer part has nothing left to stop.
        subprocess.run(["adb", "shell", "pkill", "-INT", "screenrecord"], capture_output=True)
        self.proc.wait(timeout=20)
        time.sleep(1.5)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        adb("pull", self.remote, str(self.path))
