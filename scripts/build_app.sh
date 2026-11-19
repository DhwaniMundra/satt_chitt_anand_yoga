#!/usr/bin/env bash
# Builds the app with the JDK and Android SDK in tools/.
#   scripts/build_app.sh             a debug APK for the dev backend: android/app/build/outputs/apk/debug/app-debug.apk
#   scripts/build_app.sh --release   a signed release APK for the live web app, arm64-v8a: .local/release/
# The release reads the web app's URL from .local/live_backend_url.txt (one line) and is signed with the key in
# .local/release/, made by the first release build; both stay out of git, and later releases need the same key.
# Other arguments go to Gradle: -PscaServer=http://<laptop IP>:8000 for a debug build on a phone, -Pabi=x86_64 for a
# release that runs on the emulator.
set -euo pipefail
source "$(dirname "$0")/env.sh"
cd "$SCA_ROOT/android"

if [[ "${1:-}" != "--release" ]]; then
    exec ./gradlew --console=plain assembleDebug "$@"
fi
shift

url_file="$SCA_ROOT/.local/live_backend_url.txt"
[[ -s "$url_file" ]] || { echo "missing $url_file: the live web app's URL, on one line" >&2; exit 1; }
out="$SCA_ROOT/.local/release"
signing="$out/signing.properties"
mkdir -p "$out"
if [[ ! -f "$signing" ]]; then
    password="$(head -c 24 /dev/urandom | base64 | tr -d '/+=')"
    keytool -genkeypair -keystore "$out/release.jks" -storetype PKCS12 -alias sca -keyalg RSA -keysize 4096 \
        -validity 10000 -storepass "$password" -dname "CN=Satt Chitt Anand"
    printf 'storeFile=%s\nstorePassword=%s\nkeyAlias=sca\nkeyPassword=%s\n' "$out/release.jks" "$password" "$password" > "$signing"
    chmod 600 "$signing" "$out/release.jks"
fi

abi=arm64-v8a
for arg in "$@"; do [[ "$arg" == -Pabi=* ]] && abi="${arg#-Pabi=}"; done
./gradlew --console=plain assembleRelease -PscaServer="$(head -n 1 "$url_file" | tr -d '[:space:]')" -Psigning="$signing" "$@"
version="$(sed -n 's/^ *versionName = "\(.*\)"/\1/p' app/build.gradle.kts)"
cp app/build/outputs/apk/release/app-release.apk "$out/satt-chitt-anand-$version-$abi.apk"
echo "$out/satt-chitt-anand-$version-$abi.apk"
