"""Read-only YouTube Analytics feedback. No raw metrics or OAuth credentials are committed.

A run analyses only manually mapped, published videos after their first seven full
UTC days have settled. It compares like-aged 7-day windows and writes only a
minimal, aggregate production preference to the public repository.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import requests

YT_TOKEN = 'https://oauth2.googleapis.com/token'
YT_REPORT = 'https://youtubeanalytics.googleapis.com/v2/reports'
VIDEO_ID = re.compile(r'^[A-Za-z0-9_-]{11}$')
METRICS = 'views,averageViewPercentage,likes,subscribersGained'
OPTIONS = {'question', 'direct'}

def feedback_status(status: str, **kwargs) -> dict:
    return {'status': status, 'as_of': date.today().isoformat(), **kwargs}

def can_collect(env: dict) -> bool:
    return all(env.get(s, '').strip() for s in
               ('YT_CLIENT_ID', 'YT_CLIENT_SECRET', 'YT_REFRESH_TOKEN'))

def token_from_refresh(env: dict, http: requests.Session) -> str:
    response = http.post(
        YT_TOKEN,
        data={'client_id': env['YT_CLIENT_ID'],
              'client_secret': env['YT_CLIENT_SECRET'],
              'refresh_token': env['YT_REFRESH_TOKEN'],
              'grant_type': 'refresh_token'},
        timeout=20)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data.get('access_token'), str):
        raise RuntimeError('YouTube OAuth token response missing access_token')
    return data['access_token']

def validate_mapping(raw: dict, today: date, themes: list[str]) -> list[dict]:
    eligible = []
    items = raw.get('videos', [])
    if not isinstance(items, list) or len(items) > 200:
        raise ValueError('data/published.json videos must be a list of at most 200')
    seen = set()
    for entry in items:
        if not isinstance(entry, dict):
            continue
        vid = entry.get('video_id', '')
        if not isinstance(vid, str) or not VIDEO_ID.fullmatch(vid) or vid in seen:
            continue
        seen.add(vid)
        try:
            published = date.fromisoformat(entry.get('published_at', ''))
        except (TypeError, ValueError):
            continue
        if (today - published).days < 9:
            continue
        theme, variant = entry.get('theme'), entry.get('variant')
        if theme not in themes or variant not in OPTIONS:
            continue
        eligible.append({'video_id': vid, 'published': published,
                         'theme': theme, 'variant': variant})
    return eligible[:60]

def fetch_first_week(entry: dict, token: str, http: requests.Session) -> dict | None:
    first = entry['published']
    # Full first week, identical observation age. 2-day lag for API finality.
    params = {'ids': 'channel==MINE', 'startDate': first.isoformat(),
              'endDate': (first + timedelta(days=6)).isoformat(),
              'metrics': METRICS, 'filters': 'video==' + entry['video_id']}
    response = http.get(YT_REPORT, params=params,
                        headers={'Authorization': 'Bearer ' + token},
                        timeout=25)
    response.raise_for_status()
    data = response.json()
    rows = data.get('rows', [])
    if not rows:
        return None
    header = [v['name'] for v in data.get('columnHeaders', [])]
    row = dict(zip(header, rows[0]))
    return {key: float(row[key]) for key in METRICS.split(',')}

def score(row: dict) -> float:
    views = max(1., row['views'])
    # Guard replay loops and outlier subscriber rates. Never treat as a proof
    # of causation or as a prediction of future YouTube performance.
    retained = min(140., max(0., row['averageViewPercentage'])) / 140.
    likes = min(.1, max(0., row['likes']) / views) / .1
    subscribers = min(.03, max(0., row['subscribersGained']) / views) / .03
    return .7 * retained + .2 * subscribers + .1 * likes

def aggregate(rows: list[tuple[dict, dict]], field: str, min_views: int,
              min_videos: int) -> dict[str, float]:
    groups = defaultdict(list)
    for meta, metric in rows:
        if metric['views'] >= min_views:
            groups[meta[field]].append(score(metric))
    return {name: sum(values)/len(values) for name, values in groups.items()
            if len(values) >= min_videos}

def learn(root: Path, config: dict, env: dict | None = None,
          session: requests.Session | None = None,
          today: date | None = None) -> dict:
    env = os.environ if env is None else env
    today = date.today() if today is None else today
    path = root / 'data' / 'published.json'
    if not path.exists():
        return feedback_status('awaiting_published_video_mapping')
    raw = json.loads(path.read_text(encoding='utf8'))
    entries = validate_mapping(raw, today, config.get('themes', []))
    if not entries:
        return feedback_status('awaiting_mature_published_videos')
    if not can_collect(env):
        return feedback_status('awaiting_youtube_readonly_oauth')
    http = session or requests.Session()
    token = token_from_refresh(env, http)
    rows = []
    for entry in entries:
        result = fetch_first_week(entry, token, http)
        if result is not None:
            rows.append((entry, result))
    min_views = max(50, int(config.get('min_video_views', 100)))
    min_videos = max(3, int(config.get('min_videos_per_option', 3)))
    gap = max(.06, float(config.get('min_feedback_lift', .08)))
    decision = feedback_status('insufficient_comparable_data', eligible=len(entries),
                               measured=len(rows))
    for field, target in [('theme', 'preferred_theme'), ('variant', 'preferred_variant')]:
        options = aggregate(rows, field, min_views, min_videos)
        if len(options) < 2:
            continue
        ordering = sorted(options.items(), key=lambda x: (-x[1], x[0]))
        lead, runner = ordering[0], ordering[1]
        if lead[1] - runner[1] >= gap:
            decision[target] = lead[0]
    if 'preferred_theme' in decision or 'preferred_variant' in decision:
        decision['status'] = 'experimental_preference'
    elif len(rows) >= min_videos*2:
        decision['status'] = 'no_clear_signal'
    return decision

def run_feedback(root: Path, config: dict) -> dict:
    try:
        report = learn(root, config)
    except (requests.RequestException, ValueError, KeyError, TypeError, RuntimeError) as e:
        # No auth errors or raw analytics ever enter the public git repository.
        print('Analytics ingestion unavailable:', type(e).__name__, flush=True)
        report = feedback_status('analytics_unavailable_no_change')
    out = root/'state'/'feedback.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n',
                   encoding='utf8')
    print('VELORA feedback:', report, flush=True)
    return report

if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    run_feedback(root, json.loads((root/'config.json').read_text(encoding='utf8')))
