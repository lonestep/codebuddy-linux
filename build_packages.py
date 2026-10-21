#!/usr/bin/env python3
import argparse
import hashlib
import os
import re
import shutil
import stat
import struct
import subprocess
import sys

BUILD_TIME = 1757036280

APPARMOR_PROFILE_CN = """abi <abi/4.0>,
include <tunables/global>

profile buddycn /usr/share/buddycn/buddycn flags=(unconfined) {
  userns,

  include if exists <local/buddycn>
}
"""

APPARMOR_PROFILE_INTL = """abi <abi/4.0>,
include <tunables/global>

profile codebuddy /usr/share/codebuddy/codebuddy flags=(unconfined) {
  userns,

  include if exists <local/codebuddy>
}
"""

DEB_POSTINST_CN = """#!/usr/bin/env bash
set -e

if [ -f /usr/share/buddycn/chrome-sandbox ]; then
\tchown root:root /usr/share/buddycn/chrome-sandbox 2>/dev/null || true
\tchmod 4755 /usr/share/buddycn/chrome-sandbox 2>/dev/null || true
fi

if [ -f "/usr/share/buddycn/apparmor.d/buddycn" ]; then
\tif [ -f "/etc/apparmor.d/abi/4.0" ] && [ -d "/etc/apparmor.d" ]; then
\t\tcp "/usr/share/buddycn/apparmor.d/buddycn" "/etc/apparmor.d/buddycn"
\t\tif [ -x /sbin/apparmor_parser ]; then
\t\t\t/sbin/apparmor_parser -r "/etc/apparmor.d/buddycn" 2>/dev/null || true
\t\tfi
\tfi
fi

rm -f /usr/bin/buddycn
ln -s /usr/share/buddycn/bin/buddycn /usr/bin/buddycn

if command -v update-alternatives >/dev/null 2>&1; then
\tupdate-alternatives --install /usr/bin/editor editor /usr/bin/buddycn 0 2>/dev/null || true
fi

if command -v update-desktop-database >/dev/null 2>&1; then
\tupdate-desktop-database -q /usr/share/applications 2>/dev/null || true
fi

if command -v update-mime-database >/dev/null 2>&1; then
\tupdate-mime-database /usr/share/mime 2>/dev/null || true
fi
"""

DEB_PRERM_CN = """#!/usr/bin/env bash
set -e

if command -v update-alternatives >/dev/null 2>&1; then
\tupdate-alternatives --remove editor /usr/bin/buddycn || true
fi
"""

DEB_POSTRM_CN = """#!/usr/bin/env bash
set -e

if [ "$1" = "remove" ] || [ "$1" = "purge" ]; then
\trm -f /usr/bin/buddycn

\tif [ -f "/etc/apparmor.d/buddycn" ]; then
\t\tif [ -x /sbin/apparmor_parser ]; then
\t\t\t/sbin/apparmor_parser -R "/etc/apparmor.d/buddycn" 2>/dev/null || true
\t\tfi
\t\trm -f "/etc/apparmor.d/buddycn"
\tfi

\tif command -v update-desktop-database >/dev/null 2>&1; then
\t\tupdate-desktop-database -q /usr/share/applications 2>/dev/null || true
\tfi

\tif command -v update-mime-database >/dev/null 2>&1; then
\t\tupdate-mime-database /usr/share/mime 2>/dev/null || true
\tfi
fi
"""

RPM_POSTIN_CN = """#!/bin/sh
if [ -f /usr/share/buddycn/chrome-sandbox ]; then
    chown root:root /usr/share/buddycn/chrome-sandbox 2>/dev/null || true
    chmod 4755 /usr/share/buddycn/chrome-sandbox 2>/dev/null || true
fi
rm -f /usr/bin/buddycn
ln -s /usr/share/buddycn/bin/buddycn /usr/bin/buddycn
if command -v update-alternatives >/dev/null 2>&1; then
    update-alternatives --install /usr/bin/editor editor /usr/bin/buddycn 0 2>/dev/null || true
fi
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q /usr/share/applications 2>/dev/null || true
fi
if command -v update-mime-database >/dev/null 2>&1; then
    update-mime-database /usr/share/mime 2>/dev/null || true
fi
exit 0
"""

RPM_PREUN_CN = """#!/bin/sh
if [ "$1" = "0" ]; then
    if command -v update-alternatives >/dev/null 2>&1; then
        update-alternatives --remove editor /usr/bin/buddycn 2>/dev/null || true
    fi
fi
exit 0
"""

RPM_POSTUN_CN = """#!/bin/sh
if [ "$1" = "0" ]; then
    rm -f /usr/bin/buddycn
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database -q /usr/share/applications 2>/dev/null || true
    fi
    if command -v update-mime-database >/dev/null 2>&1; then
        update-mime-database /usr/share/mime 2>/dev/null || true
    fi
fi
exit 0
"""

DEB_POSTINST_INTL = """#!/usr/bin/env bash
set -e

if [ -f /usr/share/codebuddy/chrome-sandbox ]; then
\tchown root:root /usr/share/codebuddy/chrome-sandbox 2>/dev/null || true
\tchmod 4755 /usr/share/codebuddy/chrome-sandbox 2>/dev/null || true
fi

if [ -f "/usr/share/codebuddy/apparmor.d/codebuddy" ]; then
\tif [ -f "/etc/apparmor.d/abi/4.0" ] && [ -d "/etc/apparmor.d" ]; then
\t\tcp "/usr/share/codebuddy/apparmor.d/codebuddy" "/etc/apparmor.d/codebuddy"
\t\tif [ -x /sbin/apparmor_parser ]; then
\t\t\t/sbin/apparmor_parser -r "/etc/apparmor.d/codebuddy" 2>/dev/null || true
\t\tfi
\tfi
fi

rm -f /usr/bin/codebuddy /usr/bin/buddy
ln -s /usr/share/codebuddy/bin/codebuddy /usr/bin/codebuddy
ln -s /usr/share/codebuddy/bin/buddy /usr/bin/buddy

if command -v update-alternatives >/dev/null 2>&1; then
\tupdate-alternatives --install /usr/bin/editor editor /usr/bin/codebuddy 0 2>/dev/null || true
fi

if command -v update-desktop-database >/dev/null 2>&1; then
\tupdate-desktop-database -q /usr/share/applications 2>/dev/null || true
fi

if command -v update-mime-database >/dev/null 2>&1; then
\tupdate-mime-database /usr/share/mime 2>/dev/null || true
fi
"""

DEB_PRERM_INTL = """#!/usr/bin/env bash
set -e

if command -v update-alternatives >/dev/null 2>&1; then
\tupdate-alternatives --remove editor /usr/bin/codebuddy || true
fi
"""

