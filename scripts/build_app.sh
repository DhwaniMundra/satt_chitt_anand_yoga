#!/usr/bin/env bash
# Builds the debug APK with the JDK and Android SDK in tools/. Output: android/app/build/outputs/apk/debug/app-debug.apk
set -euo pipefail
source "$(dirname "$0")/env.sh"
cd "$SCA_ROOT/android"
./gradlew --console=plain assembleDebug "$@"
