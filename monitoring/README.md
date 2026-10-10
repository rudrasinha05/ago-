# Local monitoring

Run `python -m ago.local_ops monitor --port 8010` for bounded loopback liveness/readiness and latency. Exit 2 is an actionable local alert; response details and credentials are not emitted. Existing server request IDs help correlate errors. See [Section 11](../docs/architecture/SECTION_11_LOCAL_DEPLOYMENT.md) for failure response and deployment scope. Hosted log aggregation, traces and production alerts are deferred until deployment is requested.
