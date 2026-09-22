# Fork 说明（相对上游的改动）

本项目是 [`Liyucheng1997/332_lab-jev-chat`](https://github.com/Liyucheng1997/332_lab-jev-chat) 的 fork。
上游采用 **MIT 许可**，原始著作权归原作者所有；本 fork 保留其 `LICENSE` 与全部原始代码，
仅在 `windows/`（Windows 桌面版）上做了下列有限改动。**本 fork 不是独立作品，而是派生作品。**

## 1. 改动清单

| 类型 | 文件 | 说明 |
|---|---|---|
| 新增 | `windows/jev_windows/dpi.py` | 进程级 DPI 感知声明（`SetProcessDpiAwarenessContext(-4)` → `shcore.SetProcessDpiAwareness(2)` → `SetProcessDPIAware()` 逐级回退），幂等；另含 `current_awareness()` / `ui_scale()` |
| 新增 | `windows/jev_windows/laya_backend.py` | 本地判断后端：用 [laya](https://github.com/NandhaKishorM/laya)（Apache-2.0，本地非自回归判断引擎）替代 TypeSafe Jev，复用上游同一套题目集与答案映射 |
| 修改 | `windows/run.pyw`（+7 行） | 在 Tk 出现前声明 DPI 感知（该文件同时是源码运行与 PyInstaller 打包的唯一入口） |
| 修改 | `windows/jev_windows/jev_api.py`（+13 行） | 新增 `using_local_backend()`，在 `judge()` 内按 `JEV_BACKEND` 分发；**默认路径（TypeSafe）保持原样** |
| 修改 | `windows/jev_windows/app.py` | 新增 `px()`：坐标变为物理像素后按 `ui_scale()` 换算窗口/换行尺寸，并把 `tk scaling` 固定为真实 DPI；放开"必须有 TypeSafe 密钥"的门禁（仅本地后端时）；界面文案标明当前引擎 |
| 新增 | `windows/laya_smoke.py`、`laya_probe.py`、`laya_short_probe.py` | laya 判断质量的中文评测脚本（含期望标签与区分度统计） |
| 新增 | `windows/real_chat_probe.py`、`dpi_check.py`、`dpi_verify.py` | 抓取可行性与 DPI 诊断/验证脚本 |

未改动上游的 Android 工程、题目集（`tools/jev/`）与任何其他文件。

## 2. 动机

### 2.1 需求：拿不到 TypeSafe 直连密钥

上游 Windows 版把 `https://api.typesafe.ai/v1/systemone` 作为唯一判断来源，而 TypeSafe 直连处于
early access（等待名单，无自助注册），没有密钥时无法进行任何分析。laya 与 Jev 同构
（同样只回答 `choice` / `score` / `noul` 三种原语并返回 `answers`），因此可以用同一套题目集替换判断层：

```powershell
$env:JEV_BACKEND = 'laya'          # 切换到本地引擎（默认仍是 typesafe）
$env:JEV_LAYA_MODEL = 'multilingual'   # 可选：multilingual(默认) / typed-decisions / english / router
$env:JEV_LAYA_DIR = '<预下载目录>'      # 可选：绕过 HF 符号链接缓存限制
```

**但本 fork 不把 laya 设为默认**，原因是实测其**中文判断质量不可用**（见第 3 节）。

### 2.2 缺陷：未声明 DPI 感知导致抓取错位（已修复）

DPI 不感知的进程从 Win32 拿到的是**逻辑坐标**，而 `PIL.ImageGrab` 抓的是**物理像素**。
在缩放屏上（实测机器主屏 3840×2160 @175%，逻辑值 2194×1234）两者相差 1.75 倍，
按逻辑矩形裁剪会落到屏幕的其他位置：

```
（未声明 DPI 感知）  客户区 1042x848 at (1107,130)    <- 逻辑
（声明 DPI 感知后）  客户区 1824x1484 at (1937,228)   <- 物理  1824/1042 = 1.750
```

后果有两条：**功能上**分析的是无关屏幕区域（微信 4.x `Weixin.exe` 不向 UI Automation 暴露聊天文本，
OCR 是唯一路径，因此必然触发）；**隐私上**会把无关屏幕内容当作聊天发送给已配置的第三方 API。

### 2.3 缺陷：UIA 判定过宽会把内部窗口名当聊天文本（未修复，仅记录）

当框选过宽时，`capture._uia_boxes()` 的「去重后 ≥2 个非空 Name 即认为 UIA 可用」会被微信内部子窗口的
控件名满足，从而跳过 OCR 并产出无意义消息：

```
[整个客户区（过宽）] 消息 2 条 | 样本: 'Weixin / MMUIRenderSubWindowHW'
```

建议加入"像聊天文本"的判据（如剔除与已知窗口类/进程名相同的 Name）。本 fork 未改此处。

## 3. laya 中文判断质量实测（据此不设为默认）

5 个手写中文场景，4 种配置：

| 配置 | `true_intent` 命中 | 不同意图数 | `danger` 跨度(0-9) | `should_reply` | 延迟 |
|---|---|---|---|---|---|
| multilingual + 本项目 7 题（默认预算） | 2/5 | 2/5 | 0.84 | 0.66–0.92 | 2.5 s |
| multilingual + 提高 token 预算 | 1/5 | 1/5 | 0.17 | 0.66–0.92 | 3.7 s |
| multilingual + laya 自带预设/短 schema | tone 2/5 | 2 | — | `needs_reply` 恒为 0.02–0.04 | 0.3 s |
| typed-decisions + 本项目 7 题 | 2/5 | 3/5 | 1.07（方向相反） | 0.48–0.54 | 7.0 s |

其中提高预算后输出塌缩为常数，且把明显生气的消息以 **conf 0.94** 判为闲聊。
这与 laya 自述一致：其公开成绩来自**在该评测集训练集上微调过的 checkpoint**，基础 checkpoint 零样本接近随机、
英文之外明显更弱。

## 4. 已知限制

- DPI 修复后，**升级前保存的 `chat_rect` 是逻辑坐标，必须重新框选**。
- 未在副屏、100%/150% 缩放、以及 PyInstaller 打包产物上验证 DPI 修复。
- 未在真实 GUI 流程中完整回归「框选聊天区 → 分析」。
- laya 后端在 CPU 上每次判断约 2.5–3 秒，首次需加载约 1.4 GB 权重。
- `.laya-models/`（预下载的 checkpoint）与 `.venv-windows/` 均已被 `.gitignore` 排除，不进仓库。

## 5. 归属与声明

- 上游项目与原始代码：© 原作者，MIT。
- [laya](https://github.com/NandhaKishorM/laya) 模型与库：Convai Innovations，Apache-2.0。
- 本 fork 新增/修改的代码在用户需求指导下由 AI 编程助手（DeepSeek Harness）生成并实测，
  用户负责决策与验收。**AI 生成代码的著作权归属在多数法域尚无定论**，因此本 fork 不对新增部分主张
  排他性著作权，仅为技术性改动记录。
- 使用本 fork 时请同时遵守上游 `LICENSE`，并在二次分发时保留原始版权声明。
