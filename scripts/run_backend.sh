#!/usr/bin/env bash
# Starts the backend on port 8000 with Gemma 4 E4B on the GPU.
# The Android emulator reaches it at http://10.0.2.2:8000; a phone on the same Wi-Fi at http://<this laptop's IP>:8000.
# Options (environment): SCA_GEMMA=gpu|cpu|off, SCA_TEACHER_CODE, SCA_BACKUP_REPO + SCA_GITHUB_TOKEN (see backend/sca/backup.py).
set -euo pipefail
cd "$(dirname "$0")/../backend"
exec .venv/bin/python -m sca.app