DEB_POSTRM_INTL = """#!/usr/bin/env bash
set -e

if [ "$1" = "remove" ] || [ "$1" = "purge" ]; then
\trm -f /usr/bin/codebuddy /usr/bin/buddy

\tif [ -f "/etc/apparmor.d/codebuddy" ]; then
\t\tif [ -x /sbin/apparmor_parser ]; then
\t\t\t/sbin/apparmor_parser -R "/etc/apparmor.d/codebuddy" 2>/dev/null || true
\t\tfi
\t\trm -f "/etc/apparmor.d/codebuddy"
\tfi

\tif command -v update-desktop-database >/dev/null 2>&1; then
\t\tupdate-desktop-database -q /usr/share/applications 2>/dev/null || true
\tfi

\tif command -v update-mime-database >/dev/null 2>&1; then
\t\tupdate-mime-database /usr/share/mime 2>/dev/null || true
\tfi
fi
"""

RPM_POSTIN_INTL = """#!/bin/sh
if [ -f /usr/share/codebuddy/chrome-sandbox ]; then
    chown root:root /usr/share/codebuddy/chrome-sandbox 2>/dev/null || true
    chmod 4755 /usr/share/codebuddy/chrome-sandbox 2>/dev/null || true
fi
rm -f /usr/bin/codebuddy /usr/bin/buddy
ln -s /usr/share/codebuddy/bin/codebuddy /usr/bin/codebuddy
ln -s /usr/share/codebuddy/bin/buddy /usr/bin/buddy
if command -v update-alternatives >/dev/null 2>&1; then
    update-alternatives --install /usr/bin/editor editor /usr/bin/codebuddy 0 2>/dev/null || true
fi
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q /usr/share/applications 2>/dev/null || true
fi
if command -v update-mime-database >/dev/null 2>&1; then
    update-mime-database /usr/share/mime 2>/dev/null || true
fi
exit 0
"""

RPM_PREUN_INTL = """#!/bin/sh
if [ "$1" = "0" ]; then
    if command -v update-alternatives >/dev/null 2>&1; then
        update-alternatives --remove editor /usr/bin/codebuddy 2>/dev/null || true
    fi
fi
exit 0
"""

RPM_POSTUN_INTL = """#!/bin/sh
if [ "$1" = "0" ]; then
    rm -f /usr/bin/codebuddy /usr/bin/buddy
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database -q /usr/share/applications 2>/dev/null || true
    fi
    if command -v update-mime-database >/dev/null 2>&1; then
        update-mime-database /usr/share/mime 2>/dev/null || true
    fi
fi
exit 0
"""

DESKTOP_ENTRY_INTL = """[Desktop Entry]
Name=CodeBuddy
Comment=Code Editing. Redefined.
GenericName=Text Editor
Exec=/usr/share/codebuddy/bin/codebuddy %F
Icon=codebuddy
Type=Application
StartupNotify=false
StartupWMClass=CodeBuddy
Categories=TextEditor;Development;IDE;
MimeType=application/x-codebuddy-workspace;
Actions=new-empty-window;
Keywords=vscode;codebuddy;

[Desktop Action new-empty-window]
Name=New Empty Window
Name[zh_CN]=新建空窗口
Exec=/usr/share/codebuddy/bin/codebuddy --new-window %F
Icon=codebuddy
"""

MIME_XML_INTL = """<?xml version="1.0" encoding="UTF-8"?>
<mime-info xmlns="http://www.freedesktop.org/standards/shared-mime-info">
\t<mime-type type="application/x-codebuddy-workspace">
\t\t<comment>CodeBuddy Workspace</comment>
\t\t<glob pattern="*.code-workspace"/>
\t</mime-type>
</mime-info>
"""

APPDATA_XML_INTL = """<?xml version="1.0" encoding="UTF-8"?>
<component type="desktop">
\t<id>codebuddy.desktop</id>
\t<metadata_license>MIT</metadata_license>
\t<project_license>MIT</project_license>
\t<name>CodeBuddy</name>
\t<url type="homepage">https://www.codebuddy.ai</url>
\t<summary>CodeBuddy - AI-powered IDE for Linux.</summary>
\t<description>
\t\t<p>CodeBuddy is an AI-powered integrated development environment.</p>
\t</description>
</component>
"""

LAUNCHER_SCRIPT_INTL = """#!/usr/bin/env sh
#
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.

# when run in remote terminal, use the remote cli
if [ -n "$VSCODE_IPC_HOOK_CLI" ]; then
\tREMOTE_CLI="$(which -a 'codebuddy' 2>/dev/null | grep /remote-cli/)"
\tif [ -n "$REMOTE_CLI" ]; then
\t\t"$REMOTE_CLI" "$@"
\t\texit $?
\tfi
fi

# test that VSCode wasn't installed inside WSL
if grep -qi Microsoft /proc/version 2>/dev/null && [ -z "$DONT_PROMPT_WSL_INSTALL" ]; then
\techo "To use CodeBuddy with the Windows Subsystem for Linux, please install CodeBuddy in Windows and uninstall the Linux version in WSL. You can then use the \\`codebuddy\\` command in a WSL terminal just as you would in a normal command prompt." 1>&2
\tprintf "Do you want to continue anyway? [y/N] " 1>&2
\tread -r YN
\tYN=$(printf '%s' "$YN" | tr '[:upper:]' '[:lower:]')
\tcase "$YN" in
\t\ty | yes )
\t\t;;
\t\t* )
\t\t\texit 1
\t\t;;
\tesac
\techo "To no longer see this prompt, start CodeBuddy with the environment variable DONT_PROMPT_WSL_INSTALL defined." 1>&2
fi

# If root, ensure that --user-data-dir or --file-write is specified
if [ "$(id -u)" = "0" ]; then
\tfor i in "$@"
\tdo
\t\tcase "$i" in
\t\t\t--user-data-dir | --user-data-dir=* | --file-write | tunnel | serve-web )
\t\t\t\tCAN_LAUNCH_AS_ROOT=1
\t\t\t;;
\t\tesac
\tdone
\tif [ -z "$CAN_LAUNCH_AS_ROOT" ]; then
\t\techo "You are trying to start CodeBuddy as a super user which isn't recommended. If this was intended, please add the argument \\`--no-sandbox\\` and specify an alternate user data directory using the \\`--user-data-dir\\` argument." 1>&2
\t\texit 1
\tfi
fi

if [ ! -L "$0" ]; then
\tVSCODE_PATH="$(dirname "$0")/.."
else
\tif command -v readlink >/dev/null 2>&1; then
\t\tVSCODE_PATH="$(dirname "$(readlink -f "$0")")/.."
\telse
\t\tVSCODE_PATH="/usr/share/codebuddy"
\tfi
fi

IME_HELPER="$VSCODE_PATH/bin/code-desktop-ime.sh"
if [ -f "$IME_HELPER" ]; then
\t. "$IME_HELPER"
\tcodebuddy_ensure_linux_ime_env
fi

ELECTRON="$VSCODE_PATH/codebuddy"
CLI="$VSCODE_PATH/resources/app/out/cli.js"
ELECTRON_RUN_AS_NODE=1 "$ELECTRON" "$CLI" "$@"
exit $?
"""

