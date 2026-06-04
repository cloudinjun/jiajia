from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
import base64
import json
import re
import time
import urllib.error
import urllib.request

try:
    from PIL import ImageGrab  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    ImageGrab = None


@dataclass
class ScreenContext:
    available: bool = False
    summary: str = ""
    screen_tags: list[str] = field(default_factory=list)
    confidence: float = 0.0
    sampled_at: float = 0.0

    def as_dict(self) -> dict[str, object]:
        return {
            "screen_available": self.available,
            "screen_summary": self.summary,
            "screen_tags": self.screen_tags,
            "screen_confidence": round(self.confidence, 2),
            "screen_sample_age_seconds": round(max(0.0, time.time() - self.sampled_at), 1) if self.sampled_at else None,
        }


class Eyes:
    """Low-frequency local vision.

    Screenshots are kept in memory, downscaled, sent only to local Ollama, and
    never saved to disk. The prompt asks for behavior-level labels, not text
    transcription.
    """

    def __init__(self, model: str = "qwen3-vl:8b", endpoint: str = "http://127.0.0.1:11434") -> None:
        self.model = model
        self.endpoint = endpoint.rstrip("/")
        self._last = ScreenContext(False, "screen vision has not sampled yet")

    def sample(self) -> ScreenContext:
        return self._last

    def refresh(self) -> ScreenContext:
        if ImageGrab is None:
            self._last = ScreenContext(False, "screen vision dependency is unavailable", ["vision_unavailable"])
            return self._last
        try:
            image_b64 = _capture_screen_b64()
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": _vision_prompt(),
                        "images": [image_b64],
                    }
                ],
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 180},
            }
            response = self._post_json("/api/chat", payload, timeout=24)
            content = str(response.get("message", {}).get("content", ""))
            context = _parse_screen_context(content)
            if context.available:
                self._last = context
        except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            if not self._last.available:
                self._last = ScreenContext(False, "screen vision could not reach local model", ["vision_error"])
        return self._last

    def _post_json(self, path: str, payload: dict[str, object], timeout: int) -> dict[str, object]:
        request = urllib.request.Request(
            f"{self.endpoint}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))


def _capture_screen_b64() -> str:
    image = ImageGrab.grab(all_screens=True)
    image.thumbnail((640, 360))
    if image.mode != "RGB":
        image = image.convert("RGB")
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=58, optimize=True)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _vision_prompt() -> str:
    schema = {
        "available": True,
        "summary": "高层行为摘要，不超过25个中文字符",
        "screen_tags": ["browser_research", "blank_document"],
        "confidence": 0.0,
    }
    return (
        "你是桌宠的本地视觉模块，只做高层环境感知。\n"
        "不要转录或复述屏幕上的具体文字、聊天、邮件、密码、代码、文件名或隐私内容。\n"
        "只判断用户大概在做什么，例如写作、编程、浏览资料、反复切窗、看视频、开会、空白文档发呆。\n"
        "可用标签示例: writing, coding, browsing, browser_research, blank_document, todo_visible, reading, video, meeting_or_chat, file_sorting, design_work, terminal_work, privacy_sensitive, unclear。\n"
        f"只输出 JSON: {json.dumps(schema, ensure_ascii=False)}"
    )


def _parse_screen_context(content: str) -> ScreenContext:
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
    match = re.search(r"\{.*\}", content, flags=re.DOTALL)
    if not match:
        return ScreenContext(False, "screen vision returned no JSON", ["vision_parse_error"])
    data = json.loads(match.group(0))
    tags = data.get("screen_tags")
    if not isinstance(tags, list):
        tags = []
    clean_tags = [str(tag).strip().lower().replace("-", "_") for tag in tags if str(tag).strip()]
    summary = " ".join(str(data.get("summary") or "").split())[:80]
    try:
        confidence = float(data.get("confidence") or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    if any(tag in {"privacy_sensitive", "meeting_or_chat"} for tag in clean_tags):
        summary = "privacy-sensitive active window"
    return ScreenContext(
        available=bool(data.get("available", True)),
        summary=summary,
        screen_tags=clean_tags[:8],
        confidence=max(0.0, min(1.0, confidence)),
        sampled_at=time.time(),
    )
