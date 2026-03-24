import pytest

playwright = pytest.importorskip("playwright.async_api")

from groupwatch.facebook import EXTRACT_POSTS

FEED = """
<div role="feed">
  <div role="article">
    <h3><a href="/user/1">Анна К.</a></h3>
    <div data-ad-comet-preview="message">Сдаётся студия у метро</div>
    <a href="https://www.facebook.com/groups/123/posts/555?__cft__=x">2 ч</a>
  </div>
  <div role="article">
    <strong><a href="/user/2">Игорь П.</a></strong>
    <div data-ad-preview="message">Продаю велосипед</div>
    <a href="https://www.facebook.com/groups/123/permalink/777/">1 д</a>
    <a href="https://www.facebook.com/groups/123/permalink/777/?comment_id=9">reply</a>
  </div>
  <div role="article"><a href="/groups/123/about">no post link</a></div>
</div>
"""


async def test_feed_articles_become_posts_keyed_by_permalink_id():
    async with playwright.async_playwright() as pw:
        try:
            browser = await pw.chromium.launch()
        except Exception as e:
            pytest.skip(f"chromium unavailable: {e}")
        page = await browser.new_page()
        await page.set_content(FEED)
        posts = await page.evaluate(EXTRACT_POSTS)
        await browser.close()
    assert [(p["postId"], p["author"], p["text"]) for p in posts] == [
        ("555", "Анна К.", "Сдаётся студия у метро"),
        ("777", "Игорь П.", "Продаю велосипед"),
    ]
    assert posts[0]["url"] == "https://www.facebook.com/groups/123/posts/555"
