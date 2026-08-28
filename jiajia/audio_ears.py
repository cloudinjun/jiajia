"""Hearing to match the Ears' sight: how loud is the machine right now.

`Ears` watches the foreground window; nothing listened. This reads exactly one
number — the peak level of the DEFAULT OUTPUT device, via Windows Core Audio's
IAudioMeterInformation — so the pal can tell "music has been on for an hour"
from "the room has been silent all afternoon".

Deliberately low-risk, same contract as Ears: it meters what the machine is
PLAYING (a loudness float, 0..1). It never opens the microphone, never records,
and cannot know what is playing — only that something is, and roughly how loud.

Pure ctypes COM, no dependencies. Anything failing (no audio device, headless
CI, non-Windows) degrades to a silent context and never raises out of sample().
"""
from __future__ import annotations

import ctypes
import time
from ctypes import wintypes
from dataclasses import dataclass, field

# Loudness bands for the peak meter (its scale is linear amplitude 0..1).
AUDIBLE_PEAK = 0.02      # below this the room counts as silent
LOUD_PEAK = 0.45
# A song gap or a paused video should not end a listening session.
SESSION_GRACE_SECONDS = 8.0
LONG_SESSION_SECONDS = 30 * 60
LONG_SILENCE_SECONDS = 45 * 60
# After a COM failure, how long to wait before trying the device again.
REACQUIRE_SECONDS = 30.0


@dataclass
class AudioContext:
    available: bool = False
    playing: bool = False
    peak: float = 0.0
    level: str = "silent"            # silent | quiet | audible | loud
    session_seconds: float = 0.0     # how long audio has been on, gaps bridged
    silence_seconds: float = 0.0     # how long the room has been quiet
    audio_tags: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "audio_available": self.available,
            "audio_playing": self.playing,
            "audio_peak": round(self.peak, 3),
            "audio_level": self.level,
            "audio_session_seconds": round(self.session_seconds, 1),
            "audio_silence_seconds": round(self.silence_seconds, 1),
            "audio_tags": self.audio_tags,
        }


def classify_peak(peak: float) -> str:
    if peak < AUDIBLE_PEAK:
        return "silent"
    if peak < 0.10:
        return "quiet"
    if peak < LOUD_PEAK:
        return "audible"
    return "loud"


def audio_tags(level: str, session_seconds: float, silence_seconds: float) -> list[str]:
    """Machine tags for the decision layer; keys, not user-facing text."""
    tags: list[str] = []
    if level != "silent":
        tags.append("audio_playing")
    if level == "loud":
        tags.append("audio_loud")
    if session_seconds >= LONG_SESSION_SECONDS:
        tags.append("audio_long_session")
    if silence_seconds >= LONG_SILENCE_SECONDS:
        tags.append("audio_quiet_room")
    return tags


# ── Core Audio plumbing (Windows only) ─────────────────────────────


def _guid(text: str) -> ctypes.Array:
    buffer = (ctypes.c_byte * 16)()
    if ctypes.oledll.ole32.CLSIDFromString(text, ctypes.byref(buffer)) != 0:
        raise OSError(f"bad GUID {text}")
    return buffer


def _com_method(pointer: ctypes.c_void_p, index: int, *argtypes: object):
    """Resolve slot `index` of a COM object's vtable as a callable."""
    vtable = ctypes.cast(pointer, ctypes.POINTER(ctypes.c_void_p)).contents
    slots = ctypes.cast(vtable, ctypes.POINTER(ctypes.c_void_p * (index + 1))).contents
    prototype = ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p, *argtypes)
    return prototype(slots[index])


def _release(pointer: ctypes.c_void_p | None) -> None:
    if pointer:
        try:
            _com_method(pointer, 2)(pointer)  # IUnknown::Release
        except OSError:
            pass