NATIVE_KEYMAP_INDEX = """function NativeBinding() {
  this._tried = false;
  this._keymapping = null;
}
NativeBinding.prototype._init = function() {
  if (this._tried) {
    return;
  }
  this._tried = true;
  try {
    this._keymapping = require('./build/Release/keymapping');
  } catch (err) {
    try {
      this._keymapping = require('./build/Debug/keymapping');
    } catch (err2) {
      this._keymapping = null;
    }
  }
};
NativeBinding.prototype.getKeyMap = function() {
  try {
    this._init();
    return this._keymapping ? this._keymapping.getKeyMap() : [];
  } catch (err) {
    return [];
  }
};
NativeBinding.prototype.getCurrentKeyboardLayout = function() {
  try {
    this._init();
    return this._keymapping ? this._keymapping.getCurrentKeyboardLayout() : null;
  } catch (err) {
    return null;
  }
};
NativeBinding.prototype.onDidChangeKeyboardLayout = function(callback) {
  try {
    this._init();
    if (this._keymapping) {
      this._keymapping.onDidChangeKeyboardLayout(callback);
    }
  } catch (err) {
  }
};
NativeBinding.prototype.isISOKeyboard = function() {
  try {
    this._init();
    return this._keymapping ? this._keymapping.isISOKeyboard() : false;
  } catch (err) {
    return false;
  }
};

var binding = new NativeBinding();

exports.getCurrentKeyboardLayout = function() {
  return binding.getCurrentKeyboardLayout();
};
exports.getKeyMap = function() {
  return binding.getKeyMap();
};
exports.onDidChangeKeyboardLayout = function(callback) {
  return binding.onDidChangeKeyboardLayout(callback);
};
exports.isISOKeyboard = function() {
  return binding.isISOKeyboard();
};
"""

NATIVE_WATCHDOG_INDEX = """var watchdog = null;
try {
    watchdog = require('./build/Release/watchdog');
} catch (err) {
    watchdog = null;
}

var hasStarted = false;

exports.start = function(pid) {
    if (typeof pid !== 'number' || Math.round(pid) !== pid) {
        throw new Error('Expected integer pid!');
    }
    if (hasStarted) {
        throw new Error('Can only monitor a single process!');
    }
    hasStarted = true;
    if (watchdog && typeof watchdog.start === 'function') {
        watchdog.start(pid);
    }
};

exports.exit = function(code) {
    if (watchdog && typeof watchdog.exit === 'function') {
        watchdog.exit(code || 0);
    } else {
        process.exit(code || 0);
    }
};
"""


def extract_upstream_deb(deb_path, work_dir):
    debian_dir = os.path.join(work_dir, "DEBIAN")
    root_dir = os.path.join(work_dir, "root")
    if os.path.exists(work_dir):
        shutil.rmtree(work_dir)
    os.makedirs(debian_dir, exist_ok=True)
    os.makedirs(root_dir, exist_ok=True)

    subprocess.run(["ar", "x", os.path.abspath(deb_path)], cwd=work_dir, check=True)
    for name in os.listdir(work_dir):
        if name.startswith("control.tar"):
            subprocess.run(["tar", "-xf", os.path.join(work_dir, name), "-C", debian_dir], check=True)
            os.remove(os.path.join(work_dir, name))
        elif name.startswith("data.tar"):
            subprocess.run(["tar", "-xf", os.path.join(work_dir, name), "-C", root_dir], check=True)
            os.remove(os.path.join(work_dir, name))
        elif name == "debian-binary":
            os.remove(os.path.join(work_dir, name))


def patch_spdlog_file(spdlog_path):
    with open(spdlog_path, "rb") as f:
        data = bytearray(f.read())

    versym_off = 104178
    verneed_off = 106160
    if len(data) > verneed_off + 0x180:
        cur_ver = struct.unpack_from("<H", data, versym_off + 14 * 2)[0]
        if cur_ver == 7:
            struct.pack_into("<H", data, versym_off + 14 * 2, 12)
            struct.pack_into("<H", data, verneed_off + 0xB0 + 2, 15)
            struct.pack_into("<I", data, verneed_off + 0x160 + 12, 0x20)
            data[verneed_off + 0x170 : verneed_off + 0x180] = b"\x00" * 16
            data = data.replace(b"GLIBCXX_3.4.30\x00", b"GLIBCXX_3.4.11\x00")
            with open(spdlog_path, "wb") as f:
                f.write(data)


def patch_spdlog(root_dir):
    spdlog_path = os.path.join(
        root_dir,
        "usr/share/buddycn/resources/app/node_modules/@vscode/spdlog/build/Release/spdlog.node",
    )
    if os.path.exists(spdlog_path):
        patch_spdlog_file(spdlog_path)


