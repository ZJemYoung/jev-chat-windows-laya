"""Does laya discriminate on Chinese when the question schema matches its own style?

Two question sets are compared on the same five Chinese scenes:

1. laya's own tuned preset (laya.triage_questions(): is_urgent + frustration),
   which shows the model a short schema it was trained/tuned with;
2. a SHORT schema written in laya's style (short instructions, few options,
   state referenced as `chat`), covering the same decisions jev-chat's UI shows.

If neither discriminates, the problem is laya on Chinese chat, not our question set.

Usage (from the repo root, with the project venv):
    .venv-windows\\Scripts\\python.exe windows\\laya_short_probe.py [checkpoint]
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "windows"))

import laya  # noqa: E402


CHECKPOINT = sys.argv[1] if len(sys.argv) > 1 else "multilingual"
SUBFOLDERS: dict[str, str | None] = {"english": None, "multilingual": "multilingual", "typed-decisions": "typed-decisions"}

SCENES: list[tuple[str, str]] = [
    ("A 轻松闲聊", "对方：今天天气不错啊\n我：是啊，难得\n对方：出来溜达不？"),
    ("B 潜台词/试探", "我：在忙，等下说\n对方：哦，那你忙吧\n对方：反正你也不记得上周三答应我什么了"),
    ("C 明确要求行动", "对方：明天下午三点前把合同发我邮箱\n对方：别忘了，客户在等"),
    ("D 已和好", "我：对不起，是我忘了，下次一定记住\n对方：没事了，我知道你不是故意的\n对方：那就这样吧"),
    ("E 明显生气指责", "对方：你到底有没有在听我说话？\n对方：我说了多少遍了，你每次都这样"),
]

# Written in laya's own style: short instructions, few options, `chat` field reference.
SHORT_QUESTIONS: dict = {
    "tone": {
        "type": "choice",
        "instructions": "What is the other person's tone in the latest message of `chat`?",
        "criteria": {
            "friendly": "casual, warm, no complaint and no ask",
            "testing": "checking whether you remember or care; there is subtext",
            "requesting": "asking for a concrete action, time or deliverable",
            "angry": "blaming, hurt or raising the temperature",
            "closing": "accepted, thanked, or wrapping the topic up peacefully",
        },
    },
    "anger": {
        "type": "score",
        "instructions": "How angry or hurt is the other person in `chat`?",
        "criteria": ["calm", "mildly annoyed", "clearly upset", "very angry"],
    },
    "needs_reply": {
        "type": "noul",
        "instructions": "Does the other person still need a substantive reply in `chat`?",
    },
}


def load_agent():
    subfolder = SUBFOLDERS[CHECKPOINT]
    source = os.environ.get("JEV_LAYA_DIR") or "convaiinnovations/laya"
    if subfolder is None:
        return laya.load(source)
    return laya.load(source, subfolder=subfolder)


def run(agent, label: str, questions: dict) -> None:
    print(f"\n===== {label} (checkpoint={CHECKPOINT}) =====")
    for name, question in questions.items():
        qtype = question.get("type")
        options = question.get("criteria")
        if isinstance(options, dict):
            shown = "/".join(options)
        elif isinstance(options, list):
            shown = f"{len(options)} 级"
        else:
            shown = "yes/no"
        print(f"  题 {name:14} type={qtype:6} 选项={shown}")
    for title, transcript in SCENES:
        state = {"chat": transcript}
        start = time.monotonic()
        response = agent.predict(state, questions)
        latency = int((time.monotonic() - start) * 1000)
        answers = (response or {}).get("answers") or {}
        parts = []
        for name in questions:
            value = answers.get(name) or {}
            picked = value.get("choice") or value.get("noul") or value.get("score")
            conf = value.get("confidence")
            picked_text = f"{float(picked):.2f}" if isinstance(picked, (int, float)) else str(picked)
            conf_text = "—" if conf is None else f"{float(conf):.2f}"
            parts.append(f"{name}={picked_text}(conf {conf_text})")
        print(f"  {title:12} " + "  ".join(parts) + f"  [{latency}ms]")


def main() -> None:
    agent = load_agent()
    print(f"checkpoint={CHECKPOINT} encoder={agent.cfg.get('encoder')} head_max_len={agent.cfg.get('head_max_len')}")
    run(agent, "① laya 自带调优预设 triage_questions()（仅取通用两项）", {"is_urgent": laya.triage_questions()["is_urgent"], "frustration": laya.triage_questions()["frustration"]})
    run(agent, "② 按 laya 风格手写的短 schema", SHORT_QUESTIONS)


if __name__ == "__main__":
    main()
