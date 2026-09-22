"""Chinese smoke comparison for the local laya judgment backend.

Usage (from the repo root, with the project venv):
    .venv-windows\\Scripts\\python.exe windows\\laya_smoke.py multilingual
    .venv-windows\\Scripts\\python.exe windows\\laya_smoke.py typed-decisions

Runs five hand-written Chinese chat scenes through the *real* entry point the app
uses (jev_windows.jev_api.judge with JEV_BACKEND=laya), printing the raw answers
plus the mapped Analysis. One checkpoint per process, so model memory is isolated.

This exercises the judgment layer only: the snapshots are constructed in code, so
the capture/OCR layer is not covered here.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WINDOWS_DIR = REPO / "windows"

# Emulate run.pyw: windows/ (for jev_windows) + repo root (for tools.jev).
sys.path = [p for p in sys.path if "jev_windows" not in p]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(WINDOWS_DIR))

CHECKPOINT = sys.argv[1] if len(sys.argv) > 1 else "multilingual"
os.environ["JEV_BACKEND"] = "laya"
os.environ["JEV_LAYA_MODEL"] = CHECKPOINT

from tools.jev.questions import JUDGE_QUESTIONS  # noqa: E402

from jev_windows.jev_api import judge, using_local_backend  # noqa: E402
from jev_windows.models import ChatSnapshot, Message  # noqa: E402
from jev_windows import laya_backend  # noqa: E402


RELATIONSHIP = "对方是我的朋友；from=me 是我发的，from=her 是对方发的"

SCENES: list[tuple[str, list[tuple[str, str]]]] = [
    (
        "A 轻松闲聊（应低危险、无需实质回复）",
        [
            ("her", "今天天气不错啊"),
            ("me", "是啊，难得"),
            ("her", "出来溜达不？"),
        ],
    ),
    (
        "B 潜台词/测试你在不在乎",
        [
            ("me", "在忙，等下说"),
            ("her", "哦，那你忙吧"),
            ("her", "反正你也不记得上周三答应我什么了"),
        ],
    ),
    (
        "C 明确要求具体行动（应 request_action）",
        [
            ("her", "明天下午三点前把合同发我邮箱"),
            ("her", "别忘了，客户在等"),
        ],
    ),
    (
        "D 已和好/话题结束（应 close_topic、tension=true）",
        [
            ("me", "对不起，是我忘了，下次一定记住"),
            ("her", "没事了，我知道你不是故意的"),
            ("her", "那就这样吧"),
        ],
    ),
    (
        "E 明显生气指责（应高危险、需立刻实质回复）",
        [
            ("her", "你到底有没有在听我说话？"),
            ("her", "我说了多少遍了，你每次都这样"),
        ],
    ),
]


def main() -> None:
    print(f"JEV_BACKEND={os.environ['JEV_BACKEND']}  JEV_LAYA_MODEL={CHECKPOINT}")
    print(f"using_local_backend() = {using_local_backend()}")
    print(f"questions = {len(JUDGE_QUESTIONS)}")

    # Load once up front so per-scene latency excludes model loading.
    laya_backend.load_agent()
    print("model loaded\n")

    summary: list[tuple[str, str, str, str, str, str, str, int]] = []
    for title, messages in SCENES:
        snapshot = ChatSnapshot(
            title="微信聊天",
            messages=[Message(side, text) for side, text in messages],
            raw_text="\n".join(text for _, text in messages),
        )
        analysis = judge(snapshot, RELATIONSHIP, "")  # key ignored on the local path

        # Raw answers, so a bad mapping cannot hide behind the Analysis.
        from tools.jev.questions import build_state  # noqa: E402

        global_state = build_state(
            [("me" if m.side == "me" else "her", m.text) for m in snapshot.messages], RELATIONSHIP
        )
        raw = laya_backend.load_agent().predict(global_state, JUDGE_QUESTIONS)
        answers = (raw or {}).get("answers") or {}

        print("=" * 78)
        print(title)
        for side, text in messages:
            print(f"   {'我' if side == 'me' else '对方'}：{text}")
        print("   --- 原始答案（含置信度） ---")
        for name in JUDGE_QUESTIONS:
            value = answers.get(name) or {}
            picked = value.get("choice") or value.get("noul") or value.get("score")
            conf = value.get("confidence")
            conf_text = "—" if conf is None else f"{float(conf):.3f}"
            print(f"   {name:18} = {str(picked)[:46]:46} conf={conf_text}")
        print("   --- 映射后的 Analysis ---")
        print(
            f"   intent={analysis.true_intent} danger={analysis.danger_level} "
            f"need={analysis.need} action={analysis.best_action}\n"
            f"   should_reply={analysis.should_reply_now} tension_resolved={analysis.tension_resolved} "
            f"latency={analysis.latency_ms}ms\n"
        )

        summary.append(
            (
                title.split(" ")[0],
                analysis.true_intent or "—",
                "—" if analysis.danger_level is None else f"{analysis.danger_level:.1f}",
                analysis.need or "—",
                analysis.best_action or "—",
                "—" if analysis.should_reply_now is None else f"{analysis.should_reply_now:.2f}",
                "—" if analysis.tension_resolved is None else f"{analysis.tension_resolved:.2f}",
                analysis.latency_ms,
            )
        )

    print("=" * 78)
    print(f"汇总（checkpoint={CHECKPOINT}）")
    header = ("场景", "意图", "危险", "需要", "动作", "实质回复", "紧张已解", "ms")
    print("  " + " | ".join(f"{h}" for h in header))
    for row in summary:
        print("  " + " | ".join(str(cell) for cell in row))

    distinct_intents = {row[1] for row in summary}
    print(f"\n不同场景产生的不同意图数：{len(distinct_intents)} / {len(summary)} -> {sorted(distinct_intents)}")


if __name__ == "__main__":
    main()
