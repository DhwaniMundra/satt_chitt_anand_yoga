#!/usr/bin/env bash
# One command to show the app on this laptop: the dev backend on the synthetic demo data (data/demo.json), an emulator
# with a window, and the app installed and open.
#   scripts/demo.sh         one phone, sca_phone_big (6 GB): Gemma runs on it once downloaded in Ask
#   scripts/demo.sh two     two 2 GB phones, sca_phone and sca_phone_2: the teacher on one, a student on the other
#   scripts/demo.sh stop    stops the backend and the emulators
# Logins (password demo123): teacher 9800000001, students 9800000002 to 9800000006 and 9800000008; 9800000007 waits to
# be placed in a batch.
# DEMO_HEADLESS=1 runs the emulators without windows.
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/env.sh
APK=android/app/build/outputs/apk/debug/app-debug.apk
DATA=data/demo.json
window=(); [[ "${DEMO_HEADLESS:-0}" == 1 ]] && window=(-no-window)

if [[ "${1:-}" == "stop" ]]; then
    pkill -f "[d]ev_backend.mjs" || true
    for serial in emulator-5554 emulator-5556; do # sync first: a killed emulator loses what Android had not written, a downloaded model too
        adb -s "$serial" shell sync 2>/dev/null && adb -s "$serial" emu kill || true
    done
    echo "stopped"
    exit 0
fi

[[ -f "$DATA" ]] || node scripts/seed_demo.mjs "$DATA"
if ! curl -s -m 2 localhost:8000 > /dev/null; then
    nohup node scripts/dev_backend.mjs "$DATA" > data/dev_backend.log 2>&1 &
fi
[[ -f "$APK" ]] || scripts/build_app.sh

phones=("5554 sca_phone_big"); [[ "${1:-}" == "two" ]] && phones=("5554 sca_phone" "5556 sca_phone_2")
for phone in "${phones[@]}"; do
    read -r port avd <<< "$phone"
    serial="emulator-$port"
    adb devices | grep -q "^$serial" || SCA_AVD="$avd" SCA_PORT="$port" scripts/run_emulator.sh "${window[@]}"
    adb -s "$serial" shell cmd alarm set-timezone Asia/Kolkata
    adb -s "$serial" install -r "$APK" > /dev/null
    adb -s "$serial" shell am start -n com.sattchittanand.yoga/.MainActivity > /dev/null
done
echo "Logins (password demo123): teacher 9800000001; students 9800000002-9800000006 and 9800000008; 9800000007 waits to be placed."