class AudioEars:
    """Meter the default output device. All failure modes read as silence."""

    def __init__(self) -> None:
        self._meter: ctypes.c_void_p | None = None
        self._failed_at = 0.0
        # None means "no streak", because 0.0 is a legitimate timestamp — using
        # zero as the sentinel made a session started at t=0 read as no session
        self._session_started_at: float | None = None
        self._last_audible_at: float | None = None
        self._silence_started_at: float | None = time.time()

    # -- device lifecycle -------------------------------------------------

    def _acquire(self) -> bool:
        """Open enumerator → default render endpoint → peak meter."""
        try:
            import sys

            if sys.platform != "win32":
                return False
            ole32 = ctypes.oledll.ole32
            hr = ole32.CoInitializeEx(None, 0x2)  # apartment threaded
            if hr not in (0, 1) and hr != -2147417850:  # S_OK, S_FALSE, RPC_E_CHANGED_MODE
                return False

            clsid_enumerator = _guid("{BCDE0395-E52F-467C-8E3D-C4579291692E}")
            iid_enumerator = _guid("{A95664D2-9614-4F35-A746-DE8DB63617E6}")
            iid_meter = _guid("{C02216F6-8C67-4B5B-9D00-D008E73E0064}")

            enumerator = ctypes.c_void_p()
            ole32.CoCreateInstance(
                ctypes.byref(clsid_enumerator), None, 23,  # CLSCTX_ALL
                ctypes.byref(iid_enumerator), ctypes.byref(enumerator),
            )
            device = ctypes.c_void_p()
            try:
                # IMMDeviceEnumerator::GetDefaultAudioEndpoint (slot 4):
                # eRender=0 (what the machine PLAYS — never the microphone),
                # eConsole=0
                get_default = _com_method(
                    enumerator, 4, ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)
                )
                if get_default(enumerator, 0, 0, ctypes.byref(device)) != 0 or not device:
                    return False
                meter = ctypes.c_void_p()
                # IMMDevice::Activate (slot 3)
                activate = _com_method(
                    device, 3,
                    ctypes.POINTER(ctypes.c_byte * 16), wintypes.DWORD,
                    ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p),
                )
                if activate(device, ctypes.byref(iid_meter), 23, None, ctypes.byref(meter)) != 0:
                    return False
                self._meter = meter
                return True
            finally:
                _release(device if device else None)
                _release(enumerator if enumerator else None)
        except OSError:
            return False

    def _read_peak(self) -> float | None:
        """Current output peak, or None when the device path is unusable."""
        if self._meter is None:
            now = time.time()
            if self._failed_at and now - self._failed_at < REACQUIRE_SECONDS:
                return None
            if not self._acquire():
                self._failed_at = now
                return None
            self._failed_at = 0.0
        try:
            value = ctypes.c_float(0.0)
            get_peak = _com_method(self._meter, 3, ctypes.POINTER(ctypes.c_float))
            if get_peak(self._meter, ctypes.byref(value)) != 0:
                raise OSError("GetPeakValue failed")
            return max(0.0, min(1.0, float(value.value)))
        except OSError:
            # default device changed or endpoint invalidated: drop and retry later
            _release(self._meter)
            self._meter = None
            self._failed_at = time.time()
            return None

    # -- sampling ---------------------------------------------------------

    def sample(self) -> AudioContext:
        return self._fold(self._read_peak(), time.time())

    def _fold(self, peak: float | None, now: float) -> AudioContext:
        """Turn one meter reading into streak-aware context. Pure given inputs."""
        if peak is None:
            # unavailable: report honestly, keep no fictional streaks
            quiet_for = now - self._silence_started_at if self._silence_started_at is not None else 0.0
            return AudioContext(available=False, silence_seconds=max(0.0, quiet_for))

        level = classify_peak(peak)
        audible = level != "silent"
        if audible:
            if self._session_started_at is None:
                self._session_started_at = now
            self._last_audible_at = now
            self._silence_started_at = None
        else:
            # bridge short gaps (between songs, a paused sentence) before
            # declaring the session over
            if (
                self._session_started_at is not None
                and self._last_audible_at is not None
                and now - self._last_audible_at > SESSION_GRACE_SECONDS
            ):
                self._session_started_at = None
            if self._silence_started_at is None:
                self._silence_started_at = now

        in_session = self._session_started_at is not None
        session_seconds = now - self._session_started_at if self._session_started_at is not None else 0.0
        silence_seconds = now - self._silence_started_at if self._silence_started_at is not None else 0.0
        tags = audio_tags(level if in_session or audible else "silent", session_seconds, silence_seconds)
        return AudioContext(
            available=True,
            playing=audible or in_session,
            peak=peak,
            level=level,
            session_seconds=session_seconds,
            silence_seconds=silence_seconds,
            audio_tags=tags,
        )


