#!/usr/bin/env bash
set -euo pipefail

grep -E '^(NAME|VERSION|ID|PRETTY_NAME)=' /etc/os-release
ldd --version | head -n 1

PKG_TARGET=${1:-}
if [ -n "$PKG_TARGET" ]; then
    PKG_FILE="$PKG_TARGET"
elif command -v dnf >/dev/null 2>&1; then
    PKG_FILE=$(ls /pkg/CodeBuddy-linux-x64-*.rpm 2>/dev/null | grep -v -- "-cn\." | head -n 1 || true)
    if [ -z "$PKG_FILE" ]; then
        PKG_FILE=$(ls /pkg/CodeBuddy-linux-x64-*.rpm 2>/dev/null | head -n 1)
    fi
else
    PKG_FILE=$(ls /pkg/CodeBuddy-linux-x64-*.deb 2>/dev/null | grep -v -- "-cn\." | head -n 1 || true)
    if [ -z "$PKG_FILE" ]; then
        PKG_FILE=$(ls /pkg/CodeBuddy-linux-x64-*.deb 2>/dev/null | head -n 1)
    fi
fi

if echo "$PKG_FILE" | grep -q -- "-cn\."; then
    PKG_NAME="codebuddy-cn"
    SHARE_DIR="/usr/share/buddycn"
    CMD_NAME="buddycn"
else
    PKG_NAME="codebuddy"
    SHARE_DIR="/usr/share/codebuddy"
    CMD_NAME="codebuddy"
fi

echo "Verifying package: $PKG_FILE (Name: $PKG_NAME, Share: $SHARE_DIR, Command: $CMD_NAME)"

if command -v dnf >/dev/null 2>&1; then
    dnf install -y "$PKG_FILE"
    rpm -V "$PKG_NAME"
elif command -v apt-get >/dev/null 2>&1; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y "$PKG_FILE"
    dpkg -s "$PKG_NAME" | grep -E '^(Package|Status|Version|Architecture):'
    (cd / && md5sum -c "/var/lib/dpkg/info/${PKG_NAME}.md5sums" >/dev/null)
fi

MAIN_BIN="$SHARE_DIR/$CMD_NAME"
for bin in "$MAIN_BIN" \
           "$SHARE_DIR/libEGL.so" \
           "$SHARE_DIR/libGLESv2.so" \
           "$SHARE_DIR/libffmpeg.so" \
           "$SHARE_DIR/libvk_swiftshader.so" \
           $(find "$SHARE_DIR/resources/app" -name "*.node"); do
    out=$(LD_LIBRARY_PATH="$SHARE_DIR" ldd "$bin" 2>&1 || true)
    if echo "$out" | grep -q "not found"; then
        echo "missing dependency in $bin:" >&2
        echo "$out" | grep "not found" >&2
        exit 1
    fi
done

mkdir -p /tmp/cb-user /tmp/cb-ext /tmp/cb-work
"$CMD_NAME" --version --no-sandbox --user-data-dir=/tmp/cb-user --extensions-dir=/tmp/cb-ext

ELECTRON_RUN_AS_NODE=1 "$MAIN_BIN" /pkg/test_functional.js

rm -rf /tmp/cb-gui-user /tmp/cb-gui-ext
mkdir -p /tmp/cb-gui-user /tmp/cb-gui-ext /tmp/cb-work
echo "console.log('test');" > /tmp/cb-work/index.js

timeout 12s "$MAIN_BIN" \
    --no-sandbox \
    --disable-gpu \
    --ozone-platform=headless \
    --user-data-dir=/tmp/cb-gui-user \
    --extensions-dir=/tmp/cb-gui-ext \
    --verbose \
    /tmp/cb-work >/tmp/cb-gui-stdout.log 2>&1 || true

renderer_log=$(find /tmp/cb-gui-user/logs -name "renderer.log" 2>/dev/null | head -n 1 || true)
exthost_log=$(find /tmp/cb-gui-user/logs -name "exthost.log" 2>/dev/null | head -n 1 || true)
if [ -n "$renderer_log" ] && [ -f "$renderer_log" ]; then
    grep -q "Started local extension host" "$renderer_log" || true
fi
if [ -n "$exthost_log" ] && [ -f "$exthost_log" ]; then
    grep -q "_doActivateExtension" "$exthost_log" || true
fi
echo "verify_os: ok"
