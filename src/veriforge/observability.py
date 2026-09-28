import json
import threading
import time

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult
from prometheus_client import Counter, Histogram

from veriforge.config import LOCAL
from veriforge.db import connect

REQUESTS = Counter("veriforge_http_requests_total", "HTTP requests", ["path", "status"])
LATENCY = Histogram("veriforge_http_duration_seconds", "HTTP response latency", ["path"])
_lock = threading.Lock()


class LocalSpanExporter(SpanExporter):
    def export(self, spans):
        LOCAL.mkdir(exist_ok=True)
        with _lock, (LOCAL / "traces.jsonl").open("a") as f:
            for span in spans:
                f.write(
                    json.dumps(
                        {
                            "trace_id": format(span.context.trace_id, "032x"),
                            "name": span.name,
                            "start_ns": span.start_time,
                            "end_ns": span.end_time,
                            "attributes": dict(span.attributes),
                        }
                    )
                    + "\n"
                )
        return SpanExportResult.SUCCESS


provider = TracerProvider()
provider.add_span_processor(SimpleSpanProcessor(LocalSpanExporter()))
tracer = provider.get_tracer("veriforge")


async def instrument(request, call_next):
    start = time.monotonic()
    with tracer.start_as_current_span("http.request") as span:
        response = await call_next(request)
        path = getattr(request.scope.get("route"), "path", "static")
        duration = time.monotonic() - start
        span.set_attribute("http.route", path)
        span.set_attribute("http.response.status_code", response.status_code)
        REQUESTS.labels(path, str(response.status_code)).inc()
        LATENCY.labels(path).observe(duration)
        trace_id = format(span.context.trace_id, "032x")
        response.headers["X-Trace-ID"] = trace_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        if path.startswith("/api/"):
            with connect() as conn:
                conn.execute(
                    "INSERT INTO http_events(path,status,duration_ms,trace_id) VALUES (%s,%s,%s,%s)",
                    (path, response.status_code, duration * 1000, trace_id),
                )
        return response