# ── reacting, not just sensing ─────────────────────────────────────

# Sustains and cooldowns for the announcer. A notification ding must not read
# as "music started", and one remark per event per while is plenty — the pal
# comments on sound, it does not review it continuously.
STARTED_SUSTAIN_SECONDS = 20.0
LOUD_SUSTAIN_SECONDS = 10.0
ENDED_MIN_SESSION_SECONDS = 10 * 60
EVENT_COOLDOWN_SECONDS = {
    "audio_started": 15 * 60,
    "audio_loud": 10 * 60,
    "audio_marathon": 45 * 60,
    "audio_ended": 20 * 60,
}


def audio_flavor(app_category: str) -> str:
    """What the sound probably is, judged from the FOREGROUND app.

    The meter cannot know content, but the Ears already see which app is in
    front: a music player makes "music" a fair guess, a browser suggests a
    video, a game its own noise. Anything else stays "ambient" — the honest
    "could be a song, could be a video, could be the keyboard" register.
    """
    return {
        "music": "music",
        "browser": "video",
        "meeting_or_chat": "call",
        "game": "game",
    }.get(app_category, "ambient")


def announcement_allowed_for(app_category: str) -> bool:
    """During a call or meeting the pal keeps quiet, full stop.

    A bubble popping up mid screen-share is an incident, not a companion.
    """
    return app_category != "meeting_or_chat"


class AudioEventDetector:
    """Turn the loudness stream into at most one event at a time.

    Pure signal logic: sustains, per-session once-flags and cooldowns live
    here; whether the pal may actually speak (activity policy, focus mode,
    meetings) is the app's decision.
    """

    def __init__(self) -> None:
        self._announced_at: dict[str, float] = {}
        self._loud_since: float | None = None
        self._started_for: float | None = None
        self._marathon_for: float | None = None
        self._was_playing = False
        self._last_session_seconds = 0.0
        self.session_flavor = "ambient"

    def _ready(self, event: str, now: float) -> bool:
        last = self._announced_at.get(event)
        return last is None or now - last >= EVENT_COOLDOWN_SECONDS[event]

    @staticmethod
    def _same_session(marker: float | None, remembered: float | None) -> bool:
        """Markers are now-minus-session and jitter by sampling cadence.

        An exact compare made one session yield two different markers a second
        apart, which would have announced the same music twice.
        """
        if marker is None or remembered is None:
            return False
        return abs(marker - remembered) <= SESSION_GRACE_SECONDS + 2

    def observe(self, context: AudioContext, now: float, app_category: str = "unknown") -> str | None:
        if not context.available:
            self._loud_since = None
            return None

        session_marker = (now - context.session_seconds) if context.playing else None
        # a brand-new session: remember what it sounds like it might be
        if (context.playing and not self._same_session(session_marker, self._started_for)
                and not self._was_playing):
            self.session_flavor = audio_flavor(app_category)

        if context.level == "loud":
            self._loud_since = self._loud_since or now
        else:
            self._loud_since = None

        event: str | None = None
        ended_a_real_session = (
            self._was_playing
            and not context.playing
            and self._last_session_seconds >= ENDED_MIN_SESSION_SECONDS
        )
        if ended_a_real_session and self._ready("audio_ended", now):
            event = "audio_ended"
        elif (
            context.playing
            and context.session_seconds >= LONG_SESSION_SECONDS
            and not self._same_session(session_marker, self._marathon_for)
            and self._ready("audio_marathon", now)
        ):
            self._marathon_for = session_marker
            event = "audio_marathon"
        elif (
            self._loud_since is not None
            and now - self._loud_since >= LOUD_SUSTAIN_SECONDS
            and self._ready("audio_loud", now)
        ):
            event = "audio_loud"
        elif (
            context.playing
            and context.session_seconds >= STARTED_SUSTAIN_SECONDS
            and not self._same_session(session_marker, self._started_for)
            and self._ready("audio_started", now)
        ):
            self._started_for = session_marker
            event = "audio_started"

        if event:
            self._announced_at[event] = now
        self._was_playing = context.playing
        if context.playing:
            self._last_session_seconds = context.session_seconds
        return event


