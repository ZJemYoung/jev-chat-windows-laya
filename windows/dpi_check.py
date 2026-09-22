"""Is this process DPI-unaware while ImageGrab captures physical pixels?

Win32 window/client coordinates come back in *logical* units for a DPI-unaware
process, but ImageGrab reads physical pixels. On a scaled display the two differ by
the scale factor, so a screenshot of "the rect Win32 reported" lands somewhere else
entirely. This prints both coordinate systems so the factor is unambiguous.

Usage:
    .venv-windows\\Scripts\\python.exe windows\\dpi_check.py
"""

from __future__ import annotations

import ctypes
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "windows"))

from PIL import ImageGrab  # noqa: E402
import win32api  # noqa: E402
import win32con  # noqa: E402
import win32gui  # noqa: E402

from jev_windows.windows_api import client_rect_on_screen, find_wechat_window  # noqa: E402


def main() -> None:
    user32 = ctypes.windll.user32
    shcore = getattr(ctypes.windll, "shcore", None)

    print("=== 进程 DPI 感知状态 ===")
    try:
        awareness = shcore.GetProcessDpiAwareness(None, ctypes.byref(ctypes.c_int())) if shcore else None
        value = ctypes.c_int()
        shcore.GetProcessDpiAwareness(None, ctypes.byref(value))
        names = {0: "UNAWARE", 1: "SYSTEM_AWARE", 2: "PER_MONITOR_AWARE"}
        print(f"  GetProcessDpiAwareness = {value.value} ({names.get(value.value, '?')})")
    except Exception as exc:  # noqa: BLE001
        print(f"  读取失败: {exc}")
    try:
        ctx = user32.GetThreadDpiAwarenessContext()
        print(f"  GetThreadDpiAwarenessContext = {ctx}")
    except Exception as exc:  # noqa: BLE001
        print(f"  context 读取失败: {exc}")

    print("=== Win32 报告的尺寸（逻辑单位，取决于感知状态）===")
    print(f"  SM_CXSCREEN x SM_CYSCREEN       = {user32.GetSystemMetrics(0)} x {user32.GetSystemMetrics(1)}")
    print(
        f"  SM_CXVIRTUALSCREEN x CY          = {user32.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN)}"
        f" x {user32.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN)}"
    )

    print("=== 物理分辨率（DC 报告）===")
    hdc = user32.GetDC(0)
    try:
        print(f"  DESKTOPHORZRES x VERTRES         = {win32api.GetDeviceCaps(hdc, 118)} x {win32api.GetDeviceCaps(hdc, 117)}")
        print(f"  HORZRES x VERTRES (逻辑)          = {win32api.GetDeviceCaps(hdc, 8)} x {win32api.GetDeviceCaps(hdc, 10)}")
    finally:
        user32.ReleaseDC(0, hdc)

    print("=== ImageGrab 实际抓到的像素 ===")
    image = ImageGrab.grab(all_screens=True)
    print(f"  all_screens=True                = {image.size}")
    print(f"  primary only                    = {ImageGrab.grab().size}")

    print("=== 微信窗口 ===")
    window = find_wechat_window()
    client = client_rect_on_screen(window.hwnd)
    print(f"  hwnd={window.hwnd} title={window.title!r}")
    print(f"  整窗(逻辑)   = {win32gui.GetWindowRect(window.hwnd)}")
    print(f"  客户区(逻辑) = ({client.left},{client.top})-({client.right},{client.bottom}) {client.width}x{client.height}")
    try:
        dpi = user32.GetDpiForWindow(window.hwnd)
        print(f"  GetDpiForWindow = {dpi}  (96=100%, 192=200%)")
    except Exception as exc:  # noqa: BLE001
        print(f"  GetDpiForWindow 失败: {exc}")

    logical_w = user32.GetSystemMetrics(0)
    physical_w = win32api.GetDeviceCaps(user32.GetDC(0), 118)
    if logical_w and physical_w:
        print(f"\n[结论] 物理/逻辑 宽度比 = {physical_w / logical_w:.3f}")
        print("       比值 > 1 表示本进程按逻辑坐标计算裁剪区，而 ImageGrab 用物理像素 -> 抓取会错位。")


if __name__ == "__main__":
    main()
