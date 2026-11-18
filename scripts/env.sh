# Source this file: points every tool at the copies inside this repo (tools/, gitignored).
# Usage: source scripts/env.sh
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export SCA_ROOT="$ROOT"
export JAVA_HOME="$ROOT/tools/jdk"
export ANDROID_HOME="$ROOT/tools/android-sdk"
export ANDROID_SDK_ROOT="$ANDROID_HOME"
export ANDROID_AVD_HOME="$ROOT/tools/avd"
export PATH="$JAVA_HOME/bin:$ANDROID_HOME/platform-tools:$ANDROID_HOME/emulator:$ANDROID_HOME/cmdline-tools/latest/bin:$PATH"
export SCA_AVD="${SCA_AVD:-sca_phone}"   # override to run the second phone: SCA_AVD=sca_phone_2
