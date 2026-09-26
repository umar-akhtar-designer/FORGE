"""Multi-language runners — real parsing of go/cargo test output."""

from __future__ import annotations


def test_parse_go_events_passes_and_failures():
    from app.agents.tester import _parse_go_events

    stream = (
        '{"Action":"run","Package":"acme/math","Test":"TestAdd"}\n'
        '{"Action":"pass","Package":"acme/math","Test":"TestAdd","Elapsed":0.01}\n'
        '{"Action":"run","Package":"acme/math","Test":"TestDivideByZero"}\n'
        '{"Action":"fail","Package":"acme/math","Test":"TestDivideByZero","Elapsed":0.01}\n'
        '{"Action":"skip","Package":"acme/math","Test":"TestSkip"}\n'
        '{"Action":"pass","Package":"acme/math","Elapsed":0.1}\n'
    )
    rows, total, failed = _parse_go_events(stream)
    assert total == 2
    assert failed == 1
    assert rows[0]["path"] == "acme/math"
    assert rows[1]["status"] == "failed"


def test_parse_go_events_tolerates_garbage_lines():
    from app.agents.tester import _parse_go_events

    rows, _, _ = _parse_go_events("not json\nPASS\n\n")
    assert rows == []


def test_parse_cargo_names_and_counts():
    from app.agents.tester import _parse_cargo

    out = (
        "running 3 tests\n"
        "test math::test_add ... ok\n"
        "test math::test_div_by_zero ... FAILED\n"
        "test util::test_escape ... ok\n"
        "test result: FAILED. 2 passed; 1 failed\n"
    )
    rows, total, failed = _parse_cargo(out)
    assert total == 3
    assert failed == 1
    assert rows[0]["name"] == "math::test_add"
    assert rows[2]["status"] == "passed"


def test_parse_cargo_summary_only():
    from app.agents.tester import _parse_cargo

    rows, total, failed = _parse_cargo("test result: ok. 5 passed; 0 failed; 0 ignored")
    assert rows == []
    assert total == 5
    assert failed == 0