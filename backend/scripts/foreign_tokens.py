"""Writes the list of Gemma 4 tokens that Marathi answers may not use, for the app (Gemma on the phone).

On the laptop the server lists these tokens itself (sca.assistant.Gemma.foreign_tokens: every token with a letter or a
digit that is neither Latin nor Devanagari). LiteRT-LM for Android cannot turn a token id back into text, so the phone
gets the same list made here, from the same model file, as a bitset: bit i of the file (byte i / 8, lowest bit first)
is set when token i is banned, 32 KB for Gemma 4's 262,144 tokens. Run again only if the model file changes.

Usage (from backend/, with the server stopped): .venv/bin/python -m scripts.foreign_tokens \
    ../models/gemma-4-E2B-it/gemma-4-E2B-it.litertlm ../android/app/src/main/assets/gemma4_foreign_tokens.bin
"""

import sys
from pathlib import Path

from sca.assistant import Gemma

ROOT = Path(__file__).resolve().parents[2]
VOCABULARY = 262_144  # Gemma 4


def bitset(ids: list[int], size: int = VOCABULARY) -> bytes:
    bits = bytearray(size // 8)
    for i in ids:
        bits[i // 8] |= 1 << (i % 8)
    return bytes(bits)


def main(model: Path, out: Path) -> None:
    ids = Gemma(model, "cpu", ROOT / "data" / "litert_cache").foreign_tokens()
    if max(ids) >= VOCABULARY:
        sys.exit(f"token {max(ids)} is past Gemma 4's {VOCABULARY} tokens: not a Gemma 4 model?")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(bitset(ids))
    print(f"{len(ids)} tokens -> {out}")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
