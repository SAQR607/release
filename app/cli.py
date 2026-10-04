"""CLI entry point: `python -m app <command>` (§41)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import ROOT, load_config
from .logging_setup import setup_logging


def _cmd_init(_args: argparse.Namespace) -> int:
    from .config import EXAMPLE_PATH, LOCAL_PATH
    import shutil

    made = []
    if not LOCAL_PATH.exists():
        shutil.copyfile(EXAMPLE_PATH, LOCAL_PATH)
        made.append(str(LOCAL_PATH.relative_to(ROOT)))
    for sub in ("state", "workspace", "state/story_memory", "state/episodes", "assets", "universe"):
        p = ROOT / sub
        if not p.exists():
            p.mkdir(parents=True, exist_ok=True)
            made.append(sub + "/")
    if not (ROOT / ".env").exists() and (ROOT / ".env.example").exists():
        (ROOT / ".env").write_text((ROOT / ".env.example").read_text(encoding="utf-8"), encoding="utf-8")
        made.append(".env")
    print("created: " + (", ".join(made) if made else "nothing (already present)"))
    print("next: fill .env secrets, then run `python -m app doctor`")
    return 0


def _cmd_doctor(args: argparse.Namespace) -> int:
    from . import doctor

    return doctor.main(online=args.online)


def _cmd_status(_args: argparse.Namespace) -> int:
    from .state import load_registry

    cfg = load_config(allow_example=True)
    reg = load_registry(cfg.get("paths.state", "state"))
    eps = reg.episodes()
    if not eps:
        print("no episodes registered yet")
        return 0
    print(f"{'episode':<9} {'stage':<18} {'slot':<22} {'att':>3}  title")
    for ep_id in sorted(eps):
        e = eps[ep_id]
        title = (e.get("title") or "")[:40]
        print(f"{ep_id:<9} {e['stage']:<18} {e.get('slot_key', ''):<22} {e.get('attempts', 0):>3}  {title}")
    return 0


def _cmd_schedule(args: argparse.Namespace) -> int:
    from .schedule import plan_due
    from .state import load_registry

    cfg = load_config(allow_example=True)
    reg = load_registry(cfg.get("paths.state", "state"))
    jobs = plan_due(cfg, reg)
    if args.json:
        print(json.dumps(jobs, indent=2))
    else:
        if not jobs:
            print("nothing due")
        for job in jobs:
            print(json.dumps(job))
    return 0


def _parse_stop_after(name: str | None):
    if not name:
        return None
    from .state import Stage

    return Stage(name.upper())


def _cmd_run(args: argparse.Namespace) -> int:
    from .pipeline import run_long
    from .schedule import plan_due
    from .state import load_registry

    episode_id = args.episode
    if not episode_id:
        cfg = load_config(allow_example=True)
        reg = load_registry(cfg.get("paths.state", "state"))
        jobs = [j for j in plan_due(cfg, reg) if j["kind"] == "long"]
        if not jobs:
            print("no long-form job due now (use --episode or --slot outside schedule)")
            return 0
        episode_id = jobs[0]["episode_id"]
    stage = run_long(
        episode_id,
        dry_run=True if args.dry_run else None,
        sample_sec=args.sample,
        private_test=args.private_test,
        stop_after=_parse_stop_after(args.stop_after),
    )
    print(f"{episode_id} -> {stage.value}")
    return 0


def _cmd_run_shorts(args: argparse.Namespace) -> int:
    from .pipeline import run_shorts

    stage = run_shorts(args.episode, dry_run=True if args.dry_run else None, private_test=args.private_test)
    print(f"{args.episode} -> {stage.value}")
    return 0


def _cmd_dry_run(args: argparse.Namespace) -> int:
    from .pipeline import run_long
    from .schedule import plan_due
    from .state import load_registry

    cfg = load_config(allow_example=True)
    reg = load_registry(cfg.get("paths.state", "state"))
    episode_id = args.episode
    if not episode_id:
        jobs = [j for j in plan_due(cfg, reg) if j["kind"] == "long"]
        if not jobs:
            # offline dry-run convenience: claim the next unclaimed long slot shape
            print("no long job due — pass --episode or run during a schedule slot")
            return 0
        episode_id = jobs[0]["episode_id"]
    stage = run_long(episode_id, dry_run=True, sample_sec=args.sample, private_test=True)
    print(f"DRY RUN {episode_id} -> {stage.value} (publishing skipped; resumes at publish on a real run)")
    return 0


def _cmd_youtube_oauth(_args: argparse.Namespace) -> int:
    from .config import load_env
    from .youtube.oauth import YouTubeCredentialsError, run_oauth_flow

    load_env()
    print("Opening a browser for YouTube consent (OAuth Desktop client required — SETUP.md §4).")
    try:
        token = run_oauth_flow()
    except YouTubeCredentialsError as exc:
        print(f"ERROR: {exc}")
        return 2
    except Exception as exc:
        print(f"ERROR: OAuth flow failed: {exc}")
        return 1
    print()
    print("Refresh token acquired. Copy this value:")
    print(token)
    print()
    print("Next: put it in .env (or GitHub Secrets) as YOUTUBE_REFRESH_TOKEN, then run `python -m app doctor --online`")
    return 0


def _cmd_snapshot(args: argparse.Namespace) -> int:
    from .config import load_env
    from .youtube.channel import channel_stats, format_snapshot
    from .youtube.oauth import YouTubeCredentialsError

    load_env()
    try:
        stats = channel_stats()
    except YouTubeCredentialsError as exc:
        print(f"ERROR: {exc}")
        return 2
    except Exception as exc:
        print(f"ERROR: channel snapshot failed: {exc}")
        return 1
    text = format_snapshot(stats)
    if args.json:
        print(json.dumps(stats, indent=2))
    else:
        print(text)
    if args.telegram:
        from . import telegram_client

        ok = telegram_client.send_message(text)
        print("telegram: sent" if ok else "telegram: FAILED")
        return 0 if ok else 1
    return 0


def _cmd_assets(args: argparse.Namespace) -> int:
    from .config import load_config
    from .render.assets import build_all

    cfg = load_config()
    root = cfg.get("paths.assets", "assets")
    counts = build_all(root)
    total = sum(counts.values())
    print(f"built {total} asset files under {root}/: {counts}")
    return 0


def _cmd_produce(args: argparse.Namespace) -> int:
    """Production entry: run every job due right now (long + shorts, in order).

    One failing job never blocks the rest (each is independently due); the
    final exit code is 1 if anything failed so CI reports red.
    """
    from .pipeline import run_long, run_shorts
    from .schedule import plan_due
    from .state import load_registry

    cfg = load_config(allow_example=True)
    reg = load_registry(cfg.get("paths.state", "state"))
    jobs = plan_due(cfg, reg)
    if not jobs:
        print("nothing due")
        return 0
    failed = 0
    for job in jobs:
        ep_id = job["episode_id"]
        kind = job["kind"]
        try:
            if kind == "long":
                stage = run_long(ep_id, dry_run=True if args.dry_run else None,
                                 sample_sec=args.sample, private_test=args.private_test)
            else:
                stage = run_shorts(ep_id, dry_run=True if args.dry_run else None,
                                   private_test=args.private_test)
            print(f"{kind} {ep_id} -> {stage.value}")
        except SystemExit as exc:
            failed += 1
            print(f"{kind} {ep_id} FAILED (exit {exc.code})")
    return 1 if failed else 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m app", description="Fernwood Friends automated content system")
    p.add_argument("--log-level", default=None, help="DEBUG/INFO/WARNING (default: $LOG_LEVEL or INFO)")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("init", help="create config/state/workspace scaffolding")
    sp.set_defaults(func=_cmd_init)

    sp = sub.add_parser("doctor", help="check environment, config and credentials")
    sp.add_argument("--online", action="store_true", help="also test network credentials")
    sp.set_defaults(func=_cmd_doctor)

    sp = sub.add_parser("status", help="list registered episodes and their stages")
    sp.set_defaults(func=_cmd_status)

    sp = sub.add_parser("schedule", help="show due jobs for now")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=_cmd_schedule)

    sp = sub.add_parser("run", help="run/resume the long-form pipeline for a due slot")
    sp.add_argument("--episode", help="episode id (default: next due slot)")
    sp.add_argument("--dry-run", action="store_true", help="stub publishing (private test)")
    sp.add_argument("--sample", type=float, help="render only first N seconds (QC sampling)")
    sp.add_argument("--private-test", action="store_true")
    sp.add_argument("--stop-after", help="stop after stage (e.g. SCRIPTED, AUDIO_READY)")
    sp.set_defaults(func=_cmd_run)

    sp = sub.add_parser("run-shorts", help="render+publish pending shorts for a published episode")
    sp.add_argument("--episode", required=True)
    sp.add_argument("--dry-run", action="store_true")
    sp.add_argument("--private-test", action="store_true")
    sp.set_defaults(func=_cmd_run_shorts)

    sp = sub.add_parser("dry-run", help="full pipeline with publishing stubbed")
    sp.add_argument("--episode")
    sp.add_argument("--sample", type=float)
    sp.set_defaults(func=_cmd_dry_run)

    sp = sub.add_parser("produce", help="run every job due now (production entry point)")
    sp.add_argument("--dry-run", action="store_true", help="build+QC everything, never publish")
    sp.add_argument("--sample", type=float, help="render only first N seconds (QC sampling)")
    sp.add_argument("--private-test", action="store_true")
    sp.set_defaults(func=_cmd_produce)

    sp = sub.add_parser("youtube-oauth", help="one-time YouTube OAuth flow")
    sp.set_defaults(func=_cmd_youtube_oauth)

    sp = sub.add_parser("snapshot", help="telegram channel stats snapshot")
    sp.add_argument("--json", action="store_true", help="print raw JSON stats")
    sp.add_argument("--telegram", action="store_true", help="also send the snapshot to Telegram")
    sp.set_defaults(func=_cmd_snapshot)

    sp = sub.add_parser("assets", help="build committed art assets (characters/locations/props)")
    sp.set_defaults(func=_cmd_assets)
    return p


def main(argv: list[str] | None = None) -> int:
    # Windows consoles default to cp1252; the report uses UTF-8 marks.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    parser = build_parser()
    args = parser.parse_args(argv)
    import os

    level = args.log_level or os.environ.get("LOG_LEVEL", "INFO")
    setup_logging(level, log_dir=ROOT / "logs")
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
