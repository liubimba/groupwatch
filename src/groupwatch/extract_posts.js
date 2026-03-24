() => {
  const permalink = /\/groups\/([^/?#]+)\/(?:posts|permalink)\/(\d+)/;
  const out = [];
  const seen = new Set();
  for (const article of document.querySelectorAll('[role="feed"] [role="article"], [role="feed"] > div')) {
    const link = [...article.querySelectorAll("a[href]")].find((a) => permalink.test(a.href));
    if (!link) continue;
    const [, , postId] = link.href.match(permalink);
    if (seen.has(postId)) continue;
    seen.add(postId);
    const authorNode = article.querySelector("h2 a, h3 a, h4 a, strong a");
    const textNode = article.querySelector(
      '[data-ad-preview="message"], [data-ad-comet-preview="message"], [dir="auto"]'
    );
    out.push({
      postId,
      url: link.href.split("?")[0],
      author: authorNode ? authorNode.innerText.trim() : "",
      text: textNode ? textNode.innerText.trim() : "",
    });
  }
  return out;
}
