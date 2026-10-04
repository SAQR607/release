"""CLI wiring for `produce` — the production entry point used by Actions.

One failing job must never block the other due jobs; exit code is red if
anything failed.
"""

from __future__ import annotations

from app import cli, pipeline, schedule, state
from app.config import Config
from app.state import Stage

CFG = Config(data={"telegram": {"notify_failure": False}}, path=__file__)


def _wire(monkeypatch, jobs):
    monkeypatch.setattr(cli, "load_config", lambda **kw: CFG)
    monkeypatch.setattr(schedule, "plan_due", lambda cfg, reg: jobs)
    monkeypatch.setattr(state, "load_registry", lambda p: object())


def _parse(argv):
    return cli.build_parser().parse_args(argv)


def test_produce_command_registered():
    args = _parse(["produce", "--dry-run", "--sample", "10", "--private-test"])
    assert args.func is cli._cmd_produce
    assert args.dry_run and args.sample == 10.0 and args.private_test


def test_produce_runs_every_job_despite_failure(monkeypatch):
    jobs = [{"kind": "long", "episode_id": "s01e001"},
            {"kind": "shorts", "episode_id": "s01e001"}]
    _wire(monkeypatch, jobs)
    calls: list = []

    def fake_long(episode_id, **kw):
        calls.append(("long", episode_id, kw.get("dry_run"), kw.get("sample_sec")))
        raise SystemExit(1)

    def fake_shorts(episode_id, **kw):
        calls.append(("shorts", episode_id, kw.get("dry_run"), None))
        return Stage.COMPLETE

    monkeypatch.setattr(pipeline, "run_long", fake_long)
    monkeypatch.setattr(pipeline, "run_shorts", fake_shorts)

    args = _parse(["produce", "--dry-run", "--sample", "10"])
    rc = args.func(args)
    assert rc == 1
    assert [c[0] for c in calls] == ["long", "shorts"]  # long failed, shorts still ran
    assert calls[0][2] is True and calls[0][3] == 10.0


def test_produce_all_ok_returns_zero(monkeypatch):
    _wire(monkeypatch, [{"kind": "shorts", "episode_id": "s01e001"}])
    monkeypatch.setattr(pipeline, "run_shorts",
                        lambda episode_id, **kw: Stage.COMPLETE)
    args = _parse(["produce"])
    assert args.func(args) == 0


def test_produce_nothing_due_returns_zero(monkeypatch):
    _wire(monkeypatch, [])
    args = _parse(["produce"])
    assert args.func(args) == 0
