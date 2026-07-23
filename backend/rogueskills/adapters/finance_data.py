from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx

from rogueskills.application.errors import ApplicationError


def _sha256(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def _fetched_at() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class SecFinanceDataGateway:
    """Read-only gateway for SEC EDGAR company facts and Stooq daily prices."""

    TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
    SUBMISSIONS_ROOT = "https://data.sec.gov/submissions"
    FACTS_ROOT = "https://data.sec.gov/api/xbrl/companyfacts"
    ARCHIVES_ROOT = "https://www.sec.gov/Archives/edgar/data"
    STOOQ_URL = "https://stooq.com/q/d/l/"
    YAHOO_CHART_ROOT = "https://query1.finance.yahoo.com/v8/finance/chart"

    def __init__(self, client: httpx.AsyncClient, *, sec_user_agent: str) -> None:
        self.client = client
        self.sec_user_agent = sec_user_agent
        self._ticker_cache: dict[str, dict[str, Any]] | None = None

    async def _get(
        self,
        url: str,
        *,
        params: dict[str, str] | None = None,
        sec: bool = False,
    ) -> httpx.Response:
        headers = {
            "Accept": "application/json,text/csv;q=0.9",
            "User-Agent": self.sec_user_agent if sec else "RogueSkills-Finance/0.3",
        }
        try:
            response = await self.client.get(url, params=params, headers=headers)
            response.raise_for_status()
            return response
        except httpx.ConnectError as error:
            raise ApplicationError(
                "FINANCE_SOURCE_CONNECTION_FAILED",
                f"无法连接数据源：{url}",
                status_code=503,
                retryable=True,
                details={"url": url},
            ) from error
        except httpx.TimeoutException as error:
            raise ApplicationError(
                "FINANCE_SOURCE_TIMEOUT",
                f"数据源请求超时：{url}",
                status_code=504,
                retryable=True,
                details={"url": url},
            ) from error
        except httpx.HTTPStatusError as error:
            raise ApplicationError(
                "FINANCE_SOURCE_UPSTREAM_ERROR",
                f"数据源返回 HTTP {error.response.status_code}。",
                status_code=502,
                retryable=error.response.status_code >= 500 or error.response.status_code == 429,
                details={"url": url, "upstreamStatus": error.response.status_code},
            ) from error

    async def _ticker_map(self) -> dict[str, dict[str, Any]]:
        if self._ticker_cache is not None:
            return self._ticker_cache
        response = await self._get(self.TICKERS_URL, sec=True)
        try:
            payload = response.json()
            self._ticker_cache = {
                str(item["ticker"]).upper(): item for item in payload.values()
            }
        except (ValueError, KeyError, TypeError, AttributeError) as error:
            raise ApplicationError(
                "SEC_TICKER_INDEX_INVALID",
                "SEC ticker 索引结构不可解析。",
                status_code=502,
                retryable=True,
            ) from error
        return self._ticker_cache

    async def fetch_bundle(self, *, ticker: str, as_of_date: date) -> dict[str, Any]:
        ticker = ticker.upper()
        item = (await self._ticker_map()).get(ticker)
        if not item:
            raise ApplicationError(
                "SEC_TICKER_NOT_FOUND",
                f"SEC ticker 索引中找不到 {ticker}。",
                status_code=404,
            )
        cik = int(item["cik_str"])
        cik_padded = f"{cik:010d}"
        submissions_url = f"{self.SUBMISSIONS_ROOT}/CIK{cik_padded}.json"
        facts_url = f"{self.FACTS_ROOT}/CIK{cik_padded}.json"
        submissions_response = await self._get(submissions_url, sec=True)
        facts_response = await self._get(facts_url, sec=True)
        fetched_at = _fetched_at()

        try:
            submissions = submissions_response.json()
            company_facts = facts_response.json()
        except json.JSONDecodeError as error:
            raise ApplicationError(
                "SEC_RESPONSE_INVALID",
                "SEC 返回了不可解析的 JSON。",
                status_code=502,
                retryable=True,
            ) from error

        market: dict[str, Any] | None = None
        market_errors: list[dict[str, Any]] = []
        try:
            market = await self._fetch_stooq(ticker=ticker, as_of_date=as_of_date)
        except ApplicationError as error:
            market_errors.append(
                {"code": error.code, "message": error.message, "retryable": error.retryable}
            )
            try:
                market = await self._fetch_yahoo(ticker=ticker, as_of_date=as_of_date)
            except ApplicationError as fallback_error:
                market_errors.append(
                    {
                        "code": fallback_error.code,
                        "message": fallback_error.message,
                        "retryable": fallback_error.retryable,
                    }
                )

        sources = [
            {
                "id": "sec-submissions",
                "provider": "SEC EDGAR",
                "title": f"{ticker} filing submissions",
                "url": submissions_url,
                "fetchedAt": fetched_at,
                "sha256": _sha256(submissions_response.content),
                "contentType": submissions_response.headers.get(
                    "content-type", "application/json"
                ).split(";", 1)[0],
            },
            {
                "id": "sec-companyfacts",
                "provider": "SEC EDGAR",
                "title": f"{ticker} XBRL company facts",
                "url": facts_url,
                "fetchedAt": fetched_at,
                "sha256": _sha256(facts_response.content),
                "contentType": facts_response.headers.get(
                    "content-type", "application/json"
                ).split(";", 1)[0],
            },
        ]
        if market:
            sources.append(market["source"])
        return {
            "company": {
                "ticker": ticker,
                "name": str(company_facts.get("entityName") or item.get("title") or ticker),
                "cik": cik,
                "sic": submissions.get("sic"),
                "sicDescription": submissions.get("sicDescription"),
                "fiscalYearEnd": submissions.get("fiscalYearEnd"),
            },
            "asOfDate": as_of_date.isoformat(),
            "sources": sources,
            "submissions": submissions,
            "companyFacts": company_facts,
            "market": market["price"] if market else None,
            "warnings": market_errors,
            "rawSnapshots": {
                "sec-submissions": submissions_response.text,
                "sec-companyfacts": facts_response.text,
                **({"market-price": market["raw"]} if market else {}),
            },
        }

    async def _fetch_stooq(self, *, ticker: str, as_of_date: date) -> dict[str, Any]:
        start = as_of_date - timedelta(days=20)
        response = await self._get(
            self.STOOQ_URL,
            params={
                "s": f"{ticker.lower()}.us",
                "d1": start.strftime("%Y%m%d"),
                "d2": as_of_date.strftime("%Y%m%d"),
                "i": "d",
            },
        )
        try:
            rows = list(csv.DictReader(io.StringIO(response.text)))
            valid = [
                row
                for row in rows
                if row.get("Date")
                and row.get("Close")
                and date.fromisoformat(str(row["Date"])) <= as_of_date
            ]
            row = valid[-1]
            close = float(row["Close"])
        except (ValueError, KeyError, IndexError, TypeError) as error:
            raise ApplicationError(
                "MARKET_PRICE_NOT_AVAILABLE",
                f"Stooq 没有返回 {ticker} 在基准日前的有效收盘价。",
                status_code=502,
                retryable=True,
            ) from error
        fetched_at = _fetched_at()
        return {
            "price": {
                "ticker": ticker,
                "date": row["Date"],
                "close": close,
                "currency": "USD",
                "provider": "Stooq",
                "sourceEvidenceId": "market-price",
            },
            "source": {
                "id": "market-price",
                "provider": "Stooq",
                "title": f"{ticker} daily market price",
                "url": str(response.url),
                "fetchedAt": fetched_at,
                "sha256": _sha256(response.content),
                "contentType": response.headers.get("content-type", "text/csv").split(
                    ";", 1
                )[0],
            },
            "raw": response.text,
        }

    async def _fetch_yahoo(self, *, ticker: str, as_of_date: date) -> dict[str, Any]:
        start = as_of_date - timedelta(days=20)
        period1 = int(datetime(start.year, start.month, start.day, tzinfo=UTC).timestamp())
        period2_date = as_of_date + timedelta(days=1)
        period2 = int(
            datetime(
                period2_date.year,
                period2_date.month,
                period2_date.day,
                tzinfo=UTC,
            ).timestamp()
        )
        url = f"{self.YAHOO_CHART_ROOT}/{ticker}"
        response = await self._get(
            url,
            params={
                "period1": str(period1),
                "period2": str(period2),
                "interval": "1d",
                "events": "history",
            },
        )
        try:
            payload = response.json()
            result = payload["chart"]["result"][0]
            timestamps = result["timestamp"]
            closes = result["indicators"]["quote"][0]["close"]
            rows = [
                (datetime.fromtimestamp(int(timestamp), UTC).date(), float(close))
                for timestamp, close in zip(timestamps, closes, strict=True)
                if close is not None
                and datetime.fromtimestamp(int(timestamp), UTC).date() <= as_of_date
            ]
            price_date, close = rows[-1]
            currency = str((result.get("meta") or {}).get("currency") or "USD")
        except (ValueError, KeyError, IndexError, TypeError) as error:
            raise ApplicationError(
                "MARKET_PRICE_FALLBACK_NOT_AVAILABLE",
                f"Yahoo Finance 没有返回 {ticker} 在基准日前的有效收盘价。",
                status_code=502,
                retryable=True,
            ) from error
        fetched_at = _fetched_at()
        return {
            "price": {
                "ticker": ticker,
                "date": price_date.isoformat(),
                "close": close,
                "currency": currency,
                "provider": "Yahoo Finance",
                "sourceEvidenceId": "market-price",
            },
            "source": {
                "id": "market-price",
                "provider": "Yahoo Finance",
                "title": f"{ticker} daily market price",
                "url": str(response.url),
                "fetchedAt": fetched_at,
                "sha256": _sha256(response.content),
                "contentType": response.headers.get(
                    "content-type", "application/json"
                ).split(";", 1)[0],
            },
            "raw": response.text,
        }


def filing_source_url(cik: int, accession: str | None) -> str:
    if not accession:
        return f"https://www.sec.gov/edgar/browse/?CIK={cik}"
    return f"{SecFinanceDataGateway.ARCHIVES_ROOT}/{cik}/{accession.replace('-', '')}/"