def apply_cn_tree_fixes(root_dir, debian_dir, pkg_ver):
    patch_spdlog(root_dir)

    keymap_js = os.path.join(root_dir, "usr/share/buddycn/resources/app/node_modules/native-keymap/index.js")
    if os.path.exists(keymap_js):
        with open(keymap_js, "w", encoding="utf-8") as f:
            f.write(NATIVE_KEYMAP_INDEX)

    watchdog_js = os.path.join(root_dir, "usr/share/buddycn/resources/app/node_modules/native-watchdog/index.js")
    if os.path.exists(watchdog_js):
        with open(watchdog_js, "w", encoding="utf-8") as f:
            f.write(NATIVE_WATCHDOG_INDEX)

    launcher = os.path.join(root_dir, "usr/share/buddycn/bin/buddycn")
    with open(launcher, "r", encoding="utf-8") as f:
        launcher_txt = f.read()
    if "code-desktop-ime.sh" not in launcher_txt:
        target = 'ELECTRON="$VSCODE_PATH/buddycn"'
        hook = (
            'IME_HELPER="$VSCODE_PATH/bin/code-desktop-ime.sh"\n'
            'if [ -f "$IME_HELPER" ]; then\n'
            '\t. "$IME_HELPER"\n'
            '\tcodebuddy_ensure_linux_ime_env\n'
            'fi\n\n'
            + target
        )
        launcher_txt = launcher_txt.replace(target, hook, 1)
        with open(launcher, "w", encoding="utf-8") as f:
            f.write(launcher_txt)
        os.chmod(launcher, 0o755)

    for rel_xml in ("usr/share/mime/packages/buddycn-workspace.xml", "usr/share/appdata/buddycn.appdata.xml"):
        xml_path = os.path.join(root_dir, rel_xml)
        if os.path.exists(xml_path):
            with open(xml_path, "r", encoding="utf-8") as f:
                txt = f.read()
            txt = (
                txt.replace("@@NAME_LONG@@", "CodeBuddy CN")
                .replace("@@NAME@@", "buddycn")
                .replace("@@LICENSE@@", "MIT")
            )
            with open(xml_path, "w", encoding="utf-8") as f:
                f.write(txt)

    apparmor_dir = os.path.join(root_dir, "usr/share/buddycn/apparmor.d")
    os.makedirs(apparmor_dir, exist_ok=True)
    apparmor_file = os.path.join(apparmor_dir, "buddycn")
    with open(apparmor_file, "w", encoding="utf-8") as f:
        f.write(APPARMOR_PROFILE_CN)
    os.chmod(apparmor_file, 0o644)

    sandbox_path = os.path.join(root_dir, "usr/share/buddycn/chrome-sandbox")
    os.chmod(sandbox_path, 0o4755)

    installed_kib = write_md5sums(root_dir, debian_dir)
    control_content = f"""Package: codebuddy-cn
Version: {pkg_ver}
Section: devel
Priority: optional
Architecture: amd64
Maintainer: CodeBuddy Team <codebuddy@tencent.com>
Homepage: https://www.codebuddy.ai
Installed-Size: {installed_kib}
Pre-Depends: dpkg (>= 1.16.1)
Depends: ca-certificates,
 libc6 (>= 2.33),
 libstdc++6 (>= 11),
 libasound2 (>= 1.0.17) | libasound2t64,
 libatk-bridge2.0-0 (>= 2.5.3) | libatk-bridge2.0-0t64,
 libatk1.0-0 (>= 2.11.90) | libatk1.0-0t64,
 libatspi2.0-0 (>= 2.9.90) | libatspi2.0-0t64,
 libcairo2 (>= 1.6.0) | libcairo2t64,
 libcups2 (>= 1.6.0) | libcups2t64,
 libcurl3-gnutls | libcurl3-nss | libcurl4 | libcurl4t64 | libcurl3,
 libdbus-1-3 (>= 1.9.14) | libdbus-1-3t64,
 libdrm2 (>= 2.4.60),
 libexpat1 (>= 2.1~beta3) | libexpat1t64,
 libgbm1 (>= 17.1.0~rc2),
 libglib2.0-0 (>= 2.37.3) | libglib2.0-0t64,
 libgtk-3-0 (>= 3.9.10) | libgtk-3-0t64 | libgtk-4-1,
 libnspr4 (>= 4.13),
 libnss3 (>= 3.26),
 libpango-1.0-0 (>= 1.14.0) | libpango-1.0-0t64,
 libudev1 (>= 183),
 libx11-6,
 libxcb1 (>= 1.9.2),
 libxcomposite1 (>= 0.4.4) | libxcomposite1t64,
 libxdamage1 (>= 1.1) | libxdamage1t64,
 libxext6 | libxext6t64,
 libxfixes3 | libxfixes3t64,
 libxkbcommon0 (>= 0.5.0),
 libxkbfile1 (>= 1.1.0) | libxkbfile1t64,
 libxrandr2 | libxrandr2t64,
 libxss1 | libxss1t64,
 libxtst6 | libxtst6t64,
 xdg-utils (>= 1.0.2)
Recommends: libvulkan1
Description: CodeBuddy CN - IDE for Linux.
 CodeBuddy CN integrated development environment.
 Supports Ubuntu 22.04 LTS and Ubuntu 24.04 LTS.
 .
 For more information, visit https://www.codebuddy.ai
"""
    for fname, content, mode in (
        ("control", control_content, 0o644),
        ("postinst", DEB_POSTINST_CN, 0o755),
        ("prerm", DEB_PRERM_CN, 0o755),
        ("postrm", DEB_POSTRM_CN, 0o755),
    ):
        p = os.path.join(debian_dir, fname)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
        os.chmod(p, mode)


