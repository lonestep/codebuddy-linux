# codebuddy-linux

CodeBuddy Linux 打包与修复脚本，基于官方安装程序构建适用于 **CentOS Stream 9 / 10** 与 **Ubuntu 22.04 / 24.04** 的安装包，支持国内版与国际版。

## 解决的问题

1. **CentOS Stream 9 `GLIBCXX_3.4.30` 符号缺失**：官方内置的 `@vscode/spdlog` (`spdlog.node`) 引用了 `std::condition_variable::wait@GLIBCXX_3.4.30`，而 CentOS Stream 9 的 `libstdc++.so.6.0.29` 最高仅提供 `GLIBCXX_3.4.29`。脚本将该符号版本映射回 ABI 一致的 `GLIBCXX_3.4.11`。
2. **CentOS Stream 10 依赖兼容**：移除 EL10 已废弃的 `libXScrnSaver` (`libXss.so.1`) 依赖以及自带的 `libffmpeg.so` 依赖，保留 `el9` 与 `el10` 通用的 64 位 SONAME 依赖。
3. **Ubuntu 22.04 / 24.04 打包与沙箱问题**：
   - 移除上游 `postinst` / `postrm` 中残留的微软 `vscode.sources` 软件源写入与清理逻辑。
   - 补齐 `libcups2 | libcups2t64` 与 `*t64` 库依赖声明。
   - 针对 Ubuntu 24.04 默认开启的 AppArmor 非特权用户命名空间限制，增加 `/etc/apparmor.d` 策略并设置 `chrome-sandbox` 为 `4755`。
4. **国际版 Linux 构建**：官方国际版（4.12.1）仅发布了 Windows / macOS 安装包，脚本提取跨平台 workbench、AI 套件（支持 Claude 3.7/4.0、GPT-5、Gemini 2.5 等海外模型）与产品配置，结合 Linux Electron 宿主及修补后的 Linux 原生二进制组件，生成独立命名的 `codebuddy` Linux 安装包。
5. **外围修复**：在启动脚本中加载 `code-desktop-ime.sh` 输入法配置；替换桌面元数据中未展开的 `@@NAME@@` 占位符；为缺失 `.node` 的 `native-keymap` 和 `native-watchdog` 提供降级导出。

## 安装

从 [Releases](https://github.com/lonestep/codebuddy-linux/releases) 下载对应系统的安装包：

### 国际版 (CodeBuddy)

CentOS Stream 9 / 10:
```bash
sudo dnf install -y ./CodeBuddy-linux-x64-4.12.1.39217423-757a5b2f.el9-el10.x86_64.rpm
```

Ubuntu 22.04 / 24.04:
```bash
sudo apt install -y ./CodeBuddy-linux-x64-4.12.1.39217423-757a5b2f.ubuntu22.04-24.04.amd64.deb
```

启动命令：`codebuddy` 或 `buddy`

### 国内版 (CodeBuddy CN)

CentOS Stream 9 / 10:
```bash
sudo dnf install -y ./CodeBuddy-linux-x64-4.12.0.37847260-b4c35ed0-cn.el9-el10.x86_64.rpm
```

Ubuntu 22.04 / 24.04:
```bash
sudo apt install -y ./CodeBuddy-linux-x64-4.12.0.37847260-b4c35ed0-cn.ubuntu22.04-24.04.amd64.deb
```

启动命令：`buddycn`

## 自行构建

构建国内版：
```bash
python3 build_packages.py -i /path/to/CodeBuddy-linux-x64-4.12.0.37847260-b4c35ed0-cn.deb -o .
```

构建国际版（依赖已解包的资源或指定安装包）：
```bash
python3 build_packages.py -i /path/to/CodeBuddy-win32-x64-user-4.12.1.39217423-757a5b2f.exe -o .
```

## 容器验证

```bash
podman run --rm --security-opt label=disable --network=host -v "$PWD":/pkg:ro quay.io/centos/centos:stream9 /pkg/verify_os.sh
podman run --rm --security-opt label=disable --network=host -v "$PWD":/pkg:ro quay.io/centos/centos:stream10 /pkg/verify_os.sh
podman run --rm --security-opt label=disable --network=host -v "$PWD":/pkg:ro ubuntu:22.04 /pkg/verify_os.sh
podman run --rm --security-opt label=disable --network=host -v "$PWD":/pkg:ro ubuntu:24.04 /pkg/verify_os.sh
```
