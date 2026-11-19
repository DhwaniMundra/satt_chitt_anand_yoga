#!/usr/bin/env bash
# Starts one of the project's emulators and waits until Android has booted.
#   scripts/run_emulator.sh                         -> sca_phone (2 GB) on port 5554 (adb serial emulator-5554)
#   SCA_AVD=sca_phone_big scripts/run_emulator.sh   -> the 6 GB phone, which runs Gemma
#   SCA_AVD=sca_phone_2 SCA_PORT=5556 scripts/run_emulator.sh   -> a second phone, emulator-5556
# Pass -no-window to run it headless. It boots cold, never from a saved snapshot, so what was written on the phone
# (a downloaded model, say) is there next time; stop it with scripts/demo.sh stop, which syncs first.
set -euo pipefail
source "$(dirname "$0")/env.sh"
port="${SCA_PORT:-5554}"
emulator -avd "$SCA_AVD" -port "$port" -no-snapshot -no-audio -no-boot-anim "$@" > "$SCA_ROOT/tools/emulator_$port.log" 2>&1 &
export ANDROID_SERIAL="emulator-$port"
adb wait-for-device
until [ "$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" = "1" ]; do sleep 2; done
echo "emulator-$port ready"
