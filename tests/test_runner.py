from datetime import datetime

from groupwatch.accounts import AccountPool
from groupwatch.models import Checkpoint, Group, GroupUnavailable, Post
from groupwatch.runner import Runner
from groupwatch.store import Store


def post(group, n):
    return Post(str(n), group.id, group.title, "author", f"text {n}", f"{group.url}/posts/{n}", datetime.now())


class Recorder:
    def __init__(self):
        self.posts = []
        self.errors = []

    def write_posts(self, posts):
        self.posts.extend(posts)

    def write_error(self, error):
        self.errors.append(error)


class Scripted:
    def __init__(self, behaviour):
        self.behaviour = behaviour
        self.visits = []

    async def fetch(self, group, account):
        self.visits.append((group.id, account))
        return self.behaviour(group, account, len(self.visits))


def make(behaviour, accounts=("a", "b"), tmp_path=None):
    collector = Scripted(behaviour)
    sink = Recorder()
    pool = AccountPool(accounts, min_gap=0, hourly_limit=1000, jitter=lambda: 1.0)
    runner = Runner(pool, collector, Store(tmp_path / "db.sqlite"), [sink], max_attempts=2)
    return runner, collector, sink


GROUPS = [Group(f"https://www.facebook.com/groups/{n}") for n in range(1, 6)]


async def test_every_group_is_visited_and_posts_reach_the_sink(tmp_path):
    runner, collector, sink = make(lambda g, a, i: [post(g, g.id)], tmp_path=tmp_path)
    stats = await runner.run_round(GROUPS)
    assert stats.done == 5
    assert sorted(p.post_id for p in sink.posts) == ["1", "2", "3", "4", "5"]


async def test_posts_already_seen_in_an_earlier_pass_are_not_written_twice(tmp_path):
    runner, _, sink = make(lambda g, a, i: [post(g, g.id)], tmp_path=tmp_path)
    await runner.run_round(GROUPS)
    second = await runner.run_round(GROUPS)
    assert len(sink.posts) == 5
    assert second.new == 0 and second.seen == 5


async def test_checkpoint_pauses_the_account_and_hands_the_group_to_another(tmp_path):
    def behaviour(group, account, _):
        if account == "a":
            raise Checkpoint("confirm identity")
        return [post(group, group.id)]

    runner, collector, sink = make(behaviour, tmp_path=tmp_path)
    stats = await runner.run_round(GROUPS)
    assert stats.done == 5
    assert runner.pool.accounts["a"].blocked == "checkpoint"
    assert sink.errors[0].detail == "confirm identity"
    assert sum(1 for _, acc in collector.visits if acc == "a") == 1
    assert [e.kind for e in sink.errors] == ["checkpoint"]


async def test_group_that_never_opens_is_retried_then_journaled(tmp_path):
    def behaviour(group, account, _):
        if group.id == "3":
            raise GroupUnavailable("private")
        return []

    runner, collector, sink = make(behaviour, tmp_path=tmp_path)
    stats = await runner.run_round(GROUPS)
    assert [g for g, _ in collector.visits].count("3") == 2
    assert stats.failed == 1 and stats.done == 4
    assert [(e.group_id, e.kind) for e in sink.errors] == [("3", "GroupUnavailable")]


async def test_round_ends_with_journal_entries_when_every_session_is_checkpointed(tmp_path):
    def behaviour(group, account, _):
        raise Checkpoint("blocked")

    runner, _, sink = make(behaviour, tmp_path=tmp_path)
    stats = await runner.run_round(GROUPS)
    assert stats.failed == 5
    assert runner.pool.active() == 0
    assert {e.kind for e in sink.errors} == {"checkpoint", "no_account"}
