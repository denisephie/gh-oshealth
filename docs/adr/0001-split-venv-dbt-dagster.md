Split virtualenvs for dbt and Dagster

## Status
Accepted — 2026-08-05

## Context
Both `dagster` and `dbt-core` pin transitive dependencies tightly. Jinja2, protobuf, and the `dbt-*` adapters are known flashpoints. In a single environment, an upgrade to either package can produce a resolver conflict that blocks all work until one side cuts a release — and the failure surfaces as an opaque wall of version constraints, not as an actionable error.

Separately, `dagster-dbt` does not import dbt's Python API. `DbtCliResource` shells out to a `dbt` binary. The integration is already subprocess-based, so sharing an interpreter buys nothing the integration actually uses.

## Decision
Two environments:
* Root `pyproject.toml` / `.venv` — extraction, shared Python, and Dagster.
*`transform/pyproject.toml` / `transform/.venv` — `dbt-core`, `dbt-duckdb`,`dbt-bigquery` only. -> will be added later when dbt is added

Dagster invokes dbt as a subprocess via `DbtCliResource`, pointed at the`transform/` project directory.

## Alternatives rejected
Single environment. One `uv sync`, one lockfile, one interpreter path to
reason about. Simpler to run and to explain in CI. Rejected because it accepts an upgrade-deadlock risk in exchange for convenience the subprocess boundary already provides.

## Consequences
* The dbt project runs standalone: `cd transform && dbt build` works with no Dagster installed. 
* dbt adapter upgrades and Dagster upgrades are independent.
* Cost: two lockfiles to keep current, two `uv sync` steps in CI and two Docker layers later. Contributors must know which environment a command belongs to.
* The `dbt` binary path becomes configuration. `DbtCliResource` needs an explicit path to `transform/.venv/bin/dbt`; it will not be on `PATH` when Dagster runs.