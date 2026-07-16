"""Optional OTLP runtime for API and worker composition roots."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import FastAPI
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Tracer


@dataclass(slots=True)
class TelemetryRuntime:
    service_name: str
    tracer_provider: TracerProvider
    meter_provider: MeterProvider

    @property
    def tracer(self) -> Tracer:
        return self.tracer_provider.get_tracer("cmp", "1.0.0")

    def instrument_fastapi(self, application: FastAPI) -> None:
        FastAPIInstrumentor.instrument_app(
            application,
            tracer_provider=self.tracer_provider,
            meter_provider=self.meter_provider,
        )

    def shutdown(self) -> None:
        self.tracer_provider.shutdown()
        self.meter_provider.shutdown()


def _signal_url(endpoint: str, signal: str) -> str:
    base = endpoint.rstrip("/")
    return base if base.endswith(f"/v1/{signal}") else f"{base}/v1/{signal}"


def build_telemetry_runtime(
    *,
    service_name: str,
    environment: str,
    endpoint: str | None,
    export_interval_ms: int = 10_000,
) -> TelemetryRuntime:
    """Build an SDK runtime; missing endpoint intentionally means local no-export mode."""

    if export_interval_ms < 1_000:
        raise ValueError("OpenTelemetry export interval must be at least 1000 ms")
    resource = Resource.create(
        {
            "service.name": service_name,
            "service.namespace": "cae-material-platform",
            "deployment.environment.name": environment,
        }
    )
    tracer_provider = TracerProvider(resource=resource)
    metric_readers = []
    if endpoint is not None:
        tracer_provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=_signal_url(endpoint, "traces")))
        )
        metric_readers.append(
            PeriodicExportingMetricReader(
                OTLPMetricExporter(endpoint=_signal_url(endpoint, "metrics")),
                export_interval_millis=export_interval_ms,
            )
        )
    meter_provider = MeterProvider(resource=resource, metric_readers=metric_readers)
    return TelemetryRuntime(service_name, tracer_provider, meter_provider)
