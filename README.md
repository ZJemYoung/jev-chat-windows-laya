# jev-chat-windows-laya

**Windows 版微信聊天副驾（上游 fork）**：本地 laya 判断引擎免密钥运行 + 修复高缩放屏抓取错位
*Windows fork of jev-chat: key-free local laya judge + DPI-aware screen capture fix*

<p>
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-blue.svg"></a>
  <img alt="Platform: Windows 10/11" src="https://img.shields.io/badge/platform-Windows%2010%2F11-0078D6.svg">
  <img alt="Python 3.10+" src="https://img.shields.io/badge/python-3.10%2B-3772AB.svg">
  <a href="https://github.com/Liyucheng1997/332_lab-jev-chat"><img alt="Fork of 332_lab-jev-chat" src="https://img.shields.io/badge/fork%20of-332__lab--jev--chat-8A2BE2.svg"></a>
  <a href="https://github.com/ZJemYoung/jev-chat-windows-laya/releases/tag/v1.1.0-laya.1"><img alt="Release" src="https://img.shields.io/badge/release-v1.1.0--laya.1-success.svg"></a>
</p>

> 本仓库是 [Liyucheng1997/332_lab-jev-chat](https://github.com/Liyucheng1997/332_lab-jev-chat)（MIT）的 fork，
> **仅改动 Windows 桌面版**：上游的 Android 工程、题目集与全部原始代码保持原样。
> 每处改动的依据、证据与实测数据见 **[FORK-NOTES.md](FORK-NOTES.md)**。

---

## 这个 fork 做了什么

| | 问题 | 症状 | 本 fork 的处理 |
|---|---|---|---|
| 🔴 | **高缩放屏上抓错屏幕区域** | 在 150% / 175% 缩放的显示器上点「分析当前微信对话」，读到的不是聊天内容 | ✅ **已修复**：声明进程 DPI 感知，让坐标与截图统一为物理像素；界面尺寸同步按缩放换算 |
| 🟡 | **拿不到 TypeSafe Jev 密钥** | TypeSafe 直连处于 waitlist，没有密钥时一步都走不动 | ➕ **可选**：`JEV_BACKEND=laya` 切换到本地开源判断引擎，无需密钥、正文不出本机（⚠️ 中文准确率不足，默认不启用） |
| 🟡 | **UIA 判据过宽** | 框选过宽时会把微信内部窗口名当作聊天文本 | 📝 已定位并记录，未修（见 [FORK-NOTES](FORK-NOTES.md) 第 2.3 节） |

### 为什么第一个问题必须修

```
进程未声明 DPI 感知时：
  Win32 给出的矩形    逻辑坐标  1042x848  @(1107,130)    ← 程序拿它去裁剪
  ImageGrab 截到的图  物理像素 1824x1484  @(1937,228)    ← 实际截的是这张
  比值 1.750（主屏 3840x2160 @175% 缩放）
```

后果不只是「功能坏了」：**错误的截取区域会把无关的屏幕内容当作聊天，发送给已配置的 TypeSafe / DeepSeek**。
而微信 4.x 不向 UI Automation 暴露聊天文本、OCR 是唯一采集路径，所以在缩放屏上这个缺陷**必然触发**。

### 效果

| | 修复前 | 修复后 |
|---|---|---|
| 框选的聊天区 | ❌ 截到屏幕别处（实测读到浏览器、编辑器的文字） | ✅ 截到的就是聊天区 |
| 界面尺寸（175% 缩放） | — | 窗口 875×1330、`tk scaling` 2.332，比例正常 |
| 上游单元测试 | — | 14 / 14 通过 |

> 📷 **实机截图位**（建议自行补充两张，点进仓库的人最容易被打动）：
> 把图片直接拖进 GitHub 的 README 编辑器即可自动上传并插入链接。建议放「框选聊天区」界面与「判断 + 建议回复」结果面板各一张。

## 快速开始

```powershell
git clone https://github.com/ZJemYoung/jev-chat-windows-laya.git
cd jev-chat-windows-laya
powershell -ExecutionPolicy Bypass -File .\windows\install.ps1   # 建 venv 并安装依赖
powershell -ExecutionPolicy Bypass -File .\windows\start.ps1     # 启动
```

首次使用：打开电脑版微信并进入一个文字聊天 → 点「**框选聊天区**」只框消息气泡 → 点「**分析当前微信对话**」。

> **升级提示**：修复后坐标系由逻辑像素改为物理像素，旧版本里框选过的请**重新框选一次**。
> 另：上游脚本写的是 Python 3.11，本机实测 Python 3.12 也能正常工作。

## 可选：用本地 laya 引擎替代 TypeSafe Jev

```powershell
$env:JEV_BACKEND = 'laya'                # 默认仍是 typesafe，不设即不用
$env:JEV_LAYA_MODEL = 'multilingual'     # multilingual(默认) / typed-decisions / english / router
powershell -ExecutionPolicy Bypass -File .\windows\start.ps1
```

**但请先看实测数据**（5 个手写中文场景，期望标签预先写定）：

| 配置 | 意图命中 | 不同意图数 | 危险度跨度(0-9) |
|---|---|---|---|
| `multilingual` + 本项目 7 题（默认 token 预算） | 2/5 | 2/5 | 0.84 |
| `multilingual` + 提高 token 预算 | 1/5 | 1/5 | 0.17 |
| `multilingual` + laya 自带预设 / 短 schema | tone 2/5 | 2 | — |
| `typed-decisions` + 本项目 7 题 | 2/5 | 3/5 | 1.07（方向相反） |

典型失败：一句明显在生气指责的话，被以 **0.94 的置信度**判为「轻松闲聊」。
结论——**基础 checkpoint 在中文聊天判断上不可用**（与 laya 自述「价值在微调」一致），
因此默认后端仍是 TypeSafe。想用本地引擎，建议按 laya 官方 notebook 在自己的数据上微调后再用。

## 相关分支与文档

- **[fix/dpi-awareness](https://github.com/ZJemYoung/jev-chat-windows-laya/tree/fix/dpi-awareness)** —— 只含 DPI 修复的干净分支（3 个文件 / +124 −8），用于向上游提交 PR
- **[FORK-NOTES.md](FORK-NOTES.md)** —— 改动清单、动机、完整证据、已知限制、归属与 AI 辅助声明
- 上游项目：[Liyucheng1997/332_lab-jev-chat](https://github.com/Liyucheng1997/332_lab-jev-chat)（MIT）
- 本地判断引擎：[NandhaKishorM/laya](https://github.com/NandhaKishorM/laya)（Apache-2.0）

## 边界与免责

本项目读取**你自己设备上、你自己有权查看**的聊天；只提供「复制建议」，**不含任何自动发送路径**，
并在检测到转账 / 红包 / 收款 / 支付等词时拒绝分析。使用第三方 API 时（TypeSafe / DeepSeek），
框选区域内的文字会发往对应服务；改用本地 laya 引擎时正文不出本机。请遵守相关软件的许可协议与当地法律法规。

---

<details>
<summary><b>上游项目 README 原文（未作改动，点击展开）</b></summary>

# Jev 聊天助手 (Jev Chat Assistant)

一个**非侵入式**的实时对话理解与回复辅助层——挂在任意聊天窗口旁边，读懂对方在说什么，用 [TypeSafe **Jev**](https://typesafe.ai/) 判断模型给出「对方真实意图 / 危险等级 / 该不该马上回 / 最佳动作」，再用一个生成式模型起草 3 条候选回复并让 Jev 排序，最后以半透明悬浮窗展示，一键**填入**输入框。

> **目标是全平台。** 微信（Android）只是我们跑通可行性的第一站。核心不依赖任何 App 的接口或账号——它只读「当前屏幕上正在发生的对话」，所以同一套 Jev 判断 + 生成排序内核可以平移到其它 IM、桌面端、乃至任何有聊天的地方——**手机 QQ** 已经这样接进来了，**飞书（Lark）** 采集分发已接入、正文待补。
>
> **发送始终由你手动点。** 程序只读消息、只把回复填进输入框，从不自动发送、不碰转账/红包/收款。

<p align="center"><em>A non-invasive, real-time conversation-understanding layer that sits beside any chat surface. It reads whatever conversation is on screen (no app integration, no account), uses Jev for typed judgments plus a generative model for 3 ranked candidate replies, shows them in a translucent overlay, and fills the input box — you press send. WeChat on Android is just the first platform we proved it on.</em></p>

## 项目目标

- **一层通用的「对话副驾」**：不是再造一个聊天软件，而是浮在你已在用的**任何**聊天之上的分析层。看得懂语义、给得出该怎么回，你保留最终决定权（只填入不发送、不碰转账/红包/收款）。
- **非侵入 = 可跨平台的前提**：不 hook、不改包、不走对方 App 的 API，只从屏幕采集正在显示的对话。换平台换的只是「采集方式」，判断与生成内核不变：
  - **Android 各类 App**：无障碍读屏——微信已跑通；**手机 QQ（`com.tencent.mobileqq`，9.3.50 实测节点开放，正文 `id/mjn`）** 已接入并真机跑通全链路；**飞书（Lark，`com.ss.android.lark`）** 已接入同一套采集分发：会话标题、气泡位置、输入框都能拿到，判断 → 候选 → 填入整条链在飞书里真机跑通。但飞书的消息正文是自绘控件、不在无障碍树里，正文采集要补「截图 + 本地 OCR」（进行中，见已知限制）
  - **桌面端 / 控件树被隐藏的场景**：截图 + OCR/视觉提取文本
  - 采集出的文本 → 同一个 **Jev 判断 + 生成模型起草 + Jev 排序** → 同一套悬浮窗展示
- **已验证**：微信 Android 端（8.0.78 实测）——伪装无障碍服务读到聊天节点、Jev 判断 + DeepSeek 起草 + Jev 排序、悬浮窗填入，闭环打通；手机 QQ（9.3.50 实测）——同一套内核换一个适配器，采集 / 判断 / 候选 / 填入全链路跑通。
- **下一步**：飞书正文走「截图 + OCR」补齐；再扩展到更多 IM / 桌面端 / 网页。

> 说明：微信、QQ、飞书等都是**通用聊天场景**的适配对象；本项目只读你自己设备上、你自己有权查看的聊天，不针对任何单一平台。

## 界面截图

<p align="center">
  <img src="docs/images/overlay.png" width="320" alt="悬浮窗实拍：微信聊天上方的 Jev 分析面板" />
  &nbsp;&nbsp;
  <img src="docs/images/settings.png" width="320" alt="设置页：接口 / 分析 / 外观" />
</p>

- **左：悬浮窗实拍**——挂在微信聊天上方的半透明面板：危险等级（如「危险 1/9 安全」）、对方真实意图与把握度、Jev 排好序的候选回复（每条带占比，可**复制**或**填入**输入框，发送始终你自己点）。
- **右：设置页**——接口（OpenRouter 密钥、回复生成模型）、分析（关系描述、会话白名单、对方发消息时自动分析）、外观（悬浮窗不透明度）。

## 它怎么工作

```
微信 / QQ / 飞书聊天 ──(无障碍读节点)──▶ 采集最近消息
                                  │
              ┌───────────────────┴───────────────────┐
              ▼                                        ▼
   Jev 判断（一次 7 道题）                    生成模型起草 3 条候选
   意图 / 危险 / 需求 / 动作 / 该不该回          │
              └───────────────────┬───────────────────┘
                                  ▼
                        Jev 给 3 条候选排序
                                  ▼
                半透明悬浮窗展示 → 复制 / 填入（不发送）
```

- **采集**：一个 App 一个适配器（`app/src/main/java/com/jev/probe/capture/ChatAppAdapter.kt`），服务按前台包名分发；适配器只负责把当前窗口变成「标题 + 消息列表（谁说的、说了什么）」，下游判断 / 悬浮窗 / 填入全部通用。微信适配器读聊天气泡（`com.tencent.mm:id/bkl`），按气泡位置判断谁说的；QQ 适配器读正文节点（`com.tencent.mobileqq:id/mjn`，QQ 不混淆节点），标题取 `id/371`，按气泡哪边贴着头像列判断谁说的。微信 8.0.52+ 对普通无障碍服务混淆节点，所以服务类名伪装成系统的 `com.google.android.accessibility.selecttospeak.SelectToSpeakService` 才能读到（实测微信 8.0.78 有效）。
- **判断**：[Jev](https://docs.typesafe.ai/)（System One 判断模型）只回答选择/打分/是非，一次请求发全部题目，约 1 秒返回。
- **回复**：生成式模型（默认 DeepSeek）起草 3 条候选，Jev 排序。
- **回填**：`ACTION_SET_TEXT` / 剪贴板 `ACTION_PASTE` 把选中的回复填进输入框，**不发送**。

## 适配一个新的聊天 App

1. 在 `capture/ChatAppAdapter.kt` 里实现 `ChatAppAdapter`：`pkg` 是目标 App 包名，`extract(root, res)` 从当前窗口的无障碍树里取出会话标题和消息列表（`Msg(side, text)`，`side` 是 `me` / `other`），当前窗口不是聊天时返回 `null`。
2. 在 `capture/ChatCaptureService.kt` 的 `adapters` 列表里加一行。
3. 其余不用动：判断、候选、悬浮窗、填入（`findEditable` 找可编辑输入框）都是通用的。

先用 `adb shell uiautomator dump` 看目标 App 暴露了哪些节点：像 QQ 这样节点开放的，照着 id 写就行；像微信这样混淆节点的，要靠伪装服务才看得到；像飞书这样正文自绘的，正文要另走 OCR。

## 下载安装

不想自己编译，直接装仓库里编好的包：[`apk/jev-assistant-v1.1-release.apk`](apk/jev-assistant-v1.1-release.apk)（2026-09-21 构建，release 签名，Android 11+）。

```bash
adb install -r apk/jev-assistant-v1.1-release.apk
```

之前装过 debug 包的要先卸载再装（签名不同，覆盖会失败），卸载会清掉已填的密钥和设置。小米 / HyperOS 重装后悬浮窗权限会被重置，装完按主页向导再开一次。

## Windows 电脑版微信

仓库现已包含独立的 Windows 桌面版，支持 `Weixin.exe` / `WeChat.exe`。它优先读取 Windows UI Automation；电脑版微信不暴露消息控件时，自动改用本地 OCR 识别用户框选的可见聊天区。Windows 版直连 TypeSafe Jev API 做结构化判断；可选配置 DeepSeek API，根据 Jev 判断生成三条建议回复。建议只能复制，不会自动填写或发送。

```powershell
powershell -ExecutionPolicy Bypass -File .\windows\install.ps1
powershell -ExecutionPolicy Bypass -File .\windows\start.ps1
```

构建可分发程序：

```powershell
powershell -ExecutionPolicy Bypass -File .\windows\build.ps1
# 产物：dist\Jev微信助手\Jev微信助手.exe
```

详细配置、隐私边界和使用步骤见 [`windows/README.md`](windows/README.md)。

## 构建

需要 JDK 17 + Android SDK（platform 35 / build-tools 35）。

```bash
# 用 JAVA_HOME 指向 JDK 17，local.properties 里写 sdk.dir
./gradlew assembleDebug
# 产物：app/build/outputs/apk/debug/app-debug.apk

# release 签名包：把密钥库信息写在仓库外的 properties 文件里
# （storeFile / storePassword / keyAlias / keyPassword），路径由 JEV_KEYSTORE_PROPS 指定
./gradlew assembleRelease
# 产物：app/build/outputs/apk/release/app-release.apk
```

## 配置与授权

1. 装 APK（见上面「下载安装」，或自己构建），打开「Jev 聊天助手」。
2. 在**设置**里填你自己的 [OpenRouter](https://openrouter.ai/) API Key（走 `POST /api/alpha/decisions` 调 Jev），选回复生成模型（默认 `deepseek/deepseek-chat-v3.1`；国内 Gemini/OpenAI 会被区域限制）。
3. 按主页向导开三项权限：
   - **无障碍**（读消息）
   - **悬浮窗 / 显示在其他应用上层**（展示分析）
   - **自启动 + 省电无限制**（小米/HyperOS 必做，否则后台进程被冻结、读不到消息）

密钥只存在 App 私有存储，不出设备、不进日志。

## 已知限制

- **国产 ROM 后台冻结**：小米/HyperOS 会激进地杀后台进程，即使配了前台保活、自启动、省电无限制仍可能被杀——被杀后气泡会短暂消失，需在聊天 App 里再交互一下自愈。这是所有「无障碍+悬浮窗」类 App 的公认难题。
- **飞书正文**：飞书 Android 端的消息正文由自绘控件渲染，无障碍树里只有气泡的位置和大小，没有文字（`uiautomator dump` 与伪装服务读到的一致）。目前飞书里能分析到的只有文档卡片等带 TextView 的内容，正文要补「`AccessibilityService.takeScreenshot()` 裁气泡区 + ML Kit 中文识别」。飞书默认左对齐布局下「我 / 对方」也不能按左右判，要另找依据（如已读状态）。
- **群聊**：目前按一对一分析，「对方」与关系设定对群聊不准。
- **中文**：Jev 主训练语言是英文，题目 instructions/criteria 用英文、聊天内容保留中文；上线前建议用自己的真实对话做一批标注校准（见 `tools/jev/`）。
- 伪装无障碍服务是绕过微信节点混淆的手段，微信版本更新可能失效。

## 目录

- `app/` — Android 应用（Kotlin，传统 View，无 Compose）
  - `capture/` 无障碍采集（`ChatAppAdapter.kt` 各 App 适配器、`ChatCaptureService.kt` 分发服务）与前台保活 · `jev/` Jev 客户端与题目集 · `overlay/` 悬浮窗 · `core/` 配置与数据模型
- `tools/jev/` — Jev 题目集与校准脚手架（Python，PC 上跑）
- `docs/` — 设计与验收文档

## 免责声明

仅供个人学习与研究使用。只处理你自己设备上、你自己有权查看的聊天。请遵守微信、QQ、飞书等各软件的许可协议与当地法律法规。作者不对使用后果负责。

## License

[MIT](LICENSE)

## 交流群 / 需求收集

项目刚起步，想听真实需求：你在哪个聊天 App 上最想要这个副驾？希望它判断什么、怎么提示、什么绝对不能碰？扫码进微信群直接说。

**1 群已满，不要再扫。** 2、3、4 群任选一个加入，**请勿重复加入**，内容完全一样。

<table align="center"><tr>
  <td align="center"><img src="docs/images/wechat-group-1.png" width="170" alt="jev-chat-JARVIS 1 群（已满）" /><br/><b>1 群 · 已满</b></td>
  <td align="center"><img src="docs/images/wechat-group-2.png" width="170" alt="jev-chat-JARVIS 2 群" /><br/>2 群</td>
  <td align="center"><img src="docs/images/wechat-group-3.png" width="170" alt="jev-chat-JARVIS 3 群" /><br/>3 群</td>
  <td align="center"><img src="docs/images/wechat-group-4.png" width="170" alt="jev-chat-JARVIS 4 群" /><br/>4 群</td>
</tr></table>

二维码 7 天有效（本批到 2026-09-28），过期了请开一个 [issue](https://github.com/Finderchangchang/jev-chat-JARVIS/issues) 留言，会更新。

</details>

---

<p align="center"><sub>
本仓库为 <a href="https://github.com/Liyucheng1997/332_lab-jev-chat">332_lab-jev-chat</a> 的 fork（MIT）。
上游版权归原作者所有；本 fork 的改动说明见 <a href="FORK-NOTES.md">FORK-NOTES.md</a>。
</sub></p>
