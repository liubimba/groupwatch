from __future__ import annotations

import argparse
import asyncio
from contextlib import AsyncExitStack
from pathlib import Path

from rich.console import Console
from rich.live import Live

from .accounts import AccountPool
from .dashboard import pass_hours, render
from .groups import load_groups
from .models import Group
from .runner import RoundStats, Runner
from .simulated import SimulatedCollector, demo_groups
from .sinks import CsvSink, GoogleSheetSink, Sink
from .store import Store

REAL_VISIT_SECONDS = 15.0


async def watch(runner: Runner, groups: list[Group], console: Console) -> RoundStats:
    stats = RoundStats(total=len(groups))
    task = asyncio.create_task(runner.run_round(groups, stats))
    with Live(render(stats, runner.pool), console=console, refresh_per_second=8) as live:
        while not task.done():
            await asyncio.sleep(0.125)
            live.update(render(stats, runner.pool))
        live.update(render(stats, runner.pool))
    return await task


def summary(console: Console, stats: RoundStats, out: Path, accounts: int, args) -> None:
    console.print(
        f"\n[bold]Pass finished:[/] {stats.done} groups read, {stats.failed} failed, "
        f"{stats.new} new posts, {stats.seen - stats.new} duplicates dropped by post id."
    )
    console.print(f"Results: {out / 'posts.csv'}, errors: {out / 'errors.csv'}, state: {out / 'groupwatch.db'}")
    for total in (100, 3000):
        hours = pass_hours(total, accounts, args.real_gap, REAL_VISIT_SECONDS, args.hourly_limit)
        console.print(
            f"At live pacing ({args.real_gap:.0f}s gap, ~{REAL_VISIT_SECONDS:.0f}s per group, "
            f"{args.hourly_limit}/h cap, {accounts} accounts) one pass over {total} groups takes "
            f"[bold]{hours:.1f} h[/]."
        )


async def demo(args) -> None:
    console = Console(record=bool(args.svg), width=110 if args.svg else None)
    names = [f"acc-{n}" for n in range(1, args.accounts + 1)]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    store = Store(out / "groupwatch.db")
    pool = AccountPool(names, min_gap=args.real_gap * args.time_scale, hourly_limit=10**6)
    collector = SimulatedCollector(seed=args.seed, checkpoint_account=names[-1], checkpoint_after=args.groups // 6)
    runner = Runner(pool, collector, store, [CsvSink(out)])
    groups = demo_groups(args.groups)
    for n in range(1, args.passes + 1):
        console.rule(f"pass {n} of {args.passes}")
        stats = await watch(runner, groups, console)
    summary(console, stats, out, len(names), args)
    store.close()
    if args.svg:
        console.save_svg(args.svg, title="groupwatch demo")


async def run(args) -> None:
    console = Console()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    groups = load_groups(Path(args.groups))
    names = [n.strip() for n in args.accounts.split(",") if n.strip()]
    store = Store(out / "groupwatch.db")
    sinks: list[Sink] = [CsvSink(out)]
    if args.sheet:
        sinks.append(GoogleSheetSink(args.sheet, Path(args.credentials)))
    from .facebook import FacebookCollector

    async with AsyncExitStack() as stack:
        collector = await stack.enter_async_context(
            FacebookCollector(Path(args.profiles), headless=args.headless, scrolls=args.scrolls)
        )
        pool = AccountPool(names, min_gap=args.real_gap, hourly_limit=args.hourly_limit)
        runner = Runner(pool, collector, store, sinks)
        while True:
            stats = await watch(runner, groups, console)
            summary(console, stats, out, pool.active() or 1, args)
            if not args.loop or pool.active() == 0:
                break
            await asyncio.sleep(args.loop)
    store.close()


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="groupwatch")
    sub = p.add_subparsers(dest="command", required=True)

    def pacing(cmd: argparse.ArgumentParser) -> None:
        cmd.add_argument("--real-gap", type=float, default=40.0, help="seconds between two visits by one account")
        cmd.add_argument("--hourly-limit", type=int, default=60, help="visits per account per hour")
        cmd.add_argument("--out", default="out")

    d = sub.add_parser("demo", help="run the whole pipeline against simulated groups, offline")
    d.add_argument("--groups", type=int, default=100)
    d.add_argument("--accounts", type=int, default=3)
    d.add_argument("--time-scale", type=float, default=0.005, help="live gap multiplier for the demo")
    d.add_argument("--seed", type=int, default=7)
    d.add_argument("--passes", type=int, default=2, help="later passes show that seen posts are dropped")
    d.add_argument("--svg", help="save the final screen as SVG")
    pacing(d)

    r = sub.add_parser("run", help="watch real groups through logged-in browser sessions")
    r.add_argument("--groups", required=True, help="CSV with url,name,accounts columns")
    r.add_argument("--accounts", required=True, help="comma-separated profile names")
    r.add_argument("--profiles", default="profiles")
    r.add_argument("--sheet", help="Google Sheet key to append posts and errors to")
    r.add_argument("--credentials", default="credentials.json", help="service account JSON")
    r.add_argument("--scrolls", type=int, default=3)
    r.add_argument("--headless", action="store_true")
    r.add_argument("--loop", type=float, default=0, help="seconds to wait between passes, 0 runs once")
    pacing(r)

    lg = sub.add_parser("login", help="open a browser profile to log in by hand, once")
    lg.add_argument("account")
    lg.add_argument("--profiles", default="profiles")
    return p


def main() -> None:
    args = parser().parse_args()
    if args.command == "demo":
        asyncio.run(demo(args))
    elif args.command == "run":
        asyncio.run(run(args))
    else:
        from .facebook import login

        asyncio.run(login(Path(args.profiles), args.account))
