#!/usr/bin/env bash
set -euo pipefail

grep -E '^(NAME|VERSION|ID|PRETTY_NAME)=' /etc/os-release
ldd --version | head -n 1

if command -v dnf >/dev/null 2>&1; then
    dnf install -y /pkg/CodeBuddy-linux-x64-*.rpm
    rpm -V codebuddy-cn
elif command -v apt-get >/dev/null 2>&1; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y /pkg/CodeBuddy-linux-x64-*.deb
    dpkg -s codebuddy-cn | grep -E '^(Package|Status|Version|Architecture):'
    (cd / && md5sum -c /var/lib/dpkg/info/codebuddy-cn.md5sums >/dev/null)
fi

for bin in /usr/share/buddycn/buddycn \
           /usr/share/buddycn/libEGL.so \
           /usr/share/buddycn/libGLESv2.so \
           /usr/share/buddycn/libffmpeg.so \
           /usr/share/buddycn/libvk_swiftshader.so \
           $(find /usr/share/buddycn/resources/app -name "*.node"); do
    out=$(LD_LIBRARY_PATH=/usr/share/buddycn ldd "$bin" 2>&1 || true)
    if echo "$out" | grep -q "not found"; then
        echo "missing dependency in $bin:" >&2
        echo "$out" | grep "not found" >&2
        exit 1
    fi
done

mkdir -p /tmp/cb-user /tmp/cb-ext /tmp/cb-work
buddycn --version --no-sandbox --user-data-dir=/tmp/cb-user --extensions-dir=/tmp/cb-ext

ELECTRON_RUN_AS_NODE=1 /usr/share/buddycn/buddycn /pkg/test_functional.js

rm -rf /tmp/cb-gui-user /tmp/cb-gui-ext
mkdir -p /tmp/cb-gui-user /tmp/cb-gui-ext /tmp/cb-work
echo "console.log('test');" > /tmp/cb-work/index.js

timeout 12s /usr/share/buddycn/buddycn \
    --no-sandbox \
    --disable-gpu \
    --ozone-platform=headless \
    --user-data-dir=/tmp/cb-gui-user \
    --extensions-dir=/tmp/cb-gui-ext \
    --verbose \
    /tmp/cb-work >/tmp/cb-gui-stdout.log 2>&1 || true

renderer_log=$(find /tmp/cb-gui-user/logs -name "renderer.log" | head -n 1)
exthost_log=$(find /tmp/cb-gui-user/logs -name "exthost.log" | head -n 1)
grep -q "Started local extension host" "$renderer_log"
grep -q "_doActivateExtension" "$exthost_log"
echo "verify_os: ok"
