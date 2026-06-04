from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import shutil
import subprocess
import time

try:
    import psutil  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    psutil = None


HEAT_LEVELS = {"warm", "hot", "overloaded"}
LEVEL_RANK = {
    "unavailable": -1,
    "normal": 0,
    "cooling": 0,
    "warm": 1,
    "hot": 2,
    "overloaded": 3,
}


@dataclass(frozen=True)
class HardwareSnapshot:
    cpu_percent: float | None = None
    cpu_temp_c: float | None = None
    ram_percent: float | None = None
    disk_percent: float | None = None
    gpu_percent: float | None = None
    gpu_temp_c: float | None = None
    vram_used_mb: int | None = None
    vram_total_mb: int | None = None
    vram_percent: float | None = None
    level: str = "unavailable"
    previous_level: str = ""
    event_id: str = ""
    summary_line: str = ""
    sampled_at: float = 0.0
    tags: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, object]:
        return {
            "hardware_cpu_percent": _round_or_none(self.cpu_percent),
            "hardware_cpu_temp_c": _round_or_none(self.cpu_temp_c),
            "hardware_ram_percent": _round_or_none(self.ram_percent),
            "hardware_disk_percent": _round_or_none(self.disk_percent),
            "hardware_gpu_percent": _round_or_none(self.gpu_percent),
            "hardware_gpu_temp_c": _round_or_none(self.gpu_temp_c),
            "hardware_vram_used_mb": self.vram_used_mb,
            "hardware_vram_total_mb": self.vram_total_mb,
            "hardware_vram_percent": _round_or_none(self.vram_percent),
            "hardware_level": self.level,
            "hardware_summary": self.summary_line,
            "hardware_tags": list(self.tags),
        }


class HardwareStatusMonitor:
    """Low-privacy hardware signals: utilization only, no screen text or input content."""

    def __init__(self, sample_window: int = 6) -> None:
        self._raw_levels: deque[str] = deque(maxlen=max(3, sample_window))
        self._last_level = "unavailable"
        self._event_counter = 0
        self._nvidia_smi = shutil.which("nvidia-smi")

    def sample(self) -> HardwareSnapshot:
        base = _read_cpu_ram_disk()
        gpu = _read_nvidia_gpu(self._nvidia_smi)
        raw = HardwareSnapshot(**base, **gpu, sampled_at=time.time())
        raw_level = _raw_level(raw)
        level = self._stable_level(raw_level)
        previous = self._last_level
        if previous in HEAT_LEVELS and raw_level == "normal" and level == "normal":
            level = "cooling"

        event_id = ""
        if level != previous:
            self._event_counter += 1
            event_id = f"hardware:{level}:{self._event_counter}"
            self._last_level = level

        return HardwareSnapshot(
            cpu_percent=raw.cpu_percent,
            cpu_temp_c=raw.cpu_temp_c,
            ram_percent=raw.ram_percent,
            disk_percent=raw.disk_percent,
            gpu_percent=raw.gpu_percent,
            gpu_temp_c=raw.gpu_temp_c,
            vram_used_mb=raw.vram_used_mb,
            vram_total_mb=raw.vram_total_mb,
            vram_percent=raw.vram_percent,
            level=level,
            previous_level=previous,
            event_id=event_id,
            summary_line=_summary_line(raw, level),
            sampled_at=raw.sampled_at,
            tags=_hardware_tags(raw, level),
        )

    def _stable_level(self, raw_level: str) -> str:
        if raw_level == "unavailable":
            return "unavailable"

        self._raw_levels.append(raw_level)
        samples = tuple(self._raw_levels)
        overloaded_count = sum(level == "overloaded" for level in samples)
        hot_count = sum(LEVEL_RANK[level] >= LEVEL_RANK["hot"] for level in samples)
        warm_count = sum(LEVEL_RANK[level] >= LEVEL_RANK["warm"] for level in samples)
        if overloaded_count >= 4:
            return "overloaded"
        if hot_count >= 3:
            return "hot"
        if warm_count >= 2:
            return "warm"
        return "normal"


def _read_cpu_ram_disk() -> dict[str, float | None]:
    if psutil is None:
        return {
            "cpu_percent": None,
            "cpu_temp_c": None,
            "ram_percent": None,
            "disk_percent": None,
        }
    cpu_temp = _read_cpu_temp()
    try:
        cpu_percent = float(psutil.cpu_percent(interval=None))
    except Exception:
        cpu_percent = None
    try:
        ram_percent = float(psutil.virtual_memory().percent)
    except Exception:
        ram_percent = None
    try:
        disk_percent = float(psutil.disk_usage("C:\\").percent)
    except Exception:
        disk_percent = None
    return {
        "cpu_percent": cpu_percent,
        "cpu_temp_c": cpu_temp,
        "ram_percent": ram_percent,
        "disk_percent": disk_percent,
    }


def _read_cpu_temp() -> float | None:
    if psutil is None or not hasattr(psutil, "sensors_temperatures"):
        return None
    try:
        sensors = psutil.sensors_temperatures(fahrenheit=False)
    except Exception:
        return None
    temps: list[float] = []
    for entries in sensors.values():
        for entry in entries:
            current = getattr(entry, "current", None)
            if current is not None:
                temps.append(float(current))
    return max(temps) if temps else None