# (zh, en) line pools per (event, flavor). "ambient" is the fallback flavor and
# deliberately does not claim to know what the sound is.
AUDIO_LINES: dict[tuple[str, str], tuple[tuple[str, ...], tuple[str, ...]]] = {
    ("audio_started", "music"): (
        ("开始放歌了。工位氛围组上线。", "有音乐。今天的进度条自带配乐。"),
        ("Music's on. The desk has an atmosphere department now.",
         "A soundtrack. Today's progress bar comes scored."),
    ),
    ("audio_started", "video"): (
        ("在放视频？我就当这是文献调研。", "有声音，浏览器在前台。合理怀疑是视频。"),
        ("A video, is it? I shall log this as literature review.",
         "Sound on, browser in front. I have a reasonable suspicion it's a video."),
    ),
    ("audio_started", "game"): (
        ("游戏音效上线。任务们先自己排个队。", "听这动静，是游戏。我就不打扰战局了。"),
        ("Game audio detected. The tasks may form an orderly queue.",
         "That racket is a game. I shan't disturb the campaign."),
    ),
    ("audio_started", "ambient"): (
        ("有声音了。可能是歌，可能是视频，也可能是键盘在渡劫。",
         "环境音上线。我分不清内容，只负责听个响。"),
        ("There's sound. Could be a song, could be a video, could be the keyboard ascending.",
         "Ambient audio online. I can't tell what it is; I only do loudness."),
    ),
    ("audio_loud", "ambient"): (
        ("音量有点大。我一根铁丝都在共振。", "这个响度，邻居都算参会人员了。"),
        ("That's quite loud. Even my wire is resonating.",
         "At this volume the neighbours count as attendees."),
    ),
    ("audio_marathon", "music"): (
        ("这歌单陪你半小时了。谁在陪谁加班？", "音乐连放三十分钟。你们感情很稳定。"),
        ("That playlist has kept you company for half an hour. Who's overtime-ing whom?",
         "Thirty minutes of continuous music. A very stable relationship."),
    ),
    ("audio_marathon", "ambient"): (
        ("声音持续半小时了。背景音也算一种同事。", "半小时了还在响。它比大多数任务都有毅力。"),
        ("Half an hour of sound. Background noise is a colleague of sorts.",
         "Still going after thirty minutes. More persistence than most tasks."),
    ),
    ("audio_ended", "music"): (
        ("音乐停了。世界恢复出厂音效。", "歌单放完了。安静得像周一早上。"),
        ("The music stopped. The world is back on factory sound settings.",
         "Playlist finished. Quiet as a Monday morning."),
    ),
    ("audio_ended", "ambient"): (
        ("声音停了。房间突然很像会议室。", "安静下来了。我能听见自己在思考，字面意义上没有。"),
        ("The sound stopped. The room suddenly resembles a meeting room.",
         "Quiet again. I can hear myself think — literally nothing."),
    ),
}


def audio_line(event: str, flavor: str, language: str = "zh-CN") -> str:
    """Pick a remark for the event, flavored when we have one, honest when not."""
    import random

    pools = AUDIO_LINES.get((event, flavor)) or AUDIO_LINES.get((event, "ambient"))
    if not pools:
        return ""
    zh, en = pools
    lines = en if str(language).startswith("en") else zh
    return random.choice(lines) if lines else ""