def build_intl_tree(win_app_dir, linux_base_share_dir, work_dir, full_tag):
    root_dir = os.path.join(work_dir, "root")
    debian_dir = os.path.join(work_dir, "DEBIAN")
    cb_dir = os.path.join(root_dir, "usr/share/codebuddy")
    app_dir = os.path.join(cb_dir, "resources/app")

    if os.path.exists(work_dir):
        shutil.rmtree(work_dir)
    os.makedirs(cb_dir, exist_ok=True)
    os.makedirs(debian_dir, exist_ok=True)

    # 1. Copy Electron runtime files
    for item in os.listdir(linux_base_share_dir):
        if item in ("resources", "bin", "buddycn", "apparmor.d"):
            continue
        src = os.path.join(linux_base_share_dir, item)
        dst = os.path.join(cb_dir, item)
        if os.path.isdir(src):
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)

    shutil.copy2(os.path.join(linux_base_share_dir, "buddycn"), os.path.join(cb_dir, "codebuddy"))

    # 2. Copy resources/app from win_app_dir
    shutil.copytree(win_app_dir, app_dir)

    # 3. Copy Linux native addons
    linux_nm = os.path.join(linux_base_share_dir, "resources/app/node_modules")
    app_nm = os.path.join(app_dir, "node_modules")
    for subpath in [
        "@parcel/watcher/build/Release/watcher.node",
        "@vscode/spdlog/build/Release/spdlog.node",
        "@vscode/sqlite3/build/Release/vscode-sqlite3.node",
        "kerberos/build/Release/kerberos.node",
        "node-pty/build/Release/pty.node",
        "@vscode/ripgrep/bin/rg",
    ]:
        s = os.path.join(linux_nm, subpath)
        d = os.path.join(app_nm, subpath)
        os.makedirs(os.path.dirname(d), exist_ok=True)
        shutil.copy2(s, d)

    spdlog_path = os.path.join(app_nm, "@vscode/spdlog/build/Release/spdlog.node")
    if os.path.exists(spdlog_path):
        patch_spdlog_file(spdlog_path)

    rg_exe = os.path.join(app_nm, "@vscode/ripgrep/bin/rg.exe")
    if os.path.exists(rg_exe):
        os.remove(rg_exe)

    # 4. Icon
    res_linux = os.path.join(app_dir, "resources/linux")
    os.makedirs(res_linux, exist_ok=True)
    icon_src = os.path.join(app_dir, "resources/win32/code_150x150.png")
    shutil.copy2(icon_src, os.path.join(res_linux, "code.png"))

    pixmaps_dir = os.path.join(root_dir, "usr/share/pixmaps")
    os.makedirs(pixmaps_dir, exist_ok=True)
    shutil.copy2(icon_src, os.path.join(pixmaps_dir, "codebuddy.png"))

    # 5. Desktop entry
    apps_dir = os.path.join(root_dir, "usr/share/applications")
    os.makedirs(apps_dir, exist_ok=True)
    with open(os.path.join(apps_dir, "codebuddy.desktop"), "w", encoding="utf-8") as f:
        f.write(DESKTOP_ENTRY_INTL)

    # 6. MIME & AppData
    mime_dir = os.path.join(root_dir, "usr/share/mime/packages")
    os.makedirs(mime_dir, exist_ok=True)
    with open(os.path.join(mime_dir, "codebuddy-workspace.xml"), "w", encoding="utf-8") as f:
        f.write(MIME_XML_INTL)

    appdata_dir = os.path.join(root_dir, "usr/share/appdata")
    os.makedirs(appdata_dir, exist_ok=True)
    with open(os.path.join(appdata_dir, "codebuddy.appdata.xml"), "w", encoding="utf-8") as f:
        f.write(APPDATA_XML_INTL)

    # 7. AppArmor profile
    apparmor_dir = os.path.join(cb_dir, "apparmor.d")
    os.makedirs(apparmor_dir, exist_ok=True)
    with open(os.path.join(apparmor_dir, "codebuddy"), "w", encoding="utf-8") as f:
        f.write(APPARMOR_PROFILE_INTL)

    # 8. Bin launcher scripts
    bin_dir = os.path.join(cb_dir, "bin")
    os.makedirs(bin_dir, exist_ok=True)
    shutil.copy2(os.path.join(linux_base_share_dir, "bin/code-desktop-ime.sh"), os.path.join(bin_dir, "code-desktop-ime.sh"))
    with open(os.path.join(bin_dir, "codebuddy"), "w", encoding="utf-8") as f:
        f.write(LAUNCHER_SCRIPT_INTL)
    os.chmod(os.path.join(bin_dir, "codebuddy"), 0o755)

    buddy_link = os.path.join(bin_dir, "buddy")
    if os.path.lexists(buddy_link):
        os.remove(buddy_link)
    os.symlink("codebuddy", buddy_link)

    # 9. Shims and permissions
    with open(os.path.join(app_dir, "node_modules/native-keymap/index.js"), "w", encoding="utf-8") as f:
        f.write(NATIVE_KEYMAP_INDEX)
    with open(os.path.join(app_dir, "node_modules/native-watchdog/index.js"), "w", encoding="utf-8") as f:
        f.write(NATIVE_WATCHDOG_INDEX)

    os.chmod(os.path.join(cb_dir, "codebuddy"), 0o755)
    os.chmod(os.path.join(cb_dir, "chrome-sandbox"), 0o4755)
    trash_bin = os.path.join(app_dir, "extensions/genie/out/vendor/genie-trash/linux-x64")
    if os.path.exists(trash_bin):
        os.chmod(trash_bin, 0o755)
    rg_bin = os.path.join(app_nm, "@vscode/ripgrep/bin/rg")
    if os.path.exists(rg_bin):
        os.chmod(rg_bin, 0o755)

    # 10. DEBIAN metadata
    installed_kib = write_md5sums(root_dir, debian_dir)
    control_content = f"""Package: codebuddy
Version: {full_tag}
Section: devel
Priority: optional
Architecture: amd64
Provides: buddy
Maintainer: CodeBuddy Team <codebuddy@tencent.com>
Homepage: https://www.codebuddy.ai
Installed-Size: {installed_kib}
Pre-Depends: dpkg (>= 1.16.1)
Depends: ca-certificates,
 libc6 (>= 2.33),
 libstdc++6 (>= 11),
 libasound2 (>= 1.0.17) | libasound2t64,
 libatk-bridge2.0-0 (>= 2.5.3) | libatk-bridge2.0-0t64,
 libatk1.0-0 (>= 2.11.90) | libatk1.0-0t64,
 libatspi2.0-0 (>= 2.9.90) | libatspi2.0-0t64,
 libcairo2 (>= 1.6.0) | libcairo2t64,
 libcups2 (>= 1.6.0) | libcups2t64,
 libcurl3-gnutls | libcurl3-nss | libcurl4 | libcurl4t64 | libcurl3,
 libdbus-1-3 (>= 1.9.14) | libdbus-1-3t64,
 libdrm2 (>= 2.4.60),
 libexpat1 (>= 2.1~beta3) | libexpat1t64,
 libgbm1 (>= 17.1.0~rc2),
 libglib2.0-0 (>= 2.37.3) | libglib2.0-0t64,
 libgtk-3-0 (>= 3.9.10) | libgtk-3-0t64 | libgtk-4-1,
 libnspr4 (>= 4.13),
 libnss3 (>= 3.26),
 libpango-1.0-0 (>= 1.14.0) | libpango-1.0-0t64,
 libudev1 (>= 183),
 libx11-6,
 libxcb1 (>= 1.9.2),
 libxcomposite1 (>= 0.4.4) | libxcomposite1t64,
 libxdamage1 (>= 1.1) | libxdamage1t64,
 libxext6 | libxext6t64,
 libxfixes3 | libxfixes3t64,
 libxkbcommon0 (>= 0.5.0),
 libxkbfile1 (>= 1.1.0) | libxkbfile1t64,
 libxrandr2 | libxrandr2t64,
 libxss1 | libxss1t64,
 libxtst6 | libxtst6t64,
 xdg-utils (>= 1.0.2)
Recommends: libvulkan1
Description: CodeBuddy - IDE for Linux.
 CodeBuddy integrated development environment.
 Supports Ubuntu 22.04 LTS and Ubuntu 24.04 LTS.
 .
 For more information, visit https://www.codebuddy.ai
"""
    for fname, content, mode in (
        ("control", control_content, 0o644),
        ("postinst", DEB_POSTINST_INTL, 0o755),
        ("prerm", DEB_PRERM_INTL, 0o755),
        ("postrm", DEB_POSTRM_INTL, 0o755),
    ):
        p = os.path.join(debian_dir, fname)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
        os.chmod(p, mode)

    return root_dir, debian_dir


