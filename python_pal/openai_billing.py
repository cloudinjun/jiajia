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
    prepaid_balance_snapshot: float | None = None
    prepaid_balance_snapshot_at: str = ""
    cost_since_prepaid_snapshot: float | None = None
    estimated_prepaid_remaining: float | None = None
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
            "openai_billing_prepaid_balance_snapshot": _round_money(self.prepaid_balance_snapshot),
            "openai_billing_prepaid_balance_snapshot_at": self.prepaid_balance_snapshot_at,
            "openai_billing_cost_since_prepaid_snapshot": _round_money(self.cost_since_prepaid_snapshot),
            "openai_billing_estimated_prepaid_remaining": _round_money(self.estimated_prepaid_remaining),
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
        prepaid_snapshot, prepaid_snapshot_at = self._prepaid_snapshot()
        key = os.environ.get("OPENAI_ADMIN_KEY") or os.environ.get("OPENAI_API_KEY")
        source = "organization_costs"
        if not key:
            return _build_status(
                None,
                budget,
                prepaid_snapshot,
                prepaid_snapshot_at,
                None,
                source,
                "key_missing",
                "没有找到 OPENAI_ADMIN_KEY 或 OPENAI_API_KEY。夹夹没有钥匙，就不碰账本。",
            )

        now = datetime.now().astimezone()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        try:
            raw = self._fetch_costs(key, month_start, now + timedelta(days=1))
            total, currency = _sum_costs(raw)
            snapshot_cost = None
            if prepaid_snapshot is not None and prepaid_snapshot_at:
                parsed_snapshot_at = _parse_datetime(prepaid_snapshot_at)
                if parsed_snapshot_at is not None:
                    snapshot_raw = self._fetch_costs(key, parsed_snapshot_at, now + timedelta(days=1))
                    snapshot_cost, snapshot_currency = _sum_costs(snapshot_raw)
                    currency = snapshot_currency or currency
        except urllib.error.HTTPError as exc:
            return self._http_error_status(exc, budget, prepaid_snapshot, prepaid_snapshot_at, source)
        except (OSError, TimeoutError, json.JSONDecodeError) as exc:
            return _build_status(
                None,
                budget,
                prepaid_snapshot,
                prepaid_snapshot_at,
                None,
                source,
                "network_or_parse_error",
                f"OpenAI API 账单读取失败：{type(exc).__name__}。夹夹先不乱算钱。",
            )

        return _build_status(
            total,
            budget,
            prepaid_snapshot,
            prepaid_snapshot_at,
            snapshot_cost,
            source,
            "",
            "",
            currency=currency or "usd",
        )

    def _fetch_costs(self, key: str, start_at: datetime, end_at: datetime) -> dict[str, Any]:
        all_buckets: list[dict[str, Any]] = []
        page = ""
        while True:
            params = {
                "start_time": int(start_at.timestamp()),
                "end_time": int(end_at.timestamp()),
                "limit": 180,
            }
            if page:
                params["page"] = page
            url = f"{OPENAI_COSTS_URL}?{urllib.parse.urlencode(params)}"
            request = urllib.request.Request(
                url,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
            )
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = json.loads(response.read().decode("utf-8"))
            data = raw.get("data") if isinstance(raw, dict) else None
            if isinstance(data, list):
                all_buckets.extend(bucket for bucket in data if isinstance(bucket, dict))
            if not isinstance(raw, dict) or not raw.get("has_more") or not raw.get("next_page"):
                break
            page = str(raw.get("next_page"))
        return {"data": all_buckets}

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

    def _prepaid_snapshot(self) -> tuple[float | None, str]:
        balance = (
            os.environ.get("OPENAI_API_PREPAID_BALANCE_USD")
            or os.environ.get("OPENAI_API_CREDIT_BALANCE_USD")
            or os.environ.get("OPENAI_API_BALANCE_SNAPSHOT_USD")
        )
        snapshot = _money_or_none(balance)
        at = (
            os.environ.get("OPENAI_API_PREPAID_BALANCE_SNAPSHOT_AT")
            or os.environ.get("OPENAI_API_BALANCE_SNAPSHOT_AT")
            or ""
        ).strip()
        if snapshot is not None and at:
            return snapshot, at
        if self.settings_path:
            try:
                raw = json.loads(self.settings_path.read_text(encoding="utf-8-sig"))
            except (OSError, json.JSONDecodeError):
                raw = {}
            if isinstance(raw, dict):
                snapshot = snapshot if snapshot is not None else _money_or_none(
                    raw.get("openai_api_prepaid_balance_usd")
                    or raw.get("openai_api_credit_balance_usd")
                    or raw.get("openai_api_balance_snapshot_usd")
                )
                at = at or _clean_text(
                    raw.get("openai_api_prepaid_balance_snapshot_at")
                    or raw.get("openai_api_balance_snapshot_at"),
                    limit=90,
                )
        return snapshot, at if snapshot is not None else ""

    def _http_error_status(
        self,
        exc: urllib.error.HTTPError,
        budget: float | None,
        prepaid_snapshot: float | None,
        prepaid_snapshot_at: str,
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
        return _build_status(None, budget, prepaid_snapshot, prepaid_snapshot_at, None, source, kind, message)


def _build_status(
    month_cost: float | None,
    monthly_budget: float | None,
    prepaid_snapshot: float | None,
    prepaid_snapshot_at: str,
    cost_since_prepaid_snapshot: float | None,
    source: str,
    error_kind: str,
    error_message: str,
    *,
    currency: str = "usd",
) -> OpenAIBillingStatus:
    remaining = None
    if month_cost is not None and monthly_budget is not None:
        remaining = monthly_budget - month_cost
    estimated_prepaid_remaining = None
    if prepaid_snapshot is not None and cost_since_prepaid_snapshot is not None:
        estimated_prepaid_remaining = prepaid_snapshot - cost_since_prepaid_snapshot
    level = _level_for(month_cost, monthly_budget, remaining, estimated_prepaid_remaining, error_kind)
    summary = _summary_line(
        month_cost,
        monthly_budget,
        remaining,
        prepaid_snapshot,
        prepaid_snapshot_at,
        cost_since_prepaid_snapshot,
        estimated_prepaid_remaining,
        currency,
        level,
        error_kind,
        error_message,
    )
    updated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    return OpenAIBillingStatus(
        month_cost=month_cost,
        monthly_budget=monthly_budget,
        remaining=remaining,
        prepaid_balance_snapshot=prepaid_snapshot,
        prepaid_balance_snapshot_at=prepaid_snapshot_at,
        cost_since_prepaid_snapshot=cost_since_prepaid_snapshot,
        estimated_prepaid_remaining=estimated_prepaid_remaining,
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
    estimated_prepaid_remaining: float | None,
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
    if estimated_prepaid_remaining is not None:
        if estimated_prepaid_remaining <= 0:
            return "over_budget"
        if estimated_prepaid_remaining <= 5:
            return "low"
        return "normal"
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
    prepaid_snapshot: float | None,
    prepaid_snapshot_at: str,
    cost_since_prepaid_snapshot: float | None,
    estimated_prepaid_remaining: float | None,
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
    if prepaid_snapshot is not None:
        snapshot_text = f"{unit}{prepaid_snapshot:.2f}"
        if not prepaid_snapshot_at:
            return f"OpenAI API 本月已花 {cost_text}。有余额快照 {snapshot_text}，但缺少快照时间，夹夹还不能扣账。"
        if cost_since_prepaid_snapshot is None or estimated_prepaid_remaining is None:
            return f"OpenAI API 本月已花 {cost_text}。余额快照是 {snapshot_text}，但快照后的花费还没算出来。"
        spent_text = f"{unit}{cost_since_prepaid_snapshot:.2f}"
        remaining_text = f"{unit}{estimated_prepaid_remaining:.2f}"
        if estimated_prepaid_remaining < 0:
            return f"OpenAI API 本月已花 {cost_text}。按 {prepaid_snapshot_at} 的余额快照 {snapshot_text} 扣，之后花了 {spent_text}，估计已经超出 {unit}{abs(estimated_prepaid_remaining):.2f}。"
        return f"OpenAI API 本月已花 {cost_text}。按 {prepaid_snapshot_at} 的余额快照 {snapshot_text} 扣，之后花了 {spent_text}，估计还剩 {remaining_text}。"
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


def _parse_datetime(value: str) -> datetime | None:
    text = _clean_text(value, limit=90)
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return parsed.astimezone()


def _clean_text(value: Any, limit: int = 80) -> str:
    text = " ".join(str(value or "").strip().split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _round_money(value: float | None) -> float | None:
    return round(value, 2) if value is not None else None
