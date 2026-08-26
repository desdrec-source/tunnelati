import { getCollection } from "astro:content";

export async function GET() {
  const articles = (await getCollection("articles")).sort(
    (a, b) => b.data.pubDate.valueOf() - a.data.pubDate.valueOf()
  );

  const site = "https://tunnelati.com";

  const items = articles
    .map((a) => {
      const title = escapeXml(a.data.title);
      const desc = escapeXml(a.data.description);
      const link = `${site}/articles/${a.id}`;
      return `<item>
        <title>${title}</title>
        <link>${link}</link>
        <guid>${link}</guid>
        <pubDate>${a.data.pubDate.toUTCString()}</pubDate>
        <description>${desc}</description>
      </item>`;
    })
    .join("");

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Tunnelati</title>
    <link>${site}</link>
    <description>Independent high-signal coverage of official The Boring Company developments.</description>
    ${items}
  </channel>
</rss>`;

  return new Response(xml, {
    headers: { "Content-Type": "application/rss+xml; charset=utf-8" },
  });
}

function escapeXml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
