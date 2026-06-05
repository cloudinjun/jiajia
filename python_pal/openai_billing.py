from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import time
from typing import Any
import urllib.error
import urllib.parse
import urllib.request


OPENAI_COSTS_URL = "https://api.openai.com/v1/organization/costs"


@dataclass(frozen=True)
class OpenAIBillingStatus:
    month_cost: float | None = None
    monthly_budget: float | None = None
    remaining: float | None = None
    currency: str = "usd"
    source: str = ""
    updated_at: str = ""
    level: str = "unavailable"
    error_kind: str = ""
    error_message: str = ""
    summary_line: str = "还没有 OpenAI API 账单数据。"
    event_id: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, object]:
        return {
            "openai_billing_month_cost": _round_money(self.month_cost),
            "openai_billing_monthly_budget": _round_money(self.monthly_budget),
            "openai_billing_remaining": _round_money(self.remaining),
            "openai_billing_currency": self.currency,
            "openai_billing_source": self.source,
            "openai_billing_updated_at": self.updated_at,
            "openai_billing_level": self.level,
            "openai_billing_error_kind": self.error_kind,
            "openai_billing_summary": self.summary_line,
            "openai_billing_tags": list(self.tags),
        }


class OpenAIBillingMonitor:
    def __init__(self, settings_path: Path | None = None, timeout_seconds: int = 18) -> None:
        self.settings_path = settings_path
        self.timeout_seconds = timeout_seconds

    def sample(self) -> OpenAIBillingStatus:
        budget = self._monthly_budget()
        key = os.environ.get("OPENAI_ADMIN_KEY") or os.environ.get("OPENAI_API_KEY")
        source = "organization_costs"
        if not key:
            return _build_status(
                None,
                budget,
                source,
                "key_missing",
                "没有找到 OPENAI_ADMIN_KEY 或 OPENAI_API_KEY。夹夹没有钥匙，就不碰账本。",
            )

        now = datetime.now().astimezone()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        params = urllib.parse.urlencode(
            {
                "start_time": int(month_start.timestamp()),
                "end_time": int((now + timedelta(days=1)).timestamp()),
                "limit": 31,
            }
        )
        request = urllib.request.Request(
            f"{OPENAI_COSTS_URL}?{params}",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return self._http_error_status(exc, budget, source)
        except (OSError, TimeoutError, json.JSONDecodeError) as exc:
            return _build_status(
                None,
                budget,
                source,
                "network_or_parse_error",
                f"OpenAI API 账单读取失败：{type(exc).__name__}。夹夹先不乱算钱。",
            )

        total, currency = _sum_costs(raw)
        return _build_status(total, budget, source, "", "", currency=currency or "usd")

    def _monthly_budget(self) -> float | None:
        env_value = os.environ.get("OPENAI_API_MONTHLY_BUDGET_USD") or os.environ.get("OPENAI_API_MONTHLY_LIMIT_USD")
        parsed = _money_or_none(env_value)
        if parsed is not None:
            return parsed
        if not self.settings_path:
            return None
        try:
            raw = json.loads(self.settings_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(raw, dict):
            return None
        for key in ("openai_api_monthly_budget_usd", "openai_api_monthly_limit_usd"):
            parsed = _money_or_none(raw.get(key))
            if parsed is not None:
                return parsed
        return None

    def _http_error_status(
        self,
        exc: urllib.error.HTTPError,
        budget: float | None,
        source: str,
    ) -> OpenAIBillingStatus:
        body = exc.read().decode("utf-8", errors="replace")
        message = body[:260]
        kind = f"http_{exc.code}"
        try:
            error = json.loads(body).get("error") or {}
            if isinstance(error, str):
                message = error
                if "api.usage.read" in message or "insufficient permissions" in message.lower():
                    kind = "missing_usage_scope"
            elif isinstance(error, dict):
                message = str(error.get("message") or message)
                code = str(error.get("code") or "")
                error_type = str(error.get("type") or "")
                if "api.usage.read" in message or "insufficient permissions" in message.lower():
                    kind = "missing_usage_scope"
                elif code or error_type:
                    kind = code or error_type
        except (json.JSONDecodeError, AttributeError):
            pass
        return _build_status(None, budget, source, kind, message)


def _build_status(
    month_cost: float | None,
    monthly_budget: float | None,
    source: str,
    error_kind: str,
    error_message: str,
    *,
    currency: str = "usd",
) -> OpenAIBillingStatus:
    remaining = None
    if month_cost is not None and monthly_budget is not None:
        remaining = monthly_budget - month_cost
    level = _level_for(month_cost, monthly_budget, remaining, error_kind)
    summary = _summary_line(month_cost, monthly_budget, remaining, currency, level, error_kind, error_message)
    updated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    return OpenAIBillingStatus(
        month_cost=month_cost,
        monthly_budget=monthly_budget,
        remaining=remaining,
        currency=currency,
        source=source,
        updated_at=updated_at,
        level=level,
        error_kind=error_kind,
        error_message=error_message,
        summary_line=summary,
        event_id=f"openai_billing|{level}|{month_cost}|{monthly_budget}|{error_kind}|{int(time.time() // 900)}",
        tags=_tags_for(level),
    )


def _sum_costs(raw: dict[str, Any]) -> tuple[float, str]:
    total = 0.0
    currencies: set[str] = set()
    data = raw.get("data") if isinstance(raw, dict) else None
    if not isinstance(data, list):
        return 0.0, "usd"
    for bucket in data:
        if not isinstance(bucket, dict):
            continue
        results = bucket.get("results")
        if not isinstance(results, list):
            continue
        for result in results:
            if not isinstance(result, dict):
                continue
            amount = result.get("amount")
            if not isinstance(amount, dict):
                continue
            value = _money_or_none(amount.get("value"))
            if value is not None:
                total += value
            currency = str(amount.get("currency") or "").lower()
            if currency:
                currencies.add(currency)
    currency = sorted(currencies)[0] if currencies else "usd"
    return total, currency


def _level_for(
    month_cost: float | None,
    monthly_budget: float | None,
    remaining: float | None,
    error_kind: str,
) -> str:
    if error_kind:
        if error_kind == "missing_usage_scope":
            return "permission_missing"
        if error_kind == "key_missing":
            return "key_missing"
        return "unavailable"
    if month_cost is None:
        return "unavailable"
    if monthly_budget is None:
        return "costs_only"
    if remaining is not None and remaining <= 0:
        return "over_budget"
    if remaining is not None and remaining <= 5:
        return "low"
    if monthly_budget > 0 and month_cost / monthly_budget >= 0.8:
        return "watch"
    return "normal"


def _tags_for(level: str) -> tuple[str, ...]:
    tags = {f"openai_billing_{level}"}
    if level in {"low", "over_budget"}:
        tags.update({"usage_low", "critical" if level == "over_budget" else "usage_watch"})
    if level == "watch":
        tags.add("usage_watch")
    return tuple(sorted(tags))


def _summary_line(
    month_cost: float | None,
    monthly_budget: float | None,
    remaining: float | None,
    currency: str,
    level: str,
    error_kind: str,
    error_message: str,
) -> str:
    unit = "$" if currency.lower() == "usd" else f"{currency.upper()} "
    if error_kind == "missing_usage_scope":
        return "OpenAI API 账单读不到：当前 key 缺少 api.usage.read 权限。这个账很重要，夹夹不拿没权限的钥匙硬撬。"
    if error_kind == "key_missing":
        return "还没有 OpenAI billing key。需要 OPENAI_ADMIN_KEY，或带 api.usage.read 权限的 key。"
    if error_kind:
        return f"OpenAI API 账单读取失败：{error_message or error_kind}"
    if month_cost is None:
        return "OpenAI API 账单暂时没有数据。"
    cost_text = f"{unit}{month_cost:.2f}"
    if monthly_budget is None:
        return f"OpenAI API 本月已花 {cost_text}。还没有设置月预算，所以夹夹只能报花费，不能假装知道余额。"
    budget_text = f"{unit}{monthly_budget:.2f}"
    remaining_text = f"{unit}{(remaining or 0):.2f}"
    if level == "over_budget":
        return f"OpenAI API 本月已花 {cost_text}，预算 {budget_text}，已经超了 {unit}{abs(remaining or 0):.2f}。这不是小数点，是账本在皱眉。"
    return f"OpenAI API 本月已花 {cost_text}，预算 {budget_text}，还剩 {remaining_text}。"


def _money_or_none(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed < 0:
        return None
    return parsed


def _round_money(value: float | None) -> float | None:
    return round(value, 2) if value is not None else None
