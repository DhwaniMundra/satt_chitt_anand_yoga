"""Passwords, login tokens and phone numbers. Standard library only."""

import hashlib
import hmac
import re
import secrets
import threading
import time

ITERATIONS = 200_000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"pbkdf2${ITERATIONS}${salt.hex()}${digest.hex()}"


def check_password(password: str, stored: str) -> bool:
    _, iterations, salt, digest = stored.split("$")
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations))
    return hmac.compare_digest(candidate.hex(), digest)


def new_token() -> str:
    return secrets.token_urlsafe(32)


def new_code(length: int = 6) -> str:
    """A short code people can read out or type: no 0/O or 1/I."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def normalize_phone(raw: str) -> str:
    """The WhatsApp number as +<country><number>, so one person always gets one account however they type it:
    "98765 43210", "098765 43210", "+91 98765 43210" and "0091 98765 43210" are the same number. A bare 10-digit
    number, or 11 digits with the trunk prefix 0, is taken as Indian (+91).

    Raises:
        ValueError: if it is not a plausible phone number.
    """
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("00"):
        digits = digits[2:]  # international prefix
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]  # Indian trunk prefix
    if len(digits) == 10:
        digits = "91" + digits
    if not 11 <= len(digits) <= 15 or digits.startswith("0"):
        raise ValueError("phone")
    return "+" + digits


class Attempts:
    """Slows down guessing: after `limit` failures for one key (a phone number, a user) within `window_s`, that key
    is refused until the window has passed. In memory: a restart forgets, which is acceptable for one laptop."""

    def __init__(self, limit: int = 5, window_s: float = 15 * 60) -> None:
        self.limit, self.window_s = limit, window_s
        self._failures: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def blocked(self, key: str) -> bool:
        with self._lock:
            recent = [t for t in self._failures.get(key, []) if time.monotonic() - t < self.window_s]
            self._failures[key] = recent
            return len(recent) >= self.limit

    def fail(self, key: str) -> None:
        with self._lock:
            self._failures.setdefault(key, []).append(time.monotonic())

    def clear(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)
