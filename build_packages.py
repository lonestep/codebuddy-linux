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

APPARMOR_PROFILE = """abi <abi/4.0>,
include <tunables/global>

profile buddycn /usr/share/buddycn/buddycn flags=(unconfined) {
  userns,

  include if exists <local/buddycn>
}
"""

DEB_POSTINST = """#!/usr/bin/env bash
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

DEB_PRERM = """#!/usr/bin/env bash
set -e

if command -v update-alternatives >/dev/null 2>&1; then
\tupdate-alternatives --remove editor /usr/bin/buddycn || true
fi
"""

DEB_POSTRM = """#!/usr/bin/env bash
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

RPM_POSTIN = """#!/bin/sh
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

RPM_PREUN = """#!/bin/sh
if [ "$1" = "0" ]; then
    if command -v update-alternatives >/dev/null 2>&1; then
        update-alternatives --remove editor /usr/bin/buddycn 2>/dev/null || true
    fi
fi
exit 0
"""

RPM_POSTUN = """#!/bin/sh
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


def patch_spdlog(root_dir):
    # Downgrade std::condition_variable::wait symbol version from GLIBCXX_3.4.30 (index 7)
    # to GLIBCXX_3.4.11 (index 12) so spdlog.node loads on CentOS Stream 9 (libstdc++ 6.0.29).
    spdlog_path = os.path.join(
        root_dir,
        "usr/share/buddycn/resources/app/node_modules/@vscode/spdlog/build/Release/spdlog.node",
    )
    with open(spdlog_path, "rb") as f:
        data = bytearray(f.read())

    versym_off = 104178
    verneed_off = 106160
    cur_ver = struct.unpack_from("<H", data, versym_off + 14 * 2)[0]
    if cur_ver == 7:
        struct.pack_into("<H", data, versym_off + 14 * 2, 12)
        struct.pack_into("<H", data, verneed_off + 0xB0 + 2, 15)
        struct.pack_into("<I", data, verneed_off + 0x160 + 12, 0x20)
        data[verneed_off + 0x170 : verneed_off + 0x180] = b"\x00" * 16
        data = data.replace(b"GLIBCXX_3.4.30\x00", b"GLIBCXX_3.4.11\x00")
        with open(spdlog_path, "wb") as f:
            f.write(data)


def apply_tree_fixes(root_dir, debian_dir, pkg_ver):
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
        f.write(APPARMOR_PROFILE)
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
        ("postinst", DEB_POSTINST, 0o755),
        ("prerm", DEB_PRERM, 0o755),
        ("postrm", DEB_POSTRM, 0o755),
    ):
        p = os.path.join(debian_dir, fname)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
        os.chmod(p, mode)


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


def build_rpm(root_dir, out_rpm, pkg_ver, pkg_rel, tmp_base):
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
                if fullpath == "/usr/share/buddycn/chrome-sandbox":
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
        str_entry(1000, "codebuddy-cn"),
        str_entry(1001, pkg_ver),
        str_entry(1002, pkg_rel),
        str_arr_entry(1004, ["CodeBuddy CN - IDE for Linux."], 9),
        str_arr_entry(
            1005,
            [
                "CodeBuddy CN integrated development environment.\n"
                "Supports CentOS Stream 9 and CentOS Stream 10 (x86_64).\n"
                "For more information, visit https://www.codebuddy.ai"
            ],
            9,
        ),
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
        str_entry(1024, RPM_POSTIN),
        str_entry(1025, RPM_PREUN),
        str_entry(1026, RPM_POSTUN),
        int32_entry(1028, filesizes),
        int16_entry(1030, filemodes),
        int16_entry(1033, filerdevs),
        int32_entry(1034, filemtimes),
        str_arr_entry(1035, filedigests, 8),
        str_arr_entry(1036, filelinktos, 8),
        int32_entry(1037, fileflags),
        str_arr_entry(1039, fileusername, 8),
        str_arr_entry(1040, filegroupname, 8),
        str_entry(1044, f"codebuddy-cn-{evr}.src.rpm"),
        int32_entry(1045, fileverifyflags),
        int32_entry(1046, [uncompressed_size]),
        str_arr_entry(1047, ["codebuddy-cn", "codebuddy-cn(x86-64)", "buddycn"], 8),
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
        int32_entry(1112, [8, 8, 8]),
        str_arr_entry(1113, [evr, evr, evr], 8),
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

    lead_name = f"codebuddy-cn-{evr}".encode("ascii")[:65]
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


def parse_version_info(deb_name):
    m = re.search(r"CodeBuddy-linux-x64-(\d+\.\d+\.\d+)\.(\d+)-([0-9a-f]+)-cn", deb_name)
    if m:
        return m.group(1), f"{m.group(2)}.{m.group(3)}", f"{m.group(1)}.{m.group(2)}-{m.group(3)}"
    return "4.12.0", "37847260.b4c35ed0", "4.12.0.37847260-b4c35ed0"


def main():
    parser = argparse.ArgumentParser(description="Repack CodeBuddy CN for Ubuntu 22.04/24.04 and CentOS Stream 9/10.")
    parser.add_argument(
        "-i",
        "--input",
        default="/home/shawn/下载/CodeBuddy-linux-x64-4.12.0.37847260-b4c35ed0-cn.deb",
        help="Path to upstream CodeBuddy .deb package",
    )
    parser.add_argument("-o", "--out-dir", default=".", help="Output directory for built packages")
    parser.add_argument("-w", "--work-dir", default="./inspect_deb", help="Staging directory")
    args = parser.parse_args()

    out_dir = os.path.abspath(args.out_dir)
    work_dir = os.path.abspath(args.work_dir)
    root_dir = os.path.join(work_dir, "root")
    debian_dir = os.path.join(work_dir, "DEBIAN")

    if not os.path.isdir(root_dir) or not os.path.isdir(debian_dir):
        if not os.path.isfile(args.input):
            sys.exit(f"Input package not found: {args.input}")
        extract_upstream_deb(args.input, work_dir)

    pkg_ver, pkg_rel, full_tag = parse_version_info(os.path.basename(args.input))
    apply_tree_fixes(root_dir, debian_dir, pkg_ver)

    out_deb = os.path.join(out_dir, f"CodeBuddy-linux-x64-{full_tag}-cn.ubuntu22.04-24.04.amd64.deb")
    out_rpm = os.path.join(out_dir, f"CodeBuddy-linux-x64-{full_tag}-cn.el9-el10.x86_64.rpm")

    build_deb(root_dir, debian_dir, out_deb, out_dir)
    build_rpm(root_dir, out_rpm, pkg_ver, pkg_rel, out_dir)


if __name__ == "__main__":
    main()
