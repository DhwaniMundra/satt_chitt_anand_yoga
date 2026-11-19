"""Writes the list of Gemma 4 tokens that Marathi answers may not use: every token holding a letter or a digit that is
neither Latin nor Devanagari. Without the ban, Marathi answers now and then slip in a Japanese, Korean or Arabic word,
or Bengali digits in a time.

LiteRT-LM for Android cannot turn a token id back into text, so the app gets the list made here from the same model
file, as a bitset in android/app/src/main/assets/gemma4_foreign_tokens.bin: bit i (byte i / 8, lowest bit first) is
set when token i is banned, 32 KB for Gemma 4's 262,144 tokens. Run it again only if the model file changes.

Needs LiteRT-LM for Python, version 0.18.1 (the version of the app's runtime), and the Gemma 4 E2B file:

    uv run --with litert-lm==0.18.1 python scripts/foreign_tokens.py \
        models/gemma-4-E2B-it/gemma-4-E2B-it.litertlm android/app/src/main/assets/gemma4_foreign_tokens.bin
"""

import itertools
import sys
import tempfile
import unicodedata
from pathlib import Path

import litert_lm

VOCABULARY = 262_144  # Gemma 4


def is_foreign(text: str) -> bool:
    """Whether `text` holds a letter or a digit from a script other than Latin and Devanagari: 0-9 and ०-९ are fine,
    Bengali ০-৯ or Arabic ٠-٩ are not. Punctuation, symbols and marks never count."""
    return any((ch.isalpha() or ch.isdecimal())
               and not ("0" <= ch <= "9" or unicodedata.name(ch, "").startswith(("LATIN", "DEVANAGARI")))
               for ch in text)


def foreign_tokens(model: Path) -> list[int]:
    with tempfile.TemporaryDirectory() as cache:
        engine = litert_lm.Engine(str(model), backend=litert_lm.Backend.CPU(), cache_dir=cache)
        ids = []
        for i in itertools.count():
            try:
                text = engine.detokenize([i])
            except RuntimeError:  # past the end of the vocabulary
                break
            if is_foreign(text):
                ids.append(i)
        return ids


def bitset(ids: list[int], size: int = VOCABULARY) -> bytes:
    bits = bytearray(size // 8)
    for i in ids:
        bits[i // 8] |= 1 << (i % 8)
    return bytes(bits)


def main(model: Path, out: Path) -> None:
    ids = foreign_tokens(model)
    if max(ids) >= VOCABULARY:
        sys.exit(f"token {max(ids)} is past Gemma 4's {VOCABULARY} tokens: not a Gemma 4 model?")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(bitset(ids))
    print(f"{len(ids)} tokens -> {out}")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
