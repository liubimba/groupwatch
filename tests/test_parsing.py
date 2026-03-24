from pathlib import Path

from groupwatch.facebook import chronological, looks_like_checkpoint
from groupwatch.groups import load_groups
from groupwatch.models import group_id_from_url


def test_group_id_comes_from_numeric_or_slug_urls():
    assert group_id_from_url("https://www.facebook.com/groups/123/") == "123"
    assert group_id_from_url("https://www.facebook.com/groups/some.slug?ref=x") == "some.slug"


def test_feed_is_opened_in_chronological_order():
    assert chronological("https://www.facebook.com/groups/1/") == "https://www.facebook.com/groups/1?sorting_setting=CHRONOLOGICAL"


def test_login_and_checkpoint_redirects_are_recognised():
    assert looks_like_checkpoint("https://www.facebook.com/checkpoint/1501092823525282/")
    assert looks_like_checkpoint("https://www.facebook.com/login/?next=x")
    assert not looks_like_checkpoint("https://www.facebook.com/groups/1")


def test_groups_table_lists_which_accounts_may_open_each_group():
    groups = load_groups(Path(__file__).parent.parent / "examples" / "groups.csv")
    assert len(groups) == 3
    assert groups[0].members == frozenset({"acc-1", "acc-2"})
    assert groups[2].members == frozenset()
