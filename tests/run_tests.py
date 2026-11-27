#!/usr/bin/env python3
"""qnxcheck test suite — stdlib only, no pytest needed.

Run:  python3 tests/run_tests.py
Exit code 0 when every test passes.

Each test asserts the rule codes qnxcheck reports for a fixture, plus
dogfooding: the skeleton `qnxcheck init` generates must pass `qnxcheck
check` with zero findings.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from qnxcheck.buildfile import parse_buildfile
from qnxcheck.ccheck import check_c_source
from qnxcheck.cli import main as cli_main
from qnxcheck.init import generate
from qnxcheck.makecheck import check_makefile

HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(HERE, "fixtures")


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _rules(report):
    return {f.rule for f in report.findings}


def _run(name, fn):
    try:
        fn()
    except AssertionError as exc:
        print(f"FAIL {name}: {exc}")
        return False
    except Exception as exc:  # noqa: BLE001 — report any crash as failure
        print(f"ERROR {name}: {type(exc).__name__}: {exc}")
        return False
    print(f"PASS {name}")
    return True


# ---- buildfile tests ------------------------------------------------

def test_buildfile_valid_qemu():
    r = parse_buildfile(_read(f"{FIX}/buildfiles/valid-qemu-x86_64.build"),
                        "valid-qemu-x86_64.build")
    assert r.errors == 0 and r.warnings == 0, r.render_text()


def test_buildfile_valid_shell_docs_example():
    r = parse_buildfile(_read(f"{FIX}/buildfiles/valid-shell.build"),
                        "valid-shell.build")
    assert r.errors == 0 and r.warnings == 0, r.render_text()


def test_buildfile_valid_rpi5():
    r = parse_buildfile(_read(f"{FIX}/buildfiles/valid-rpi5.build"),
                        "valid-rpi5.build")
    assert r.errors == 0 and r.warnings == 0, r.render_text()


def _bad_buildfile(rule, filename):
    r = parse_buildfile(_read(f"{FIX}/buildfiles/{filename}"), filename)
    assert rule in _rules(r), (
        f"expected {rule} in {sorted(_rules(r))}:\n{r.render_text()}")


def test_buildfile_bad_rules():
    cases = [
        ("B01", "bad-B01-unknown-attr.build"),
        ("B02", "bad-B02-two-bracket-groups.build"),
        ("B03", "bad-B03-empty-value.build"),
        ("B04", "bad-B04-unclosed-inline.build"),
        ("B05", "bad-B05-no-bootstrap.build"),
        ("B06", "bad-B06-no-script.build"),
        ("B07", "bad-B07-no-procnto.build"),
        ("B07", "bad-B07b-procnto-not-last.build"),
        ("B08", "bad-B08-no-startup.build"),
        ("B09", "bad-B09-duplicate-target.build"),
        ("B10", "bad-B10-nonexec-boot-binary.build"),
        ("B11", "bad-B11-bad-perms.build"),
        ("B12", "bad-B12-link-no-target.build"),
        ("B13", "bad-B13-script-missing-binary.build"),
        ("B15", "bad-B15-unknown-arch.build"),
        ("B16", "bad-B16-comment-no-space.build"),
        ("B17", "bad-B17-two-bootstraps.build"),
    ]
    for rule, filename in cases:
        _bad_buildfile(rule, filename)


# ---- C checker tests -------------------------------------------------

def test_c_good_server_clean():
    r = check_c_source(_read(f"{FIX}/c/good-server.c"), "good-server.c")
    assert r.errors == 0 and r.warnings == 0, r.render_text()


def test_c_good_client_clean():
    # TimerTimeout arms the MsgSend, so C06 must not fire.
    r = check_c_source(_read(f"{FIX}/c/good-client.c"), "good-client.c")
    assert r.errors == 0 and r.warnings == 0, r.render_text()


def test_c_bad_client_all_rules():
    r = check_c_source(_read(f"{FIX}/c/bad-client.c"), "bad-client.c")
    rules = _rules(r)
    expected = {"C02", "C03", "C04", "C05", "C06", "C07", "C08", "C09",
                "C10", "C11", "C12", "C13", "C14", "C15"}
    missing = expected - rules
    assert not missing, f"missing rules {sorted(missing)}:\n{r.render_text()}"


# ---- makefile checker tests ------------------------------------------

def test_makefile_good_clean():
    r = check_makefile(_read(f"{FIX}/makefiles/good-Makefile"),
                       "good-Makefile")
    assert r.errors == 0 and r.warnings == 0, r.render_text()


def test_makefile_bad_rules():
    r = check_makefile(_read(f"{FIX}/makefiles/bad-Makefile"),
                       "bad-Makefile")
    rules = _rules(r)
    for rule in ("M01", "M02", "M03", "M04", "M05"):
        assert rule in rules, f"missing {rule} in {sorted(rules)}"


# ---- dogfooding: init skeleton must pass qnxcheck check --------------

def test_init_skeleton_passes_check():
    with tempfile.TemporaryDirectory() as tmp:
        for target in ("x86_64", "rpi5"):
            out = os.path.join(tmp, target)
            generate(target, "qnx-hello", out)
            code = cli_main(["check", out])
            assert code == 0, (
                f"qnxcheck init --target {target} skeleton fails "
                f"qnxcheck check (exit {code})")


def test_cli_json_output():
    r = parse_buildfile(
        _read(f"{FIX}/buildfiles/bad-B01-unknown-attr.build"), "x.build")
    import json
    data = json.loads(r.render_json())
    assert data["summary"]["errors"] >= 1
    assert any(f["rule"] == "B01" for f in data["findings"])


TESTS = [
    ("buildfile: valid qemu x86_64", test_buildfile_valid_qemu),
    ("buildfile: valid shell (QNX docs example)",
     test_buildfile_valid_shell_docs_example),
    ("buildfile: valid rpi5", test_buildfile_valid_rpi5),
    ("buildfile: all bad fixtures fire their rule",
     test_buildfile_bad_rules),
    ("c: good server clean", test_c_good_server_clean),
    ("c: good client clean (TimerTimeout arms MsgSend)",
     test_c_good_client_clean),
    ("c: bad client fires C02-C15", test_c_bad_client_all_rules),
    ("makefile: good clean", test_makefile_good_clean),
    ("makefile: bad fires M01-M05", test_makefile_bad_rules),
    ("dogfood: init skeleton passes qnxcheck check",
     test_init_skeleton_passes_check),
    ("cli: JSON output parses", test_cli_json_output),
]


def main():
    passed = 0
    for name, fn in TESTS:
        if _run(name, fn):
            passed += 1
    print(f"\n{passed}/{len(TESTS)} tests passed")
    return 0 if passed == len(TESTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
