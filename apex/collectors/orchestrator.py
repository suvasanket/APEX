"""Route Basket & Booking Window Matrix Orchestrator for APEX."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from apex.collectors.base import BaseCollector, CollectorResult
from apex.models.fare import (
    BookingWindow,
    calculate_observation_target_date,
    get_window_offset,
)

METHODOLOGY_DIR = Path(__file__).resolve().parent.parent.parent / "docs" / "methodology"
DEFAULT_ROUTES_PATH = METHODOLOGY_DIR / "route_basket.json"
DEFAULT_WINDOWS_PATH = METHODOLOGY_DIR / "booking_windows.json"


class RouteDefinition(BaseModel):
    """Definition of a canonical domestic basket route."""

    model_config = ConfigDict(frozen=True)

    route_id: str = Field(..., description="Unique route identifier (e.g. DEL-BOM)")
    origin_iata: str = Field(..., min_length=3, max_length=3)
    origin_city: str
    destination_iata: str = Field(..., min_length=3, max_length=3)
    destination_city: str
    direction: str = "one_way"
    weight: float = Field(..., ge=0.0, le=1.0)
    description: str


class BookingWindowDefinition(BaseModel):
    """Definition of a canonical booking lead-time window."""

    model_config = ConfigDict(frozen=True)

    window_id: str = Field(..., description="Window code (T+1, T+7, T+15, T+30, T+45)")
    offset_days: int = Field(..., ge=0)
    name: str
    rationale: str


class CollectionTask(BaseModel):
    """Single execution task pairing a route and a booking window."""

    model_config = ConfigDict(frozen=True)

    route: RouteDefinition
    window: BookingWindowDefinition
    collection_date: date
    target_date: date

    @property
    def task_id(self) -> str:
        return f"{self.route.route_id}_{self.window.window_id}_{self.target_date.strftime('%Y%m%d')}"


class RouteBasketOrchestrator:
    """Orchestrates acquisition across the 5x5 route-window methodology matrix."""

    def __init__(
        self,
        collector: Optional[BaseCollector] = None,
        routes_path: Optional[Path | str] = None,
        windows_path: Optional[Path | str] = None,
    ):
        self.collector = collector
        self.routes_path = Path(routes_path) if routes_path else DEFAULT_ROUTES_PATH
        self.windows_path = Path(windows_path) if windows_path else DEFAULT_WINDOWS_PATH

        self._routes = self._load_routes()
        self._windows = self._load_windows()

    def _load_routes(self) -> list[RouteDefinition]:
        with open(self.routes_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        routes = [RouteDefinition(**item) for item in data]
        if not routes:
            raise ValueError(f"No routes loaded from {self.routes_path}")
        total_weight = sum(r.weight for r in routes)
        if abs(total_weight - 1.0) > 1e-5:
            raise ValueError(f"Route weights must sum to 1.0, got: {total_weight}")
        return routes

    def _load_windows(self) -> list[BookingWindowDefinition]:
        with open(self.windows_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        windows = [BookingWindowDefinition(**item) for item in data]
        if not windows:
            raise ValueError(f"No booking windows loaded from {self.windows_path}")
        return windows

    @property
    def routes(self) -> list[RouteDefinition]:
        """Return list of canonical routes."""
        return list(self._routes)

    @property
    def windows(self) -> list[BookingWindowDefinition]:
        """Return list of canonical booking windows."""
        return list(self._windows)

    def get_route(self, route_id: str) -> RouteDefinition:
        """Find a route by its identifier."""
        clean_id = route_id.strip().upper()
        for r in self._routes:
            if r.route_id == clean_id:
                return r
        raise KeyError(f"Route '{route_id}' not found in basket.")

    def get_window(self, window_id: str) -> BookingWindowDefinition:
        """Find a booking window by its identifier."""
        clean_id = window_id.strip().upper()
        for w in self._windows:
            if w.window_id == clean_id:
                return w
        raise KeyError(f"Window '{window_id}' not found in methodology.")

    def generate_matrix(
        self,
        collection_date: Optional[date] = None,
        route_ids: Optional[list[str]] = None,
        window_ids: Optional[list[str]] = None,
    ) -> list[CollectionTask]:
        """Generate the collection task matrix (default: 5 routes x 5 windows = 25 tasks)."""
        base_date = collection_date or datetime.now(timezone.utc).date()

        target_routes = (
            [self.get_route(rid) for rid in route_ids] if route_ids else self._routes
        )
        target_windows = (
            [self.get_window(wid) for wid in window_ids] if window_ids else self._windows
        )

        tasks = []
        for r in target_routes:
            for w in target_windows:
                target_dt = base_date + timedelta(days=w.offset_days)
                tasks.append(
                    CollectionTask(
                        route=r,
                        window=w,
                        collection_date=base_date,
                        target_date=target_dt,
                    )
                )
        return tasks

    async def execute_task(self, task: CollectionTask) -> CollectorResult:
        """Execute a single collection task with the configured collector."""
        if self.collector is None:
            raise RuntimeError("No collector configured in orchestrator.")

        return await self.collector.collect_route(
            origin=task.route.origin_iata,
            destination=task.route.destination_iata,
            travel_date=task.target_date,
            window_label=task.window.window_id,
        )

    async def execute_matrix(
        self,
        collection_date: Optional[date] = None,
        route_ids: Optional[list[str]] = None,
        window_ids: Optional[list[str]] = None,
    ) -> list[CollectorResult]:
        """Execute all tasks in the matrix sequentially."""
        tasks = self.generate_matrix(
            collection_date=collection_date,
            route_ids=route_ids,
            window_ids=window_ids,
        )
        results = []
        for t in tasks:
            result = await self.execute_task(t)
            results.append(result)
        return results
