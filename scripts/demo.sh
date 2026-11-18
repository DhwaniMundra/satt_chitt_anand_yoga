#!/usr/bin/env bash
# One command to show the app on this laptop: the backend with Gemma on the synthetic demo data, the emulator with a
# window, and the app installed and open.
#   scripts/demo.sh            one phone
#   scripts/demo.sh two        a second phone too (log in as the teacher on one, a student on the other)
# Logins (password demo123): teacher 9800000001, students 9800000002 to 9800000006; 9800000007 waits for approval.
# Pass DEMO_HEADLESS=1 to run the emulators without windows. Stop everything with: scripts/demo.sh stop
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/env.sh
APK=android/app/build/outputs/apk/debug/app-debug.apk
window=(); [[ "${DEMO_HEADLESS:-0}" == 1 ]] && window=(-no-window)

if [[ "${1:-}" == "stop" ]]; then
    pkill -f "[b]in/python -m sca.app" || true
    for serial in emulator-5554 emulator-5556; do adb -s "$serial" emu kill 2>/dev/null || true; done
    echo "stopped"
    exit 0
fi

[[ -f data/demo.sqlite3 ]] || (cd backend && .venv/bin/python -m scripts.seed_demo ../data/demo.sqlite3)
if ! curl -s -m 2 localhost:8000/health > /dev/null; then
    SCA_DB="$PWD/data/demo.sqlite3" SCA_TEACHER_CODE=RAMIT1994 nohup scripts/run_backend.sh > data/backend_demo.log 2>&1 &
fi
[[ -f "$APK" ]] || scripts/build_app.sh

phones=(5554); [[ "${1:-}" == "two" ]] && phones=(5554 5556)
for port in "${phones[@]}"; do
    serial="emulator-$port"
    avd=sca_phone; [[ "$port" == 5556 ]] && avd=sca_phone_2
    adb devices | grep -q "^$serial" || SCA_AVD="$avd" SCA_PORT="$port" scripts/run_emulator.sh "${window[@]}"
    adb -s "$serial" shell cmd alarm set-timezone Asia/Kolkata
    adb -s "$serial" install -r "$APK" > /dev/null
    adb -s "$serial" shell am start -n com.sattchittanand.yoga/.MainActivity > /dev/null
done

echo -n "waiting for Gemma"
until curl -s -m 2 localhost:8000/health | grep -q '"ready"'; do echo -n "."; sleep 2; done
echo " ready"
echo "Logins (password demo123): teacher 9800000001; students 9800000002-9800000006; 9800000007 is waiting for approval."
