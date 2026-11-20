# Development

Everything needed to run, test and change the app. The README is the overview; this is the workshop.

## Requirements

Linux. The toolchain (JDK 21, Android SDK and emulator images, Node 22) and the Gemma model live in `tools/` and
`models/`, which git ignores (see [a fresh machine](#a-fresh-machine)). Gemma runs on the phone, so the laptop needs no
GPU.

## Run it

**A demo, in one command**
```bash
scripts/demo.sh          # the dev backend on demo data, the 6 GB emulator, the app open
scripts/demo.sh two      # two 2 GB phones: the teacher on one, a student on the other
scripts/demo.sh stop
```
Logins, password `demo123`: the teacher `9800000001`; students `9800000002` to `9800000006` and `9800000008` (Asha
is in the Intermediate batch, Kavita in Pain management); `9800000007` (Neha) is waiting to be placed, with her answers
given.
For Ask, download Gemma once in the app (2.6 GB, kept on the emulator).

**Step by step**
```bash
source scripts/env.sh                                   # java, node, adb and the emulator from tools/
node scripts/seed_demo.mjs data/demo.json               # the synthetic demo (or skip it: an empty Sheet)
node scripts/dev_backend.mjs data/demo.json             # port 8000; SCA_DELAY_MS=1500 to feel the live speed
scripts/build_app.sh                                    # android/app/build/outputs/apk/debug/app-debug.apk
SCA_AVD=sca_phone_big scripts/run_emulator.sh           # the 6 GB phone, which runs Gemma (sca_phone has 2 GB)
adb install -r android/app/build/outputs/apk/debug/app-debug.apk
```
The dev backend is the live backend's own `appsscript/dist/Code.gs`, run in Node on the test fakes, with its Sheet in
a JSON file. On an empty Sheet it prints the teacher sign-up code (or set `SCA_TEACHER_CODE`). The emulator reaches
the laptop at `http://10.0.2.2:8000`; for a phone on the same Wi-Fi, build with
`scripts/build_app.sh -PscaServer=http://<laptop IP>:8000`.

**The release**
```bash
scripts/build_app.sh --release              # signed, arm64-v8a, for the live web app: .local/release/
scripts/build_app.sh --release -Pabi=x86_64 # the same app for the emulator, to test the shrunk build there
```
It reads the live web app's URL from `.local/live_backend_url.txt` and signs with the key in `.local/release/`, made
by the first release build; both stay out of git, and every later release needs the same key. Setting up and updating
the live backend: [`appsscript/README.md`](../appsscript/README.md).

To try the shrunk app against the dev backend, Gemma and its tools included (R8 must keep what LiteRT-LM reads by
reflection), build the release for the emulator with the dev backend's address and the debug key, so it installs over
the debug app and keeps the downloaded model:
```bash
cd android && ./gradlew assembleRelease -Pabi=x86_64 -PscaServer=http://10.0.2.2:8000 -Psigning=<debug key's properties>
```
The properties file names `~/.android/debug.keystore` (`storePassword`, `keyPassword`: `android`; `keyAlias`:
`androiddebugkey`). A release allows plain HTTP only when built against such an `http://` address.

## Test

```bash
node --test 'appsscript/test/*.test.mjs'                                 # the backend: every route, on fakes of the Sheet
SCA_TEST_NOW=2026-11-22T18:31:00Z node --test 'appsscript/test/*.test.mjs'  # the same at another moment
node appsscript/scripts/build.mjs --check                                # dist/Code.gs is the build of src/ and content/
cd android && ./gradlew testDebugUnitTest                                # the app's JVM tests: the companion, notes, solo, the server's JSON
python3 scripts/eval_phone.py docs/evals/next_phone.md                   # Gemma in the app on the 6 GB emulator
SCA_WEBAPP_URL=<url> node appsscript/scripts/smoke.mjs 5                 # the live web app, with requests that write no row
```
The backend's tests run at a frozen moment; `SCA_TEST_NOW` runs them at another ([how](../appsscript/README.md#tests)). The phone evaluation needs the dev backend on the demo data and Gemma
downloaded; it asks each question in a fresh chat, reads the reply from the screen and writes every answer out. Its
checks are coarse: read every answer before trusting a pass.

## Tour it and make the media

Raw screenshots and recordings stay in `.local/visualization/` (git ignores it): `viz_v0/` holds the prototypes
(v0.1 to v0.7) and `viz_v0.9/` the practice tracker. In each, a version's screenshots are in `screens/<version>/`,
each tour shot with its UI dump beside it (`<name>.xml`, every element's bounds), and its recordings and the videos
made from them in `tours/`. Only what the README and the iteration log show goes in `docs/media/`.

```bash
python3 scripts/capture_tour.py v0.9.1                     # one version's screenshots and recordings (6 GB emulator)
python3 scripts/two_phone_test.py v0.9.1-two-phones PILOT1 # two 2 GB emulators, one dev backend, an empty Sheet
scripts/setup_media.sh                                     # once: tools/media-venv
tools/media-venv/bin/python scripts/make_figures.py        # hero, GIF strips, contact sheets
tools/media-venv/bin/python scripts/make_diagrams.py       # the diagrams
tools/media-venv/bin/python scripts/make_video.py          # the narrated tour (Kokoro-82M voice)
python3 scripts/preview_readme.py                          # the README as GitHub renders it
```
Both start their own dev backend, so stop any other first (`scripts/demo.sh stop`). The two-phone test needs a second
emulator: `SCA_AVD=sca_phone_2 SCA_PORT=5556 scripts/run_emulator.sh`.

## Where things are

| Path | What it is |
|---|---|
| `android/` | The app: `Data.kt` (the envelope client and models), `AppViewModel.kt`, `ui/` (one file per screen), `companion/` (Gemma on the phone, its tools and the notes' search), text in `res/values{,-hi,-mr}` |
| `appsscript/` | The live backend: `src/` (one file per part), `dist/Code.gs` (the file to paste), `test/` (every route, on fakes of the Sheet) |
| `content/` | The studio in three languages (`studio.json`: name, teacher, batches, the intake's poses), the curriculum and asana library (`curriculum.json`), and the companion's notes (`knowledge/`) |
| `scripts/` | Run it (`demo.sh`, `dev_backend.mjs`, `seed_demo.mjs`, `build_app.sh`, `run_emulator.sh`), test it on phones (`eval_phone.py`, `capture_tour.py`, `two_phone_test.py`, `phone.py`), make media (`make_figures.py`, `make_diagrams.py`, `make_video.py`, `preview_readme.py`) |
| `docs/` | `decisions.md`, `iterations/` (the log), `evals/` (every answer), `media/` (what the README shows) |
| `.local/` | *Not committed.* The live URL and the release key; recordings and raw screenshots in `visualization/` |
| `data/`, `tools/`, `models/` | *Not committed.* The dev backend's Sheets; the toolchain; the Gemma model |

## A fresh machine

`tools/` and `models/` were copied from an existing setup. On a new machine (not yet scripted):
1. JDK 21 (for example Eclipse Temurin) into `tools/jdk`, and Node 22 into `tools/node`.
2. Android command-line tools into `tools/android-sdk/cmdline-tools/latest`, then
   `sdkmanager "platform-tools" "emulator" "platforms;android-36" "build-tools;36.0.0" "system-images;android-36;google_apis_playstore;x86_64"`.
3. With `ANDROID_AVD_HOME=tools/avd`: `avdmanager create avd -n sca_phone -k "system-images;android-36;google_apis_playstore;x86_64" -d pixel_6`,
   the same for `sca_phone_2`, and `sca_phone_big` with `hw.ramSize=6144` in its `config.ini`, for Gemma.
4. Gemma itself is downloaded by the app, in Ask. For the evaluations on the laptop in `docs/evals/` before v0.9,
   `gemma-4-E2B-it.litertlm` and `gemma-4-E4B-it.litertlm` from Hugging Face (`litert-community`) go in `models/`.
