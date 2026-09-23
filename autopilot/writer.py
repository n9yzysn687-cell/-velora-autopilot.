"""Cautious French editorial writing. External LLM is opt-in; deterministic fallback costs 0."""
import json
import os
import requests
from .source import Topic


def template_story(t: Topic, channel: str):
    head = t.headline.strip().rstrip('.!?')
    return {
        'title': f'IA : {head[:70]}',
        'description': (
            f'Un sujet à explorer : {head}. Source à consulter : {t.url}\n\n'
            'Cette vidéo propose un angle éditorial. Vérifiez les affirmations de la source '
            'avant toute diffusion publique.\n#IA #OpenSource #Shorts'
        ),
        'script': (
            f'Un sujet à suivre : « {head[:46]} ». '
            'Qu’est-ce que cela change en pratique ? '
            'On examine la source, on teste et on sépare les faits des promesses. '
            f'Sur {channel}, place aux outils et aux résultats vérifiables. '
            'La source est en description. Abonne-toi pour la suite.'
        ),
        'hook': 'Une idée IA à vérifier, plutôt qu’une promesse facile.',
        'verified': False,
        'source_url': t.url,
        'source_title': t.headline,
    }


def generate_story(t: Topic, channel: str, language: str, backend: str, session: requests.Session | None = None):
    base = template_story(t, channel)
    if backend != 'gemini':
        return base
    if os.environ.get('GEMINI_FREE_ONLY_CONFIRMED') != 'true':
        raise RuntimeError('Gemini key might bill; only enable after confirming a free-only account. Default template remains free.')
    key = os.environ.get('GEMINI_API_KEY', '').strip()
    if not key:
        raise RuntimeError('Script Gemini selected but GEMINI_API_KEY is missing. No billed fallback.')
    model = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash-lite')
    prompt = (
        'Create original short-form editorial writing in French as JSON with keys title, hook, script, description. '
        'Length: 65-85 spoken words. Do not claim facts beyond the SINGLE provided headline and URL. '
        'Clearly distinguish questions, hypotheses and facts. Include the exact source URL in description. '
        'No misleading performance figures, no invented quotes, no copy-pasted source article. '
        f'CHANNEL={channel}; LANGUAGE={language}; HEADLINE={t.headline}; SOURCE_URL={t.url}; SOURCE_SITE={t.domain}'
    )
    http = session or requests.Session()
    resp = http.post(
        f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
        headers={'x-goog-api-key': key},
        json={'contents': [{'parts': [{'text': prompt}]}],
              'generationConfig': {'responseMimeType': 'application/json', 'temperature': 0.55}},
        timeout=45,
    )
    if resp.status_code == 429:
        raise RuntimeError('Free LLM quota exhausted; stopped. No paid fallback.')
    resp.raise_for_status()
    text = resp.json()['candidates'][0]['content']['parts'][0]['text']
    data = json.loads(text)
    for field in ('title', 'hook', 'script', 'description'):
        if not isinstance(data.get(field), str) or not data[field].strip():
            raise RuntimeError(f'LLM response missing {field}; production stopped.')
    data['title'] = data['title'][:98]
    data['script'] = data['script'][:3000]
    data['description'] = data['description'][:4500] + f'\nSource: {t.url}'
    data.update(source_url=t.url, source_title=t.headline, verified=False)
    return data
