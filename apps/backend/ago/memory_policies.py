"""Explicit bounded experience values and deterministic extractive summaries."""
from uuid import UUID


def validate_memory(scope: str, scope_id: str, kind: str, content: str,
                    source_ref: str, retention_hours: int) -> None:
    UUID(scope_id)
    if scope not in {'employee', 'department', 'project', 'company'}:
        raise ValueError('Unknown memory scope')
    if kind not in {'episodic', 'working', 'summary'}:
        raise ValueError('Unknown memory kind')
    if not 1 <= len(content.strip()) <= 12000 or not 1 <= len(source_ref.strip()) <= 1000:
        raise ValueError('Bounded content and provenance required')
    maximum = 24 if kind == 'working' else 365 * 24
    if type(retention_hours) is not int or not 1 <= retention_hours <= maximum:
        raise ValueError('Invalid memory retention')


def extractive_summary(records: list[dict]) -> str:
    if not 2 <= len(records) <= 20:
        raise ValueError('Consolidation requires 2–20 explicit sources')
    # Verbatim excerpts: no new facts and no request to a model/provider.
    return '\n'.join(record['content'][:400] for record in records)
