"""Verify the DPI fix: awareness, coordinate agreement, and the app's own capture path.

Usage (from the repo root, with the project venv):
    .venv-windows\\Scripts\\python.exe windows\\dpi_verify.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "windows"))

from jev_windows.dpi import current_awareness, enable_dpi_awareness, ui_scale  # noqa: E402

print("=== 1. DPI 感知声明 ===")
print(f"  启用前 awareness = {current_awareness()}")
print(f"  enable_dpi_awareness() -> {enable_dpi_awareness()}")
print(f"  启用后 awareness = {current_awareness()}")
print(f"  再次调用（应为 already:*） -> {enable_dpi_awareness()}")
print(f"  ui_scale = {ui_scale():.3f}（1.0=100%，1.75=175%）")

from PIL import ImageGrab  # noqa: E402

from jev_windows.capture import capture_chat  # noqa: E402
from jev_windows.models import Rect  # noqa: E402
from jev_windows.windows_api import client_rect_on_screen, find_wechat_window  # noqa: E402

print("\n=== 2. 坐标系是否一致 ===")
window = find_wechat_window()
client = client_rect_on_screen(window.hwnd)
image = ImageGrab.grab(all_screens=True)
print(f"  微信客户区 {client.width}x{client.height} at ({client.left},{client.top})")
print(f"  ImageGrab 全屏 {image.size}")
in_bounds = client.right <= image.size[0] and client.bottom <= image.size[1]
print(f"  客户区落在抓图范围内：{in_bounds}  <- False 说明两套坐标系仍然错位")

print("\n=== 3. 走 app 自己的抓取函数 ===")
for label, rect in (
    ("整个客户区（过宽）", Rect(0, 0, client.width, client.height)),
    (
        "按气泡区框选",
        Rect(int(client.width * 0.30), int(client.height * 0.08), client.width, int(client.height * 0.82)),
    ),
):
    try:
        snapshot = capture_chat(window, rect)
    except Exception as exc:  # noqa: BLE001
        print(f"  [{label}] 失败: {exc}")
        continue
    sample = snapshot.raw_text[:50].replace("\n", " / ")
    print(f"  [{label}] 消息 {len(snapshot.messages)} 条 | raw_text {len(snapshot.raw_text)} 字 | 样本: {sample!r}")

print("\n=== 4. GUI 在物理像素下的窗口尺寸 ===")
from jev_windows.app import JUDGE_LABEL, JevApp, px  # noqa: E402

print(f"  px(500) x px(760) = {px(500)} x {px(760)}（100% 时即 500x760）")
app = JevApp()
app.withdraw()
app.update()
print(f"  实际窗口: {app.winfo_width()} x {app.winfo_height()}")
print(f"  tk scaling = {app.tk.call('tk', 'scaling')}")
print(f"  JUDGE_LABEL = {JUDGE_LABEL}")
app.destroy()
print("  GUI 构建成功并已销毁")
