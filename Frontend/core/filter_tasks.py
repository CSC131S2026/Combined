"""
Background-friendly filter computations for the dashboard.
"""

from dataclasses import dataclass

from core.filter_engine import FilterEngine


@dataclass(frozen=True)
class FilterTaskResult:
    filtered_records: list
    filtered_agg: dict
    all_agg: dict


def compute_full_aggregates(records: list, engine: FilterEngine | None = None) -> dict:
    """Compute aggregate statistics for a loaded dataset."""
    engine = engine or FilterEngine()
    return engine.compute_aggregates(records)


def compute_filter_task(
    records: list,
    filters: dict,
    all_agg: dict | None,
    engine: FilterEngine | None = None,
) -> FilterTaskResult:
    """Apply filters and compute visible aggregates, reusing cached full aggregates."""
    engine = engine or FilterEngine()
    filtered_records = engine.apply(records, dict(filters or {}))
    return FilterTaskResult(
        filtered_records=filtered_records,
        filtered_agg=engine.compute_aggregates(filtered_records),
        all_agg=all_agg if all_agg is not None else engine.compute_aggregates(records),
    )
