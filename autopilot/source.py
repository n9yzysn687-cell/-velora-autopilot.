"""Public, low-cost discovery with explicit source provenance and de-duplication."""
from dataclasses import dataclass
import html
from urllib.parse import urlsplit
import requests

API = 'https://hn.algolia.com/api/v1/search_by_date'

@dataclass(frozen=True)
class Topic:
    id: str
    headline: str
    url: str
    domain: str
    date: str
    theme: str


def normalize_topic(hit: dict, theme: str) -> Topic | None:
    title = html.unescape(str(hit.get('title') or '').strip())
    url = str(hit.get('url') or '').strip()
    ident = str(hit.get('objectID') or '').strip()
    if not ident or not (12 <= len(title) <= 135):
        return None
    if not url.startswith('https://'):
        return None
    domain = urlsplit(url).hostname or ''
    if not domain or domain.endswith('.local'):
        return None
    return Topic(ident, title, url, domain, str(hit.get('created_at') or ''), theme)


def discover(themes: list[str], seen: set[str], session: requests.Session | None = None) -> Topic:
    http = session or requests.Session()
    # Explore broad and topic-specific searches, without claiming they are YouTube trends.
    for theme in themes:
        response = http.get(API, params={
            'query': theme, 'tags': 'story', 'hitsPerPage': 30,
        }, timeout=18)
        response.raise_for_status()
        for hit in response.json().get('hits', []):
            topic = normalize_topic(hit, theme)
            if topic and topic.id not in seen:
                return topic
    raise RuntimeError('No fresh, cited candidate found; no fabricated news video produced.')
