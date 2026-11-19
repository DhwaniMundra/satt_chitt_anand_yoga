# Development

Everything needed to run, test and change the app. The README is the overview; this is the workshop.

## Requirements

Linux with an NVIDIA GPU. The toolchain (JDK 21, Android SDK, emulator image) and the Gemma model live in `tools/` and
`models/`, which git ignores (see [a fresh machine](#a-fresh-machine)).

## Run it

**A demo, in one command**
```bash
scripts/demo.sh          # server with Gemma on demo data, an emulator, the app open
scripts/demo.sh two      # a second phone: teacher on one, student on the other
scripts/demo.sh stop
```
Logins, password `demo123`: teacher `9800000001`; students `9800000002` to `9800000006`; `9800000007` is waiting for
approval.

**Step by step**
```bash
source scripts/env.sh                  # points java, adb and the emulator at tools/
scripts/run_backend.sh                 # API on :8000, Gemma loads in the background (SCA_GEMMA=off to skip)
scripts/build_app.sh                   # android/app/build/outputs/apk/debug/app-debug.apk
scripts/run_emulator.sh                # boots tools/avd/sca_phone
adb install -r android/app/build/outputs/apk/debug/app-debug.apk
```
The server prints the teacher sign-up code when it starts (or set `SCA_TEACHER_CODE`). The emulator reaches the laptop
at `http://10.0.2.2:8000`. A phone on the same Wi-Fi needs the laptop's address: build with
`scripts/build_app.sh -PscaServer=http://<laptop IP>:8000`, or change **Server address** on the first screen.

**Backups** (optional): a private GitHub repository and a fine-grained token with read and write access to its
contents; set `SCA_BACKUP_REPO=owner/name` and `SCA_GITHUB_TOKEN=…` before starting the server. An empty server
restores from the last backup.

## Test

```bash
cd backend && .venv/bin/python -m pytest -q                        # 95 tests: API, retrieval, safety path, backup, companion
.venv/bin/python -m scripts.eval_assistant ../docs/evals/next.md   # the assistant's question set; stop the server first
.venv/bin/python -m scripts.eval_companion ../data/demo.sqlite3 ../docs/evals/next_companion.md  # the companion's conversations
```
The companion's evaluation runs on a copy of the demo database; `SCA_MODEL=<path to a .litertlm>` picks the model
(E4B by default; the reports compare E2B and E4B). Run one evaluation at a time, with the server stopped. The checks
are coarse; read every answer in the report before trusting a pass.

## Tour it and make the media

Raw screenshots and recordings stay in `.local/visualization/` (git ignores it): files worth watching on top, raw
screenshots in `tours/`, build files in `work/`. Only what the README and the iteration log show goes in `docs/media/`.

```bash
cd backend && .venv/bin/python -m scripts.seed_demo ../data/demo.sqlite3 && cd ..
SCA_DB=$PWD/data/demo.sqlite3 scripts/run_backend.sh
python3 scripts/capture_tour.py v0.5 data/demo.sqlite3                   # one version's screenshots and recordings
python3 scripts/two_phone_test.py v0.5-two-phones http://10.0.2.2:8000 data/two_phones.sqlite3 <teacher code>
scripts/setup_media.sh                                                   # once: tools/media-venv
tools/media-venv/bin/python scripts/make_figures.py                      # hero, GIF strips, contact sheets
tools/media-venv/bin/python scripts/make_diagrams.py                     # the three diagrams
tools/media-venv/bin/python scripts/make_video.py                        # the narrated tour (Kokoro-82M voice)
python3 scripts/preview_readme.py                                        # the README as GitHub renders it
```
The two-phone test needs a second emulator: `SCA_AVD=sca_phone_2 SCA_PORT=5556 scripts/run_emulator.sh`, and a server
on a fresh database started with `SCA_TEACHER_CODE`.

## Where things are

| Path | What it is |
|---|---|
| `android/` | The app: `Data.kt` (HTTP and models), `AppViewModel.kt`, `ui/` (one file per screen), text in `res/values{,-hi,-mr}` |
| `backend/sca/` | The server: `app.py` (API), `db.py`, `auth.py`, `studio.py`, `whatsapp.py`, `assistant.py` (notes and Gemma), `companion.py` (the chat and its tools), `backup.py` |
| `backend/knowledge/` | The assistant's notes, in English and Marathi |
| `backend/content/studio.json` | Classes, weekly rhythm and teacher, in three languages |
| `backend/tests/`, `backend/evals/` | Tests; the assistant's question set (the companion's conversations are in `backend/scripts/eval_companion.py`) |
| `scripts/` | Run it (`demo.sh`, `run_backend.sh`, `build_app.sh`, `run_emulator.sh`), tour it (`capture_tour.py`, `two_phone_test.py`, `phone.py`), make media (`make_figures.py`, `make_diagrams.py`, `make_video.py`, `preview_readme.py`) |
| `docs/` | `decisions.md`, `iterations/` (the log), `evals/` (every answer), `media/` (what the README shows) |
| `.local/visualization/` | *Not committed.* Recordings on top; raw screenshots in `tours/`; build files in `work/` |
| `data/`, `tools/`, `models/` | *Not committed.* Databases; toolchain; the Gemma model |

## A fresh machine

`tools/` and `models/` were copied from an existing setup. On a new machine (not yet scripted):
1. JDK 21 (for example Eclipse Temurin) into `tools/jdk`.
2. Android command-line tools into `tools/android-sdk/cmdline-tools/latest`, then
   `sdkmanager "platform-tools" "emulator" "platforms;android-36" "build-tools;36.0.0" "system-images;android-36;google_apis_playstore;x86_64"`.
3. `avdmanager create avd -n sca_phone -k "system-images;android-36;google_apis_playstore;x86_64" -d pixel_6` with
   `ANDROID_AVD_HOME=tools/avd`.
4. `gemma-4-E4B-it.litertlm` from Hugging Face (`litert-community/gemma-4-E4B-it-litert-lm`) into
   `models/gemma-4-E4B-it/`; for the companion's E2B evaluation, the E2B file (`gemma-4-E2B-it.litertlm`) into
   `models/gemma-4-E2B-it/`.
5. `cd backend && uv venv .venv && uv pip install -e ".[dev]"`.
