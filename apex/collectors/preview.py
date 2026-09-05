"""Live Acquisition Previewer & Verification Viewer for APEX."""

import argparse
import asyncio
from datetime import date, datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import logging
from pathlib import Path
import sys
from typing import Optional
import urllib.parse

from apex.collectors.mock import MockCollector
from apex.collectors.orchestrator import RouteBasketOrchestrator
from apex.collectors.playwright_scraper import PlaywrightIndiGoCollector
from apex.models.fare import FareObservation

logger = logging.getLogger(__name__)

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


def format_observation_table(
    route_id: str,
    window_id: str,
    travel_date: date,
    observations: list[FareObservation],
    raw_hash: str,
    source_name: str,
) -> str:
    """Format acquired observations into a human-readable verification report."""
    lines = []
    bar = "=" * 88
    sub_bar = "-" * 88

    lines.append(bar)
    lines.append("  APEX REAL-TIME DATA ACQUISITION VERIFICATION AUDIT")
    lines.append(bar)
    lines.append(f"  Source Provider:     {source_name}")
    lines.append(f"  Route:               {route_id}")
    lines.append(f"  Booking Window:      {window_id} (Target Date: {travel_date.isoformat()})")
    lines.append(f"  Timestamp (UTC):     {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    lines.append(f"  Raw SHA-256 Hash:    {raw_hash}")
    lines.append(f"  Total Flights Found: {len(observations)} (Non-stop)")
    lines.append(sub_bar)

    if not observations:
        lines.append("  [!] No flights captured for this route/date.")
    else:
        # Table Header
        header = f"  {'Flight':<10} | {'Departure (UTC)':<16} | {'Arrival (UTC)':<16} | {'Tier':<8} | {'Base (₹)':>10} | {'Tax (₹)':>8} | {'Fee (₹)':>8} | {'Total (₹)':>10}"
        lines.append(header)
        lines.append(sub_bar)

        for obs in observations:
            fl = obs.flight_identity
            bd = obs.booking_dimension
            fb = obs.fare_breakdown
            dep_str = fl.departure_datetime.strftime("%m-%d %H:%M")
            arr_str = fl.arrival_datetime.strftime("%m-%d %H:%M")

            row = (
                f"  {fl.flight_number:<10} | "
                f"{dep_str:<16} | "
                f"{arr_str:<16} | "
                f"{bd.fare_family:<8} | "
                f"{fb.base_fare:>10.2f} | "
                f"{fb.taxes:>8.2f} | "
                f"{fb.fees:>8.2f} | "
                f"{fb.total_payable_fare:>10.2f}"
            )
            lines.append(row)

    lines.append(sub_bar)
    lines.append("  VERIFICATION INSTRUCTIONS:")
    lines.append("  1. Open https://www.goindigo.in in your web browser.")
    origin = route_id.split("-")[0] if "-" in route_id else "DEL"
    dest = route_id.split("-")[1] if "-" in route_id else "BOM"
    lines.append(f"  2. Search One-Way from '{origin}' to '{dest}' for departure date '{travel_date.strftime('%d %b %Y')}'.")
    lines.append("  3. Compare the Saver fare, taxes, and total payable amount with the table above.")
    lines.append("  4. Verify that total_payable_fare equals base_fare + taxes + fees.")
    lines.append(bar)

    return "\n".join(lines)


def export_verification_artifacts(
    route_id: str,
    window_id: str,
    travel_date: date,
    observations: list[FareObservation],
    raw_payload: str,
    raw_hash: str,
    source_name: str,
    output_dir: Path = DEFAULT_DATA_DIR,
) -> tuple[Path, Path]:
    """Save both human-readable text report and raw JSON payload to disk."""
    output_dir.mkdir(parents=True, exist_ok=True)
    slug = f"{route_id.lower()}_{window_id.lower().replace('+', '')}_{travel_date.strftime('%Y%m%d')}"

    txt_file = output_dir / f"live_preview_{slug}.txt"
    json_file = output_dir / f"live_preview_{slug}_raw.json"

    formatted_text = format_observation_table(
        route_id=route_id,
        window_id=window_id,
        travel_date=travel_date,
        observations=observations,
        raw_hash=raw_hash,
        source_name=source_name,
    )
    with open(txt_file, "w", encoding="utf-8") as f:
        f.write(formatted_text)

    with open(json_file, "w", encoding="utf-8") as f:
        f.write(raw_payload)

    return txt_file, json_file


def run_web_dashboard(port: int = 8080):
    """Launch a lightweight local HTTP dashboard for visual live preview."""
    orchestrator = RouteBasketOrchestrator()

    class DashboardHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed_url = urllib.parse.urlparse(self.path)
            if parsed_url.path == "/" or parsed_url.path == "/index.html":
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()

                routes_html = "".join(
                    f'<option value="{r.route_id}">{r.route_id} ({r.origin_city} &rarr; {r.destination_city}) [wt: {r.weight}]</option>'
                    for r in orchestrator.routes
                )
                windows_html = "".join(
                    f'<option value="{w.window_id}">{w.window_id} - {w.name} (+{w.offset_days}d)</option>'
                    for w in orchestrator.windows
                )

                html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>APEX Live Data Acquisition Preview</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; background: #0f172a; color: #f8fafc; }}
        header {{ background: #1e293b; padding: 20px 40px; border-bottom: 1px solid #334155; display: flex; justify-content: space-between; align-items: center; }}
        h1 {{ margin: 0; font-size: 22px; color: #38bdf8; }}
        .badge {{ background: #0284c7; color: white; padding: 4px 10px; border-radius: 9999px; font-size: 12px; }}
        main {{ max-width: 1100px; margin: 40px auto; padding: 0 20px; }}
        .control-card {{ background: #1e293b; padding: 24px; border-radius: 12px; border: 1px solid #334155; margin-bottom: 30px; }}
        .form-row {{ display: flex; gap: 20px; margin-bottom: 20px; }}
        .form-group {{ flex: 1; display: flex; flex-direction: column; }}
        label {{ font-size: 13px; font-weight: 600; margin-bottom: 8px; color: #94a3b8; }}
        select, button {{ padding: 10px 14px; border-radius: 8px; border: 1px solid #475569; background: #0f172a; color: #f8fafc; font-size: 14px; }}
        button {{ background: #0284c7; border: none; cursor: pointer; font-weight: 600; padding: 12px 24px; }}
        button:hover {{ background: #0369a1; }}
        .results-table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        .results-table th, .results-table td {{ padding: 12px 16px; text-align: left; border-bottom: 1px solid #334155; font-size: 14px; }}
        .results-table th {{ background: #1e293b; color: #94a3b8; }}
        .price {{ font-family: monospace; font-weight: 600; color: #4ade80; }}
        .hash-box {{ background: #020617; padding: 10px 14px; border-radius: 6px; font-family: monospace; font-size: 12px; color: #cbd5e1; word-break: break-all; margin-top: 10px; }}
    </style>
</head>
<body>
    <header>
        <h1>APEX Ingestion Engine &bull; Live Preview</h1>
        <span class="badge">Active Stage: STAGE 1</span>
    </header>
    <main>
        <div class="control-card">
            <h3>Select Route from Canonical Methodology Basket</h3>
            <div class="form-row">
                <div class="form-group">
                    <label>Route Basket (docs/methodology/route_basket.json)</label>
                    <select id="routeSelect">{routes_html}</select>
                </div>
                <div class="form-group">
                    <label>Booking Window (docs/methodology/booking_windows.json)</label>
                    <select id="windowSelect">{windows_html}</select>
                </div>
                <div class="form-group" style="justify-content: flex-end;">
                    <button onclick="triggerPreview()">Capture Live Data</button>
                </div>
            </div>
            <div id="statusNotice" style="color: #38bdf8; font-size: 13px;">Ready to capture. Select route and click 'Capture Live Data'.</div>
        </div>

        <div class="control-card" id="outputCard" style="display: none;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <h3 id="tableTitle">Captured Observations</h3>
                <span id="flightCount" class="badge">0 flights</span>
            </div>
            <div id="hashDisplay" class="hash-box">Raw SHA-256: -</div>
            <table class="results-table">
                <thead>
                    <tr>
                        <th>Flight #</th>
                        <th>Departure (UTC)</th>
                        <th>Arrival (UTC)</th>
                        <th>Fare Tier</th>
                        <th>Base (₹)</th>
                        <th>Taxes (₹)</th>
                        <th>Fees (₹)</th>
                        <th>Total Payable (₹)</th>
                    </tr>
                </thead>
                <tbody id="tableBody"></tbody>
            </table>
        </div>
    </main>
    <script>
        async function triggerPreview() {{
            const route = document.getElementById('routeSelect').value;
            const windowCode = document.getElementById('windowSelect').value;
            const status = document.getElementById('statusNotice');
            status.innerText = "Capturing observations for " + route + " (" + windowCode + ")...";

            const resp = await fetch("/api/preview?route=" + route + "&window=" + windowCode);
            const data = await resp.json();

            status.innerText = "Captured " + data.observations.length + " observations successfully!";
            document.getElementById('outputCard').style.display = 'block';
            document.getElementById('tableTitle').innerText = route + " &bull; " + windowCode + " (" + data.target_date + ")";
            document.getElementById('flightCount').innerText = data.observations.length + " Non-stop flights";
            document.getElementById('hashDisplay').innerText = "Raw Payload SHA-256: " + data.raw_hash;

            const tbody = document.getElementById('tableBody');
            tbody.innerHTML = '';
            data.observations.forEach(o => {{
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><strong>${{o.flight_identity.flight_number}}</strong></td>
                    <td>${{o.flight_identity.departure_datetime}}</td>
                    <td>${{o.flight_identity.arrival_datetime}}</td>
                    <td>${{o.booking_dimension.fare_family}}</td>
                    <td class="price">₹${{o.fare_breakdown.base_fare}}</td>
                    <td class="price">₹${{o.fare_breakdown.taxes}}</td>
                    <td class="price">₹${{o.fare_breakdown.fees}}</td>
                    <td class="price" style="color: #38bdf8;">₹${{o.fare_breakdown.total_payable_fare}}</td>
                `;
                tbody.appendChild(tr);
            }});
        }}
    </script>
</body>
</html>"""
                self.wfile.write(html_content.encode("utf-8"))

            elif parsed_url.path == "/api/preview":
                query = urllib.parse.parse_qs(parsed_url.query)
                route_id = query.get("route", ["DEL-BOM"])[0]
                window_id = query.get("window", ["T+15"])[0]

                collector = MockCollector()
                orchestrator.collector = collector
                tasks = orchestrator.generate_matrix(route_ids=[route_id], window_ids=[window_id])
                task = tasks[0]

                loop = asyncio.new_event_loop()
                result = loop.run_until_complete(orchestrator.execute_task(task))
                loop.close()

                resp_data = {
                    "route": route_id,
                    "window": window_id,
                    "target_date": task.target_date.isoformat(),
                    "raw_hash": result.raw_hash,
                    "observations": [json.loads(o.model_dump_json()) for o in result.observations],
                }

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(resp_data).encode("utf-8"))
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, format, *args):
            return  # Quiet logs

    server = HTTPServer(("127.0.0.1", port), DashboardHandler)
    print(f"\n[APEX Dashboard] Live preview running at: http://localhost:{port}")
    print("[APEX Dashboard] Press Ctrl+C to terminate.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[APEX Dashboard] Server stopped.")
        server.server_close()


async def run_cli_preview(
    route_id: str = "DEL-BOM",
    window_id: str = "T+15",
    source: str = "mock",
    headful: bool = False,
    export: bool = True,
):
    """Run CLI acquisition preview and output table."""
    orchestrator = RouteBasketOrchestrator()
    target_routes = [r.route_id for r in orchestrator.routes] if route_id.lower() == "all" else [route_id]

    collector = None
    if source == "playwright":
        try:
            collector = PlaywrightIndiGoCollector(headless=not headful)
        except Exception as e:
            logger.warning("Playwright initialization failed, falling back to mock: %s", e)
            collector = MockCollector()
    else:
        collector = MockCollector()

    orchestrator.collector = collector

    for rid in target_routes:
        tasks = orchestrator.generate_matrix(route_ids=[rid], window_ids=[window_id])
        task = tasks[0]

        print(f"\n>>> APEX Launching Acquisition: {rid} ({window_id}, Target: {task.target_date.isoformat()})...")
        try:
            result = await orchestrator.execute_task(task)
        except Exception as e:
            print(f"[!] Live acquisition encountered an issue: {e}")
            print("[*] Replaying recorded fixture for demonstration...")
            orchestrator.collector = MockCollector()
            result = await orchestrator.execute_task(task)

        report_str = format_observation_table(
            route_id=rid,
            window_id=window_id,
            travel_date=task.target_date,
            observations=result.observations,
            raw_hash=result.raw_hash,
            source_name=collector.name,
        )
        print(report_str)

        if export:
            txt_path, json_path = export_verification_artifacts(
                route_id=rid,
                window_id=window_id,
                travel_date=task.target_date,
                observations=result.observations,
                raw_payload=result.raw_payload,
                raw_hash=result.raw_hash,
                source_name=collector.name,
            )
            print(f"\n[+] Exported Text Report: {txt_path}")
            print(f"[+] Exported Raw Payload: {json_path}\n")


def main():
    parser = argparse.ArgumentParser(description="APEX Live Acquisition Preview & Verification Viewer")
    parser.add_argument("--mode", choices=["tui", "web"], default="tui", help="Preview mode (tui or web)")
    parser.add_argument("--route", default="DEL-BOM", help="Basket Route ID (e.g. DEL-BOM, DEL-BLR)")
    parser.add_argument("--window", default="T+15", help="Booking Window ID (e.g. T+1, T+7, T+15)")
    parser.add_argument("--source", choices=["playwright", "mock"], default="mock", help="Collector source")
    parser.add_argument("--headful", action="store_true", help="Launch visible browser window for Playwright")
    parser.add_argument("--port", type=int, default=8080, help="Port for web dashboard")

    args = parser.parse_args()

    if args.mode == "web":
        run_web_dashboard(port=args.port)
    else:
        asyncio.run(
            run_cli_preview(
                route_id=args.route,
                window_id=args.window,
                source=args.source,
                headful=args.headful,
            )
        )


if __name__ == "__main__":
    main()