def write_md5sums(root_dir, debian_dir):
    lines = []
    total_bytes = 0
    for dirpath, dirnames, filenames in os.walk(root_dir):
        dirnames.sort()
        for fname in sorted(filenames):
            fpath = os.path.join(dirpath, fname)
            if os.path.islink(fpath):
                continue
            rel = os.path.relpath(fpath, root_dir)
            with open(fpath, "rb") as f:
                content = f.read()
            total_bytes += len(content)
            digest = hashlib.md5(content).hexdigest()
            lines.append(f"{digest}  {rel}\n")

    md5sums_path = os.path.join(debian_dir, "md5sums")
    with open(md5sums_path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    os.chmod(md5sums_path, 0o644)
    return (total_bytes + 1023) // 1024


def build_deb(root_dir, debian_dir, out_deb, tmp_base):
    tmp_dir = os.path.join(tmp_base, "tmp_deb_build")
    os.makedirs(tmp_dir, exist_ok=True)
    try:
        debian_bin = os.path.join(tmp_dir, "debian-binary")
        with open(debian_bin, "wb") as f:
            f.write(b"2.0\n")

        control_tar_xz = os.path.join(tmp_dir, "control.tar.xz")
        data_tar_xz = os.path.join(tmp_dir, "data.tar.xz")

        subprocess.run(
            f"tar --owner=0 --group=0 --numeric-owner -C {debian_dir} -cf - . | xz -T0 -6 -c > {control_tar_xz}",
            shell=True,
            check=True,
        )
        subprocess.run(
            f"tar --owner=0 --group=0 --numeric-owner -C {root_dir} -cf - . | xz -T0 -6 -c > {data_tar_xz}",
            shell=True,
            check=True,
        )

        if os.path.exists(out_deb):
            os.remove(out_deb)
        subprocess.run(
            ["ar", "rcsD", out_deb, debian_bin, control_tar_xz, data_tar_xz],
            check=True,
        )
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    print(f"Built {out_deb} ({os.path.getsize(out_deb)} bytes)")


def pack_header(entries, region_tag):
    entries = sorted(entries, key=lambda x: x[0])
    idx_list = []
    data_store = bytearray()
    for tag, dtype, count, raw in entries:
        align = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 1, 9: 1}[dtype]
        while len(data_store) % align != 0:
            data_store.append(0)
        idx_list.append(struct.pack(">IIII", tag, dtype, len(data_store), count))
        data_store.extend(raw)
    new_il = len(entries) + 1
    trailer = struct.pack(">IIiI", region_tag, 7, -new_il * 16, 16)
    reg_idx = struct.pack(">IIII", region_tag, 7, len(data_store), 16)
    data_store.extend(trailer)
    return (
        b"\x8e\xad\xe8\x01\x00\x00\x00\x00"
        + struct.pack(">II", new_il, len(data_store))
        + reg_idx
        + b"".join(idx_list)
        + bytes(data_store)
    )


def str_entry(tag, s):
    return (tag, 6, 1, s.encode("utf-8") + b"\x00")


def str_arr_entry(tag, arr, dtype=8):
    return (tag, dtype, len(arr), b"".join(s.encode("utf-8") + b"\x00" for s in arr))


def int32_entry(tag, arr):
    return (tag, 4, len(arr), struct.pack(f">{len(arr)}I", *[x & 0xFFFFFFFF for x in arr]))


def int16_entry(tag, arr):
    return (tag, 3, len(arr), struct.pack(f">{len(arr)}H", *[x & 0xFFFF for x in arr]))


def cpio_header(ino, mode, uid, gid, nlink, mtime, filesize, devmajor, devminor, name_b):
    hdr = (
        f"070701"
        f"{ino:08x}{mode:08x}{uid:08x}{gid:08x}"
        f"{nlink:08x}{mtime:08x}{filesize:08x}"
        f"{devmajor:08x}{devminor:08x}{0:08x}{0:08x}"
        f"{len(name_b):08x}00000000"
    ).encode("ascii")
    out = bytearray(hdr) + name_b
    while len(out) % 4 != 0:
        out.append(0)
    return bytes(out)


