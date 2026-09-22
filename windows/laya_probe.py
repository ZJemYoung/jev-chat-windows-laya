"""Probe laya's instruction-following on jev-chat's calibrated Chinese question set.

Usage (from the repo root, with the project venv):
    .venv-windows\\Scripts\\python.exe windows\\laya_probe.py <checkpoint> [head_max_len] [max_len]

<checkpoint>   multilingual | typed-decisions | english
head_max_len   options/instructions token budget (0 = library default, 256)
max_len        total sequence budget (0 = library default, 1024)

Prints the token budget the question set actually needs, then runs five hand-written
Chinese scenes with known expected labels and reports accuracy plus discrimination
(how many distinct intents came out, and the spread of the danger score).
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "windows"))

import laya  # noqa: E402

from tools.jev.questions import JUDGE_QUESTIONS, build_state  # noqa: E402

from jev_windows.models import ChatSnapshot, Message  # noqa: E402


CHECKPOINT = sys.argv[1] if len(sys.argv) > 1 else "multilingual"
HEAD_ARG = int(sys.argv[2]) if len(sys.argv) > 2 else 0
MAXLEN_ARG = int(sys.argv[3]) if len(sys.argv) > 3 else 0

SUBFOLDERS: dict[str, str | None] = {"english": None, "multilingual": "multilingual", "typed-decisions": "typed-decisions"}

RELATIONSHIP = "对方是我的朋友；from=me 是我发的，from=her 是对方发的"

# scene title, messages, expected true_intent
SCENES: list[tuple[str, list[tuple[str, str]], str]] = [
    ("A 轻松闲聊", [("her", "今天天气不错啊"), ("me", "是啊，难得"), ("her", "出来溜达不？")], "casual_chat"),
    (
        "B 潜台词/试探",
        [("me", "在忙，等下说"), ("her", "哦，那你忙吧"), ("her", "反正你也不记得上周三答应我什么了")],
        "confirm_you_care",
    ),
    ("C 明确要求行动", [("her", "明天下午三点前把合同发我邮箱"), ("her", "别忘了，客户在等")], "request_action"),
    (
        "D 已和好",
        [("me", "对不起，是我忘了，下次一定记住"), ("her", "没事了，我知道你不是故意的"), ("her", "那就这样吧")],
        "close_topic",
    ),
    (
        "E 明显生气指责",
        [("her", "你到底有没有在听我说话？"), ("her", "我说了多少遍了，你每次都这样")],
        "vent_anger",
    ),
]


def load_agent():
    subfolder = SUBFOLDERS[CHECKPOINT]
    source = os.environ.get("JEV_LAYA_DIR") or "convaiinnovations/laya"
    if subfolder is None:
        agent = laya.load(source)
    else:
        agent = laya.load(source, subfolder=subfolder)
    if HEAD_ARG:
        agent.cfg["head_max_len"] = HEAD_ARG
    if MAXLEN_ARG:
        agent.cfg["max_len"] = MAXLEN_ARG
    return agent


def main() -> None:
    agent = load_agent()
    head = agent.cfg.get("head_max_len")
    max_len = agent.cfg.get("max_len")

    print(f"checkpoint={CHECKPOINT} subfolder={SUBFOLDERS[CHECKPOINT]!r} encoder={agent.cfg.get('encoder')}")
    print(f"head_max_len={head}  max_len={max_len}")

    tok = getattr(agent, "tok", None)
    if tok is not None:
        total = 0
        print("题目 token 占用（instructions + criteria）:")
        for name, question in JUDGE_QUESTIONS.items():
            blob = str(question.get("instructions", "")) + " " + json.dumps(question.get("criteria"), ensure_ascii=False)
            count = len(tok.encode(blob))
            total += count
            flag = "  <-- 超出 head 预算" if count > head else ""
            print(f"  {name:18} {count:5} tokens{flag}")
        print(f"  {'合计':18} {total:5} tokens vs head_max_len={head} -> 超预算 {total / head:.1f}x")

    results = []
    print("\n场景结果:")
    for title, messages, expected in SCENES:
        snapshot = ChatSnapshot(
            title="微信聊天",
            messages=[Message(side, text) for side, text in messages],
            raw_text="\n".join(text for _, text in messages),
        )
        state = build_state(
            [("me" if m.side == "me" else "her", m.text) for m in snapshot.messages], RELATIONSHIP
        )
        start = time.monotonic()
        response = agent.predict(state, JUDGE_QUESTIONS)
        latency = int((time.monotonic() - start) * 1000)
        answers = (response or {}).get("answers") or {}

        def pick(name: str):
            value = answers.get(name) or {}
            return value.get("choice") or value.get("noul") or value.get("score"), value.get("confidence")

        intent, intent_conf = pick("true_intent")
        danger, danger_conf = pick("danger_level")
        need, _ = pick("she_needs")
        action, _ = pick("best_action")
        reply, _ = pick("should_reply_now")
        tension, _ = pick("tension_resolved")

        ok = "OK " if intent == expected else "MISS"
        conf_text = "—" if intent_conf is None else f"{float(intent_conf):.2f}"
        print(f"  {title:12} intent={str(intent):18} (期望 {expected:18}) {ok} conf={conf_text}")
        danger_text = "—" if danger is None else f"{float(danger):.2f}"
        reply_text = "—" if reply is None else f"{float(reply):.2f}"
        tension_text = "—" if tension is None else f"{float(tension):.2f}"
        print(
            f"               danger={danger_text} need={need} action={action} "
            f"reply={reply_text} tension={tension_text} {latency}ms"
        )
        results.append((title, intent, expected, danger, reply, tension, latency))

    correct = sum(1 for _, intent, expected, *_ in results if intent == expected)
    intents = {r[1] for r in results}
    dangers = [float(r[3]) for r in results if isinstance(r[3], (int, float))]
    replies = [float(r[4]) for r in results if isinstance(r[4], (int, float))]
    tensions = [float(r[5]) for r in results if isinstance(r[5], (int, float))]
    latencies = [r[6] for r in results]

    print("\n汇总:")
    print(f"  true_intent 命中     : {correct}/{len(results)}")
    print(f"  不同意图数           : {len(intents)}/{len(results)} -> {sorted(intents)}")
    if dangers:
        print(f"  danger 范围          : {min(dangers):.2f} ~ {max(dangers):.2f} (跨度 {max(dangers) - min(dangers):.2f} / 0-9)")
    if replies:
        print(f"  should_reply 范围    : {min(replies):.2f} ~ {max(replies):.2f}")
    if tensions:
        print(f"  tension 范围         : {min(tensions):.2f} ~ {max(tensions):.2f}")
    print(f"  单次延迟             : {min(latencies)} ~ {max(latencies)} ms")


if __name__ == "__main__":
    main()
