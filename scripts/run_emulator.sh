#!/usr/bin/env bash
# Starts the project's emulator (tools/avd/sca_phone) and waits until Android has booted.
# Pass -no-window to run it headless.
set -euo pipefail
source "$(dirname "$0")/env.sh"
emulator -avd "$SCA_AVD" -no-snapshot-save -no-audio -no-boot-anim "$@" > "$SCA_ROOT/tools/emulator.log" 2>&1 &
adb wait-for-device
until [ "$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" = "1" ]; do sleep 2; done
echo "emulator ready"