def build_rpm(
    root_dir,
    out_rpm,
    pkg_ver,
    pkg_rel,
    tmp_base,
    pkg_name="codebuddy-cn",
    provides=None,
    summary="CodeBuddy CN - IDE for Linux.",
    description=None,
    postin=RPM_POSTIN_CN,
    preun=RPM_PREUN_CN,
    postun=RPM_POSTUN_CN,
    binary_sandbox_path="/usr/share/buddycn/chrome-sandbox",
):
    if provides is None:
        provides = [pkg_name, f"{pkg_name}(x86-64)", "buddycn"]
    if description is None:
        description = (
            f"{pkg_name} integrated development environment.\n"
            "Supports CentOS Stream 9 and CentOS Stream 10 (x86_64).\n"
            "For more information, visit https://www.codebuddy.ai"
        )

    system_dirs = {
        "/usr",
        "/usr/bin",
        "/usr/share",
        "/usr/share/appdata",
        "/usr/share/applications",
        "/usr/share/doc",
        "/usr/share/mime",
        "/usr/share/mime/packages",
        "/usr/share/pixmaps",
    }

    all_paths = []
    for dirpath, _, filenames in os.walk(root_dir):
        rel_dir = "/" + os.path.relpath(dirpath, root_dir)
        if rel_dir != "/." and rel_dir not in system_dirs:
            all_paths.append((rel_dir, dirpath))
        for fname in filenames:
            fpath = os.path.join(dirpath, fname)
            rel_file = "/" + os.path.relpath(fpath, root_dir)
            all_paths.append((rel_file, fpath))

    all_paths.sort(key=lambda x: x[0])

    dirnames = []
    dir_map = {}
    dirindexes = []
    basenames = []
    filesizes = []
    filemodes = []
    filerdevs = []
    filemtimes = []
    filedigests = []
    filelinktos = []
    fileflags = []
    fileusername = []
    filegroupname = []
    fileverifyflags = []
    filedevices = []
    fileinodes = []
    filelangs = []

    tmp_rpm_dir = os.path.join(tmp_base, "tmp_rpm_build")
    os.makedirs(tmp_rpm_dir, exist_ok=True)
    compressed_cpio_path = os.path.join(tmp_rpm_dir, "payload.cpio.xz")

    uncompressed_sha256 = hashlib.sha256()
    uncompressed_size = 0

    xz_proc = subprocess.Popen(
        ["xz", "-T0", "-6", "-c"],
        stdin=subprocess.PIPE,
        stdout=open(compressed_cpio_path, "wb"),
    )

    def write_cpio(chunk):
        nonlocal uncompressed_size
        uncompressed_sha256.update(chunk)
        uncompressed_size += len(chunk)
        xz_proc.stdin.write(chunk)

    try:
        for idx, (fullpath, hostpath) in enumerate(all_paths, 1):
            d, b = os.path.split(fullpath)
            d = d + "/"
            if d not in dir_map:
                dir_map[d] = len(dirnames)
                dirnames.append(d)
            dirindexes.append(dir_map[d])
            basenames.append(b)

            st = os.lstat(hostpath)
            mtime = int(st.st_mtime) if st.st_mtime > 315532800 else BUILD_TIME

            if stat.S_ISLNK(st.st_mode):
                mode = stat.S_IFLNK | 0o777
                linkto = os.readlink(hostpath)
                content = linkto.encode("utf-8")
                fsize = len(content)
                digest = ""
                nlink = 1
            elif stat.S_ISDIR(st.st_mode):
                mode = stat.S_IFDIR | 0o755
                linkto = ""
                content = b""
                fsize = 0
                digest = ""
                nlink = 2
            else:
                perm = stat.S_IMODE(st.st_mode)
                if fullpath == binary_sandbox_path:
                    perm = 0o4755
                mode = stat.S_IFREG | perm
                linkto = ""
                with open(hostpath, "rb") as f:
                    content = f.read()
                fsize = len(content)
                digest = hashlib.sha256(content).hexdigest()
                nlink = 1

            filesizes.append(fsize)
            filemodes.append(mode)
            filerdevs.append(0)
            filemtimes.append(mtime)
            filedigests.append(digest)
            filelinktos.append(linkto)
            fileflags.append(0)
            fileusername.append("root")
            filegroupname.append("root")
            fileverifyflags.append(0xFFFFFFFF)
            filedevices.append(1)
            fileinodes.append(idx)
            filelangs.append("")

            name_b = ("." + fullpath).encode("utf-8") + b"\x00"
            hdr_bytes = cpio_header(
                ino=idx,
                mode=mode,
                uid=0,
                gid=0,
                nlink=nlink,
                mtime=mtime,
                filesize=len(content),
                devmajor=0,
                devminor=1,
                name_b=name_b,
            )
            write_cpio(hdr_bytes)
            if content:
                write_cpio(content)
                rem = len(content) % 4
                if rem != 0:
                    write_cpio(b"\x00" * (4 - rem))

        write_cpio(cpio_header(0, 0, 0, 0, 1, 0, 0, 0, 0, b"TRAILER!!!\x00"))
        xz_proc.stdin.close()
        ret = xz_proc.wait()
        if ret != 0:
            raise RuntimeError(f"xz exited with {ret}")

        with open(compressed_cpio_path, "rb") as f:
            compressed_cpio = f.read()
    finally:
        shutil.rmtree(tmp_rpm_dir, ignore_errors=True)

    payload_sha256_hex = hashlib.sha256(compressed_cpio).hexdigest()
    payload_alt_sha256_hex = uncompressed_sha256.hexdigest()

    req_tuples = [
        ("/bin/sh", "", 0x00000500),
        ("/bin/sh", "", 0x00000900),
        ("/bin/sh", "", 0x00001100),
        ("ca-certificates", "", 0),
        ("ld-linux-x86-64.so.2()(64bit)", "", 0),
        ("libX11.so.6()(64bit)", "", 0),
        ("libXcomposite.so.1()(64bit)", "", 0),
        ("libXdamage.so.1()(64bit)", "", 0),
        ("libXext.so.6()(64bit)", "", 0),
        ("libXfixes.so.3()(64bit)", "", 0),
        ("libXrandr.so.2()(64bit)", "", 0),
        ("libXtst.so.6()(64bit)", "", 0),
        ("libasound.so.2()(64bit)", "", 0),
        ("libatk-1.0.so.0()(64bit)", "", 0),
        ("libatk-bridge-2.0.so.0()(64bit)", "", 0),
        ("libatspi.so.0()(64bit)", "", 0),
        ("libc.so.6()(64bit)", "", 0),
        ("libc.so.6(GLIBC_2.33)(64bit)", "", 0),
        ("libcairo.so.2()(64bit)", "", 0),
        ("libcups.so.2()(64bit)", "", 0),
        ("libdbus-1.so.3()(64bit)", "", 0),
        ("libdl.so.2()(64bit)", "", 0),
        ("libdrm.so.2()(64bit)", "", 0),
        ("libexpat.so.1()(64bit)", "", 0),
        ("libgbm.so.1()(64bit)", "", 0),
        ("libgcc_s.so.1()(64bit)", "", 0),
        ("libgcc_s.so.1(GCC_3.0)(64bit)", "", 0),
        ("libgio-2.0.so.0()(64bit)", "", 0),
        ("libglib-2.0.so.0()(64bit)", "", 0),
        ("libgobject-2.0.so.0()(64bit)", "", 0),
        ("libgtk-3.so.0()(64bit)", "", 0),
        ("libm.so.6()(64bit)", "", 0),
        ("libnspr4.so()(64bit)", "", 0),
        ("libnss3.so()(64bit)", "", 0),
        ("libnssutil3.so()(64bit)", "", 0),
        ("libpango-1.0.so.0()(64bit)", "", 0),
        ("libpthread.so.0()(64bit)", "", 0),
        ("libsmime3.so()(64bit)", "", 0),
        ("libstdc++.so.6()(64bit)", "", 0),
        ("libstdc++.so.6(CXXABI_1.3)(64bit)", "", 0),
        ("libstdc++.so.6(GLIBCXX_3.4.29)(64bit)", "", 0),
        ("libudev.so.1()(64bit)", "", 0),
        ("libutil.so.1()(64bit)", "", 0),
        ("libxcb.so.1()(64bit)", "", 0),
        ("libxkbcommon.so.0()(64bit)", "", 0),
        ("libxkbfile.so.1()(64bit)", "", 0),
        ("rpmlib(CompressedFileNames)", "3.0.4-1", 0x0100000A),
        ("rpmlib(FileDigests)", "4.6.0-1", 0x0100000A),
        ("rpmlib(PayloadFilesHavePrefix)", "4.0-1", 0x0100000A),
        ("rpmlib(PayloadIsXz)", "5.2-1", 0x0100000A),
        ("rtld(GNU_HASH)", "", 0),
        ("xdg-utils", "", 0),
    ]

    req_names = [r[0] for r in req_tuples]
    req_vers = [r[1] for r in req_tuples]
    req_flags = [r[2] for r in req_tuples]
    evr = f"{pkg_ver}-{pkg_rel}"

    entries = [
        str_arr_entry(100, ["C"], 8),
        str_entry(1000, pkg_name),
        str_entry(1001, pkg_ver),
        str_entry(1002, pkg_rel),
        str_arr_entry(1004, [summary], 9),
        str_arr_entry(1005, [description], 9),
        int32_entry(1006, [BUILD_TIME]),
        str_entry(1007, "localhost"),
        int32_entry(1009, [sum(filesizes)]),
        str_entry(1011, "Tencent"),
        str_entry(1014, "MIT"),
        str_entry(1015, "CodeBuddy Team <codebuddy@tencent.com>"),
        str_entry(1016, "Development/Tools"),
        str_entry(1020, "https://www.codebuddy.ai"),
        str_entry(1021, "linux"),
        str_entry(1022, "x86_64"),
        str_entry(1024, postin),
        str_entry(1025, preun),
        str_entry(1026, postun),
        int32_entry(1028, filesizes),
        int16_entry(1030, filemodes),
        int16_entry(1033, filerdevs),
        int32_entry(1034, filemtimes),
        str_arr_entry(1035, filedigests, 8),
        str_arr_entry(1036, filelinktos, 8),
        int32_entry(1037, fileflags),
        str_arr_entry(1039, fileusername, 8),
        str_arr_entry(1040, filegroupname, 8),
        str_entry(1044, f"{pkg_name}-{evr}.src.rpm"),
        int32_entry(1045, fileverifyflags),
        int32_entry(1046, [uncompressed_size]),
        str_arr_entry(1047, provides, 8),
        int32_entry(1048, req_flags),
        str_arr_entry(1049, req_names, 8),
        str_arr_entry(1050, req_vers, 8),
        str_entry(1064, "4.19.1.1"),
        str_entry(1086, "/bin/sh"),
        str_entry(1087, "/bin/sh"),
        str_entry(1088, "/bin/sh"),
        int32_entry(1095, filedevices),
        int32_entry(1096, fileinodes),
        str_arr_entry(1097, filelangs, 8),
        int32_entry(1112, [8] * len(provides)),
        str_arr_entry(1113, [evr] * len(provides), 8),
        int32_entry(1116, dirindexes),
        str_arr_entry(1117, basenames, 8),
        str_arr_entry(1118, dirnames, 8),
        str_entry(1124, "cpio"),
        str_entry(1125, "xz"),
        str_entry(1126, "6"),
        str_entry(1132, "x86_64-redhat-linux-gnu"),
        int32_entry(5011, [8]),
        str_entry(5062, "utf-8"),
        str_arr_entry(5092, [payload_sha256_hex], 8),
        int32_entry(5093, [8]),
        str_arr_entry(5097, [payload_alt_sha256_hex], 8),
    ]

    main_hdr = pack_header(entries, 63)
    sig_entries = [
        (269, 6, 1, hashlib.sha1(main_hdr).hexdigest().encode("ascii") + b"\x00"),
        (273, 6, 1, hashlib.sha256(main_hdr).hexdigest().encode("ascii") + b"\x00"),
        (1000, 4, 1, struct.pack(">I", len(main_hdr) + len(compressed_cpio))),
        (1004, 7, 16, hashlib.md5(main_hdr + compressed_cpio).digest()),
    ]
    sig_hdr = pack_header(sig_entries, 62)
    while len(sig_hdr) % 8 != 0:
        sig_hdr += b"\x00"

    lead_name = f"{pkg_name}-{evr}".encode("ascii")[:65]
    lead = struct.pack(
        ">4sBBhh66shh16s",
        b"\xed\xab\xee\xdb",
        3,
        0,
        0,
        1,
        lead_name,
        1,
        5,
        b"\x00" * 16,
    )

    with open(out_rpm, "wb") as f:
        f.write(lead)
        f.write(sig_hdr)
        f.write(main_hdr)
        f.write(compressed_cpio)

    print(f"Built {out_rpm} ({os.path.getsize(out_rpm)} bytes)")


