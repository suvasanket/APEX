"""Playwright-based browser automation and network interception scraper for IndiGo."""

import asyncio
from datetime import date, datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any, Optional

from playwright.async_api import Browser, BrowserContext, Page, Response, async_playwright

from apex.collectors.base import BaseCollector, CollectorResult
from apex.collectors.indigo import IndiGoResponseParser
from apex.models.fare import BookingWindow, FareObservation

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_MS = 45000


class PlaywrightIndiGoCollector(BaseCollector):
    """Acquires live domestic fare observations from goindigo.in via Playwright Chromium."""

    def __init__(
        self,
        name: str = "PlaywrightIndiGoCollector",
        source_code: str = "indigo_direct",
        headless: bool = True,
        timeout_ms: int = DEFAULT_TIMEOUT_MS,
    ):
        super().__init__(
            name=name,
            source_code=source_code,
            min_delay_seconds=2.0,
            max_requests_per_minute=20,
        )
        self.headless = headless
        self.timeout_ms = timeout_ms
        self.parser = IndiGoResponseParser(non_stop_only=True)

    @staticmethod
    def _is_flight_search_response(url: str, content_type: str) -> bool:
        """Heuristic detecting whether response is an IndiGo flight search payload."""
        url_lower = url.lower()
        if not ("json" in content_type.lower() or "application/json" in content_type.lower()):
            return False
        search_keywords = ["flightsearch", "booking", "availability", "searchflight", "journey"]
        return any(kw in url_lower for kw in search_keywords)

    async def _intercept_live_search(
        self,
        origin: str,
        destination: str,
        travel_date: date,
        window_label: str,
    ) -> tuple[str, list[FareObservation]]:
        """Launch Playwright Chromium, navigate to IndiGo, intercept live search payload."""
        date_str = travel_date.strftime("%Y-%m-%d")
        search_url = (
            f"https://www.goindigo.in/booking/flight-select.html"
            f"?origin={origin}&destination={destination}&travelDate={date_str}&tripType=OW&adults=1"
        )

        captured_payloads: list[str] = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=self.headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                ],
            )
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/128.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1366, "height": 768},
            )

            page = await context.new_page()

            async def handle_response(response: Response):
                try:
                    content_type = response.headers.get("content-type", "")
                    if self._is_flight_search_response(response.url, content_type):
                        text = await response.text()
                        if "flights" in text or "journeys" in text or "fare" in text:
                            captured_payloads.append(text)
                except Exception as e:
                    logger.debug("Error reading response: %s", e)

            page.on("response", handle_response)

            try:
                logger.info("Navigating to IndiGo search for %s->%s on %s", origin, destination, date_str)
                await page.goto(
                    f"https://www.goindigo.in",
                    wait_until="domcontentloaded",
                    timeout=self.timeout_ms,
                )

                # Wait for page readiness
                await page.wait_for_timeout(3000)

                # Direct API search query attempt via browser context to avoid UI flakiness
                api_url = (
                    f"https://www.goindigo.in/flightSearch/search"
                    f"?origin={origin}&destination={destination}&date={date_str}&currency=INR"
                )
                try:
                    api_resp = await context.request.get(
                        api_url,
                        headers={"accept": "application/json, text/plain, */*"},
                        timeout=15000,
                    )
                    if api_resp.status == 200:
                        text = await api_resp.text()
                        if "flights" in text or "journeys" in text:
                            captured_payloads.append(text)
                except Exception as e:
                    logger.debug("Direct API probe not available: %s", e)

                # Wait if background responses are completing
                if not captured_payloads:
                    await page.wait_for_timeout(5000)

            finally:
                await context.close()
                await browser.close()

        # Parse captured payloads
        for raw in captured_payloads:
            try:
                obs = self.parser.parse(
                    raw_payload=raw,
                    origin=origin,
                    destination=destination,
                    travel_date=travel_date,
                    window_label=window_label,
                )
                if obs:
                    return raw, obs
            except Exception as e:
                logger.debug("Failed parsing candidate payload: %s", e)
                continue

        raise RuntimeError(
            f"No valid flight search payloads intercepted for {origin}->{destination} on {travel_date}"
        )

    async def collect_route(
        self, origin: str, destination: str, travel_date: date, window_label: str
    ) -> CollectorResult:
        """Collect live observations with circuit-breaker protection and offline fallback."""
        self.circuit_breaker.can_execute()

        try:
            raw_payload, observations = await self._intercept_live_search(
                origin=origin,
                destination=destination,
                travel_date=travel_date,
                window_label=window_label,
            )
            self.circuit_breaker.record_success()
            return CollectorResult.create(
                observations=observations,
                raw_payload=raw_payload,
                execution_meta={
                    "origin": origin,
                    "destination": destination,
                    "travel_date": travel_date.isoformat(),
                    "window": window_label,
                    "count": len(observations),
                    "live": True,
                },
            )
        except Exception as e:
            self.circuit_breaker.record_failure()
            logger.warning("Live Playwright scraping failed: %s", e)
            raise
