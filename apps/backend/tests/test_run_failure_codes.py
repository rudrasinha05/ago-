"""Issue #10: failed runs get a fixed, secret-free reason code (never exception text)."""
import socket
from urllib.error import URLError

import pytest

from ago.agent_runtime import RUN_FAILURE_CODES, run_failure_code
from ago.credit_domain import CreditBudgetExceeded, CreditBudgetMissing


def chained(outer, inner):
    try:
        try:
            raise inner
        except Exception as exc:
            raise outer from exc
    except Exception as final:
        return final


@pytest.mark.parametrize("exc,code", [
    (CreditBudgetMissing("No configured virtual-credit budget"), "credit_budget_missing"),
    (CreditBudgetExceeded("Virtual-credit budget exceeded"), "credit_budget_exceeded"),
    (TimeoutError("timed out"), "model_timeout"),
    (socket.timeout("timed out"), "model_timeout"),
    (URLError(TimeoutError("slow")), "model_timeout"),
    (URLError(ConnectionRefusedError(111, "refused")), "model_unreachable"),
    (ConnectionResetError("reset"), "model_unreachable"),
    (RuntimeError("Local model did not complete"), "model_incomplete"),
    (ValueError("Agent result must be a dictionary"), "handler_error"),
    (PermissionError("No configured virtual-credit budget"), "handler_error"),
])
def test_codes_come_from_exception_types(exc, code):
    assert run_failure_code(exc) == code
    assert code in RUN_FAILURE_CODES


def test_wrapped_causes_are_found_and_cycles_terminate():
    wrapped = chained(RuntimeError("chain role failed"), CreditBudgetMissing("x"))
    assert run_failure_code(wrapped) == "credit_budget_missing"
    first, second = RuntimeError("a"), RuntimeError("b")
    first.__cause__, second.__cause__ = second, first
    assert run_failure_code(first) == "handler_error"


def test_typed_credit_errors_remain_permission_errors_for_existing_callers():
    assert issubclass(CreditBudgetMissing, PermissionError)
    assert issubclass(CreditBudgetExceeded, PermissionError)
