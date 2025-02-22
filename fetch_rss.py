import json
import feedparser
from datetime import datetime

def load_feeds_from_json(file_path="feeds.json"):
    """Load the JSON file with the RSS feeds."""
    with open(file_path, "r", encoding="utf-8") as file:
        data = json.load(file)
    return data.get("feeds", [])

def fetch_rss_feed(feed_url, start_date=None):
    """Gets the RSS feed from the given URL and prints the titles, links, and dates of the articles."""
    feed = feedparser.parse(feed_url)

    if 'entries' in feed:
        for entry in feed.entries:
            published_date = datetime(*entry.published_parsed[:6])
            if start_date is None or published_date >= start_date:
                print(f"Title: {entry.title}")
                print(f"Link: {entry.link}")
                print(f"Date: {published_date.strftime('%Y-%m-%d %H:%M:%S')}")
                print("-" * 40)
    else:
        print("No articles found in the feed.")

def main(start_date_str=None):
    rss_urls = load_feeds_from_json()
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d") if start_date_str else None

    for rss_url in rss_urls:
        fetch_rss_feed(rss_url, start_date)

if __name__ == "__main__":
    import sys
    start_date_arg = sys.argv[1] if len(sys.argv) > 1 else None
    main(start_date_arg)
