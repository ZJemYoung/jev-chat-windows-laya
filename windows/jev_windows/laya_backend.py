"""Local, key-free judgment backend for the Windows assistant, powered by laya.

Why this exists
---------------
The TypeSafe/Jev direct API is early-access only (waitlist, no self-serve signup),
so a machine without a TypeSafe key cannot run the judgment step at all. laya is a
non-autoregressive System One decision engine (Apache-2.0) that answers the same
three primitives Jev does — ``choice`` / ``score`` / ``noul`` — so the calibrated
question set in ``tools/jev/questions.py`` and the answer mapping already used by
the TypeSafe path can be reused unchanged.

Properties of this backend
--------------------------
* no API key, no waitlist, no per-request cost;
* nothing is sent over the network at inference time — the chat text stays on this
  machine (model weights are downloaded from Hugging Face once, then cached);
* same ``Analysis`` contract as :func:`jev_windows.jev_api.judge`.

Selection
---------
``JEV_BACKEND=laya``       select this backend (see :func:`jev_windows.jev_api.judge`)
``JEV_LAYA_MODEL=<name>``  checkpoint: ``multilingual`` (default) | ``typed-decisions``
                           | ``english`` | ``router``
``JEV_LAYA_DIR=<path>``    optional pre-downloaded checkpoint tree; see below.

``multilingual`` is the default because this app judges Chinese chat text and the
English checkpoint collapses on non-Latin scripts (the laya README reports 0.000
accuracy at 0.952 confidence on Khmer). ``router`` lets laya pick per request at
the cost of loading more than one checkpoint into memory.

Windows note: Hugging Face's default cache stores blobs as symlinks, which needs
Developer Mode or an elevated shell (``WinError 1314`` otherwise). If the one-shot
download fails, pre-fetch the checkpoint into a plain directory and point
``JEV_LAYA_DIR`` at it::

    python -c "from huggingface_hub import snapshot_download as d; \
        d('convaiinnovations/laya', allow_patterns=[f'multilingual/{n}' for n in \
        ('rl_agent_config.json','model.safetensors','tokenizer/*','encoder/*')], \
        local_dir=r'D:\\models\\laya')"

The directory must then contain the checkpoint as a subfolder named after
``JEV_LAYA_MODEL`` (or the checkpoint files at its root for ``english``).
"""

from __future__ import annotations

import json
import os
import time

from tools.jev.questions import JUDGE_QUESTIONS, build_state

# Reuse the TypeSafe path's answer mapping so both backends cannot drift apart.
from .jev_api import _choice, _number
from .models import Analysis, ChatSnapshot


REPO_ID = "convaiinnovations/laya"
DEFAULT_CHECKPOINT = "multilingual"

# checkpoint name -> subfolder inside the convaiinnovations/laya repo (None = repo root)
_CHECKPOINTS: dict[str, str | None] = {
    "english": None,
    "multilingual": "multilingual",
    "typed-decisions": "typed-decisions",
}


class LayaUnavailableError(RuntimeError):
    """The local judgment engine could not be loaded or returned nothing usable."""


_AGENT = None
_AGENT_NAME: str | None = None


def checkpoint_name() -> str:
    """Checkpoint requested via ``JEV_LAYA_MODEL`` (default ``multilingual``)."""
    return (os.environ.get("JEV_LAYA_MODEL") or DEFAULT_CHECKPOINT).strip().lower()


def model_local_dir() -> str:
    """Pre-downloaded checkpoint tree from ``JEV_LAYA_DIR`` (empty when unset)."""
    return (os.environ.get("JEV_LAYA_DIR") or "").strip()


def _load_agent(name: str):
    try:
        import laya
    except ImportError as exc:  # pragma: no cover - depends on the local venv
        raise LayaUnavailableError(
            "未安装本地判断引擎 laya，请先运行："
            "\\.venv-windows\\Scripts\\python.exe -m pip install laya"
        ) from exc

    if name == "router":
        return laya.Router(preload=True)
    if name not in _CHECKPOINTS:
        raise LayaUnavailableError(
            f"未知的 JEV_LAYA_MODEL={name!r}；可选：router / " + " / ".join(_CHECKPOINTS)
        )

    source = model_local_dir() or REPO_ID
    subfolder = _CHECKPOINTS[name]
    if model_local_dir() and subfolder and not os.path.isdir(os.path.join(source, subfolder)):
        raise LayaUnavailableError(
            f"JEV_LAYA_DIR={source!r} 中没有 {subfolder!r} 子目录（当前 JEV_LAYA_MODEL={name}）。"
            " 请清空 JEV_LAYA_DIR 以改用 Hugging Face 缓存，或先把该 checkpoint 预下载到该目录。"
        )
    if subfolder is None:
        return laya.load(source)
    return laya.load(source, subfolder=subfolder)


def load_agent():
    """Load (and cache) the selected laya checkpoint. Exposed for diagnostics."""
    global _AGENT, _AGENT_NAME
    name = checkpoint_name()
    if _AGENT is None or _AGENT_NAME != name:
        _AGENT = _load_agent(name)
        _AGENT_NAME = name
    return _AGENT


def judge(snapshot: ChatSnapshot, relationship: str) -> Analysis:
    """Judge one chat snapshot locally. Same contract as the TypeSafe path."""
    agent = load_agent()
    messages = [("me" if message.side == "me" else "her", message.text) for message in snapshot.messages]
    state = build_state(messages, relationship)

    start = time.monotonic()
    try:
        response = agent.predict(state, JUDGE_QUESTIONS)
    except TypeError:
        # Some laya builds want the state as a serialized document rather than a dict.
        response = agent.predict(json.dumps(state, ensure_ascii=False), JUDGE_QUESTIONS)
    latency_ms = int((time.monotonic() - start) * 1000)

    answers = (response or {}).get("answers") or {}
    if not answers:
        raise LayaUnavailableError("laya 未返回 answers，无法判断（请检查模型是否正确加载）")

    return Analysis(
        true_intent=_choice(answers, "true_intent"),
        danger_level=_number(answers, "danger_level", "score", "answer"),
        need=_choice(answers, "she_needs"),
        best_action=_choice(answers, "best_action"),
        should_reply_now=_number(answers, "should_reply_now", "noul", "answer"),
        tension_resolved=_number(answers, "tension_resolved", "noul", "answer"),
        latency_ms=latency_ms,
    )