def parse_version_info(pkg_name):
    m = re.search(r"CodeBuddy-(?:linux|win32)-x64(?:-user)?-(\d+\.\d+\.\d+)\.(\d+)-([0-9a-f]+)", pkg_name)
    if m:
        is_cn = "-cn" in pkg_name
        return m.group(1), f"{m.group(2)}.{m.group(3)}", f"{m.group(1)}.{m.group(2)}-{m.group(3)}", is_cn
    return "4.12.0", "37847260.b4c35ed0", "4.12.0.37847260-b4c35ed0", True


def main():
    parser = argparse.ArgumentParser(description="Build CodeBuddy packages for Ubuntu 22.04/24.04 and CentOS Stream 9/10.")
    parser.add_argument(
        "-i",
        "--input",
        default="/home/shawn/下载/CodeBuddy-win32-x64-user-4.12.1.39217423-757a5b2f.exe",
        help="Path to upstream CodeBuddy package (.deb or .exe)",
    )
    parser.add_argument("-o", "--out-dir", default=".", help="Output directory for built packages")
    parser.add_argument("-w", "--work-dir", default="", help="Staging directory")
    parser.add_argument(
        "--edition",
        choices=["auto", "cn", "intl"],
        default="auto",
        help="Edition to build (auto, cn, or intl)",
    )
    args = parser.parse_args()

    out_dir = os.path.abspath(args.out_dir)
    pkg_ver_base, pkg_rel, full_tag, is_cn_detected = parse_version_info(os.path.basename(args.input))

    if args.edition == "cn" or (args.edition == "auto" and is_cn_detected):
        work_dir = os.path.abspath(args.work_dir) if args.work_dir else os.path.abspath("./inspect_deb")
        root_dir = os.path.join(work_dir, "root")
        debian_dir = os.path.join(work_dir, "DEBIAN")

        if not os.path.isdir(root_dir) or not os.path.isdir(debian_dir):
            if not os.path.isfile(args.input):
                sys.exit(f"Input package not found: {args.input}")
            extract_upstream_deb(args.input, work_dir)

        apply_cn_tree_fixes(root_dir, debian_dir, pkg_ver_base)
        out_deb = os.path.join(out_dir, f"CodeBuddy-linux-x64-{full_tag}-cn.ubuntu22.04-24.04.amd64.deb")
        out_rpm = os.path.join(out_dir, f"CodeBuddy-linux-x64-{full_tag}-cn.el9-el10.x86_64.rpm")

        build_deb(root_dir, debian_dir, out_deb, out_dir)
        build_rpm(root_dir, out_rpm, pkg_ver_base, pkg_rel, out_dir)
    else:
        # International edition
        work_dir = os.path.abspath(args.work_dir) if args.work_dir else os.path.abspath("./inspect_intl")
        win_extract_dir = os.path.abspath("./win_extract")
        win_app_dir = os.path.join(win_extract_dir, "resources/app")

        if not os.path.isdir(win_app_dir):
            sys.exit(f"Extracted Windows app directory not found at {win_app_dir}. Please extract the installer first.")

        linux_base_share_dir = os.path.abspath("./inspect_deb/root/usr/share/buddycn")
        if not os.path.isdir(linux_base_share_dir):
            sys.exit(f"Linux Electron host files not found at {linux_base_share_dir}.")

        root_dir, debian_dir = build_intl_tree(win_app_dir, linux_base_share_dir, work_dir, full_tag)

        out_deb = os.path.join(out_dir, f"CodeBuddy-linux-x64-{full_tag}.ubuntu22.04-24.04.amd64.deb")
        out_rpm = os.path.join(out_dir, f"CodeBuddy-linux-x64-{full_tag}.el9-el10.x86_64.rpm")

        build_deb(root_dir, debian_dir, out_deb, out_dir)
        build_rpm(
            root_dir=root_dir,
            out_rpm=out_rpm,
            pkg_ver=f"{pkg_ver_base}.{pkg_rel.split('.')[0]}",
            pkg_rel=pkg_rel.split('.')[1] if '.' in pkg_rel else "1",
            tmp_base=out_dir,
            pkg_name="codebuddy",
            provides=["codebuddy", "codebuddy(x86-64)", "buddy"],
            summary="CodeBuddy - IDE for Linux.",
            description=(
                "CodeBuddy integrated development environment.\n"
                "Supports CentOS Stream 9 and CentOS Stream 10 (x86_64).\n"
                "For more information, visit https://www.codebuddy.ai"
            ),
            postin=RPM_POSTIN_INTL,
            preun=RPM_PREUN_INTL,
            postun=RPM_POSTUN_INTL,
            binary_sandbox_path="/usr/share/codebuddy/chrome-sandbox",
        )


if __name__ == "__main__":
    main()
