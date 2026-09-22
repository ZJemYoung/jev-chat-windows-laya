"""Probe the live WeChat window for a real-conversation laya test.

DPI note: a DPI-unaware process gets *logical* coordinates from Win32 while
ImageGrab returns *physical* pixels. On a scaled display (this machine: primary
3840x2160 at 175%, reported as 2194x1234) that mismatch makes every crop land in the
wrong place. ``--dpi-aware`` calls SetProcessDpiAwareness(2) before anything touches
the screen so both coordinate systems agree.

Modes (combinable):
  --show-text                  print the captured transcript (default: counts only)
  --dpi-aware                  enable per-monitor DPI awareness before capturing
  --diagnose-cover             report which process owns the top window at sample points
  --raise                      temporarily set the window topmost for the grab
  --wait-foreground=<seconds>  wait until WeChat is foreground, then capture at once

Usage:
    .venv-windows\\Scripts\\python.exe windows\\real_chat_probe.py --dpi-aware --show-text
"""

from __future__ import annotations

import atexit
import sys
import time
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

SHOW_TEXT = "--show-text" in sys.argv
RAISE = "--raise" in sys.argv
DIAGNOSE = "--diagnose-cover" in sys.argv
DPI_AWARE = "--dpi-aware" in sys.argv
WAIT_FG = next((int(a.split("=", 1)[1]) for a in sys.argv if a.startswith("--wait-foreground=")), 0)

# Must happen before any DC/screenshot is created.
if DPI_AWARE:
    import ctypes

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
        print("[DPI] 已启用 PER_MONITOR_AWARE")
    except Exception as exc:  # noqa: BLE001
        print(f"[DPI] 启用失败：{exc}")

sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "windows"))

from jev_windows.capture import _absolute_rect, _boxes_to_messages, _ocr_boxes, _uia_boxes  # noqa: E402
from jev_windows.models import Rect  # noqa: E402
from jev_windows.windows_api import (  # noqa: E402
    WECHAT_EXECUTABLES,
    _process_name,
    client_rect_on_screen,
    find_wechat_window,
)


def brief(text: str, limit: int = 12) -> str:
    text = text.replace("\n", " ")
    return text if SHOW_TEXT else (text[:limit] + "…" if len(text) > limit else text)


def top_root_at(x: int, y: int) -> int:
    import win32gui

    hwnd = win32gui.WindowFromPoint((x, y))
    return (win32gui.GetAncestor(hwnd, 2) or hwnd) if hwnd else 0


def foreground_process() -> tuple[str, str]:
    import win32api
    import win32gui
    import win32process

    fg = win32gui.GetForegroundWindow()
    _, pid = win32process.GetWindowThreadProcessId(fg)
    try:
        handle = win32api.OpenProcess(0x1000, False, pid)
        exe = win32process.GetModuleFileNameEx(handle, 0).rsplit("\\", 1)[-1]
    except Exception:  # noqa: BLE001
        exe = "?"
    return exe, win32gui.GetWindowText(fg)


def diagnose_cover(client: Rect) -> None:
    counter: Counter[str] = Counter()
    for fx in (0.15, 0.35, 0.55, 0.75, 0.95):
        for fy in (0.15, 0.35, 0.55, 0.75, 0.95):
            x = int(client.left + client.width * fx)
            y = int(client.top + client.height * fy)
            root = top_root_at(x, y)
            counter[(_process_name(root) or "?") if root else "?"] += 1
    total = sum(counter.values())
    print(f"[遮挡诊断] 客户区采样 {total} 点，最上层窗口归属：")
    for name, count in counter.most_common():
        mark = "  <-- 微信" if name.lower() in WECHAT_EXECUTABLES else ""
        print(f"    {name:22} {count}/{total}{mark}")


def raise_window(hwnd: int) -> None:
    import win32con
    import win32gui

    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    win32gui.SetWindowPos(
        hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
        win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW,
    )
    atexit.register(restore_window, hwnd)
    time.sleep(0.6)


def restore_window(hwnd: int) -> None:
    try:
        import win32con
        import win32gui

        win32gui.SetWindowPos(
            hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0, win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
        )
    except Exception:  # noqa: BLE001
        pass


def wait_for_wechat_foreground(seconds: int) -> bool:
    deadline = time.monotonic() + seconds
    last = ""
    while time.monotonic() < deadline:
        exe, _ = foreground_process()
        if exe.lower() in WECHAT_EXECUTABLES:
            return True
        if exe != last:
            print(f"[等待] 前台：{exe}，请点一下微信窗口…（剩余 {int(deadline - time.monotonic())}s）")
            last = exe
        time.sleep(0.4)
    return False


def main() -> None:
    from PIL import ImageGrab

    try:
        window = find_wechat_window()
    except Exception as exc:
        print(f"[不可用] 找不到可见的微信窗口：{exc}")
        print("请打开电脑版微信、进入一个真实聊天并保持窗口可见（≥500x400）后重跑。")
        return

    client = client_rect_on_screen(window.hwnd)
    print(f"[窗口] hwnd={window.hwnd} title={brief(window.title, 40)!r} proc={window.process_name}")
    print(f"[客户区] {client.width}x{client.height} at ({client.left},{client.top})")
    print(f"[抓图尺寸] ImageGrab(all_screens=True) = {ImageGrab.grab(all_screens=True).size}")

    exe, title = foreground_process()
    print(f"[前台] {exe} / {brief(title, 50)!r}")

    if DIAGNOSE:
        diagnose_cover(client)
        return

    if WAIT_FG and not wait_for_wechat_foreground(WAIT_FG):
        print(f"[超时] {WAIT_FG}s 内微信未成为前台窗口，放弃本次抓取。")
        return

    if RAISE:
        raise_window(window.hwnd)
        root = top_root_at(client.left + client.width // 2, client.top + client.height // 2)
        print(f"[置顶校验] 客户区中心点最上层窗口：{_process_name(root) or '?'}")

    inner = Rect(
        int(client.width * 0.30), int(client.height * 0.08), client.width, int(client.height * 0.82)
    )
    area = _absolute_rect(window, inner)
    print(f"[候选聊天区] 屏幕坐标 ({area.left},{area.top})-({area.right},{area.bottom})")

    uia = _uia_boxes(window, area)
    print(f"[UI Automation] 文本节点 {len(uia)} 个，去重 {len({b.text for b in uia})} 个")
    boxes = uia
    if not boxes:
        try:
            boxes = _ocr_boxes(area)
            print(f"[OCR 兜底] 识别文本块 {len(boxes)} 个")
        except Exception as exc:  # noqa: BLE001
            print(f"[OCR 失败] {exc}")
            return

    messages = _boxes_to_messages(boxes, area)
    me = sum(1 for m in messages if m.side == "me")
    print(f"[解析结果] 消息 {len(messages)} 条（我 {me} / 对方 {len(messages) - me}）")
    for index, message in enumerate(messages, start=1):
        print(f"    {index}. [{'我' if message.side == 'me' else '对方'}] {brief(message.text, 80)}")
    if not SHOW_TEXT:
        print("\n（未显示正文；加 --show-text 打印真实内容）")


if __name__ == "__main__":
    main()