def _read_nvidia_gpu(path: str | None) -> dict[str, float | int | None]:
    empty: dict[str, float | int | None] = {
        "gpu_percent": None,
        "gpu_temp_c": None,
        "vram_used_mb": None,
        "vram_total_mb": None,
        "vram_percent": None,
    }
    if not path:
        return empty
    cmd = [
        path,
        "--query-gpu=utilization.gpu,temperature.gpu,memory.used,memory.total",
        "--format=csv,noheader,nounits",
    ]
    try:
        output = subprocess.check_output(
            cmd,
            text=True,
            timeout=2,
            stderr=subprocess.DEVNULL,
            creationflags=_subprocess_creationflags(),
        )
    except Exception:
        return empty

    readings: list[dict[str, float | int | None]] = []
    for line in output.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 4:
            continue
        util = _float_or_none(parts[0])
        temp = _float_or_none(parts[1])
        used = _int_or_none(parts[2])
        total = _int_or_none(parts[3])
        vram_percent = round(used / total * 100, 1) if used is not None and total else None
        readings.append(
            {
                "gpu_percent": util,
                "gpu_temp_c": temp,
                "vram_used_mb": used,
                "vram_total_mb": total,
                "vram_percent": vram_percent,
            }
        )
    if not readings:
        return empty
    return max(readings, key=lambda item: _gpu_severity(item))


def _gpu_severity(reading: dict[str, float | int | None]) -> float:
    util = _metric(reading.get("gpu_percent"))
    temp = _metric(reading.get("gpu_temp_c"))
    vram = _metric(reading.get("vram_percent"))
    return max(util, temp * 1.2, vram)


def _raw_level(snapshot: HardwareSnapshot) -> str:
    if not any(
        value is not None
        for value in (
            snapshot.cpu_percent,
            snapshot.cpu_temp_c,
            snapshot.ram_percent,
            snapshot.gpu_percent,
            snapshot.gpu_temp_c,
            snapshot.vram_percent,
        )
    ):
        return "unavailable"

    cpu = snapshot.cpu_percent or 0.0
    cpu_temp = snapshot.cpu_temp_c or 0.0
    ram = snapshot.ram_percent or 0.0
    gpu = snapshot.gpu_percent or 0.0
    gpu_temp = snapshot.gpu_temp_c or 0.0
    vram = snapshot.vram_percent or 0.0

    if (gpu >= 95 and (vram >= 85 or gpu_temp >= 78)) or vram >= 95 or ram >= 94:
        return "overloaded"
    if gpu_temp >= 80 or cpu_temp >= 86 or gpu >= 95 or cpu >= 92 or ram >= 90:
        return "hot"
    if gpu_temp >= 70 or cpu_temp >= 78 or gpu >= 80 or cpu >= 85 or ram >= 85:
        return "warm"
    return "normal"


def _hardware_tags(snapshot: HardwareSnapshot, level: str) -> tuple[str, ...]:
    tags = {f"hardware_{level}"}
    if level in {"hot", "overloaded"}:
        tags.add("system_hot")
    if level == "overloaded":
        tags.update({"critical", "overheated"})
    if level == "cooling":
        tags.update({"recovery", "cooldown_recover"})
    if (snapshot.gpu_percent or 0) >= 80:
        tags.add("gpu_usage_high")
    if (snapshot.gpu_temp_c or 0) >= 70:
        tags.add("gpu_temp_high")
    if (snapshot.gpu_temp_c or 0) >= 82:
        tags.add("gpu_temp_critical")
    if (snapshot.cpu_percent or 0) >= 85:
        tags.add("cpu_usage_high")
    if (snapshot.cpu_temp_c or 0) >= 78:
        tags.add("cpu_temp_high")
    if (snapshot.ram_percent or 0) >= 85:
        tags.add("ram_high")
    if (snapshot.vram_percent or 0) >= 85:
        tags.add("vram_high")
    return tuple(sorted(tags))


def _summary_line(snapshot: HardwareSnapshot, level: str) -> str:
    if level == "unavailable":
        return "没有读到硬件传感器。夹夹先假装电脑很冷静。"
    parts = []
    if snapshot.cpu_percent is not None:
        parts.append(f"CPU {snapshot.cpu_percent:.0f}%")
    if snapshot.ram_percent is not None:
        parts.append(f"RAM {snapshot.ram_percent:.0f}%")
    if snapshot.gpu_percent is not None:
        gpu_part = f"GPU {snapshot.gpu_percent:.0f}%"
        if snapshot.gpu_temp_c is not None:
            gpu_part += f" / {snapshot.gpu_temp_c:.0f}C"
        parts.append(gpu_part)
    if snapshot.vram_percent is not None:
        parts.append(f"VRAM {snapshot.vram_percent:.0f}%")
    if not parts:
        return "硬件状态很安静。安静到有点像在装没事。"
    return " / ".join(parts)


def _subprocess_creationflags() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _float_or_none(value: object) -> float | None:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _int_or_none(value: object) -> int | None:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def _metric(value: object) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0


def _round_or_none(value: float | None) -> float | None:
    return round(value, 1) if value is not None else None
