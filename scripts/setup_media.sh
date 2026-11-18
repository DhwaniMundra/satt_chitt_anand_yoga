#!/usr/bin/env bash
# Creates tools/media-venv for the narrated video (scripts/make_video.py): Kokoro-82M text-to-speech
# (https://huggingface.co/hexgrad/Kokoro-82M, Apache-2.0) on the CPU, Pillow and SciPy. The voice model is read from
# tools/hf (HF_HOME); the first run downloads it there if it is missing, later runs work offline.
# Fonts: Sora and JetBrains Mono (SIL Open Font License) in tools/fonts.
set -euo pipefail
cd "$(dirname "$0")/.."
uv venv -q --python 3.12 tools/media-venv
VIRTUAL_ENV=tools/media-venv uv pip install -q --index-url https://download.pytorch.org/whl/cpu torch
VIRTUAL_ENV=tools/media-venv uv pip install -q kokoro soundfile pillow scipy pip
