"""Editorial discovery v3.1: finite public-source search, quality gates and auditable ranking.

HN scores are discovery signals, not proof of audience demand or article accuracy.
An official GitHub release verifies that a release entry exists, not its claims.
No arbitrary webpage crawling, payment APIs, social scraping or fake trends.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
import html
import ipaddress
import math
import re
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
import requests

HN_API='https://hn.algolia.com/api/v1/search_by_date'
GITHUB_RELEASES={
    'comfyanonymous/ComfyUI':'outils open source',
    'huggingface/diffusers':'création vidéo IA',
}
QUERIES={
    'intelligence artificielle':('open source AI','AI agents'),
    'automatisation':('AI automation','AI agent'),
    'création vidéo IA':('AI video generation','video diffusion'),
    'outils open source':('open source AI','ComfyUI'),
}
TOPIC_TERMS={'ai','artificial','intelligence','agent','agents','automation',
             'automated','video','videos','diffusion','model','models','llm',
             'open','source','comfyui','wan','ltx','huggingface','github',
             'inference','generation','generative','image','images','workflow',
             'workflows','local','robot','robots','rendering'}
BOILERPLATE={'your','guide','ultimate','comprehensive','top','best','free','2026',
             'what','how','why','and','the','a','an','for','with','of','to','is',
             'about','new','from','in','on','du','des','les','le','la','un','une'}
OFFICIAL_DOMAINS={'github.com','huggingface.co','arxiv.org','openai.com',
                  'research.google','deepmind.google','ai.meta.com',
                  'developer.nvidia.com','docs.nvidia.com','blog.google',
                  'pytorch.org','github.blog'}
LOW_TRUST_SUFFIXES=('blogspot.com','tumblr.com','wordpress.com','substack.com')
BAD_DOMAINS={'medium.com','x.com','twitter.com','youtube.com','youtu.be',
             'linkedin.com','reddit.com','t.co'}
STOP={'a','an','and','the','for','how','with','this','that','from','about',
      'new','into','using','your','via','out','you','are','has','have','can',
      '2026','2025','2024','its','their','his','her','nous','les','des','une',
      'sur','avec','dans','pour','qui','est','ces','nous','vos','notre','leur'}

@dataclass(frozen=True)
class Topic:
    id:str
    headline:str
    url:str
    domain:str
    date:str
    theme:str
    signal:int=0
    origin:str='hacker_news'

def tokens(value:str)->set[str]:
    return {w for w in re.findall(r'[a-z0-9]{3,}', value.lower())
            if w not in STOP}

def similar_title(a:str,b:str)->float:
    aa,bb=tokens(a),tokens(b)
    return len(aa&bb)/len(aa|bb) if aa and bb else 0.

def canonical_url(url:str)->str:
    parts=urlsplit(url)
    pairs=[(k,v) for k,v in parse_qsl(parts.query,keep_blank_values=True)
           if not (k.startswith('utm_') or k in ('ref','source','fbclid','gclid'))]
    path=parts.path.rstrip('/') or '/'
    return urlunsplit(('https',parts.netloc.lower(),path,urlencode(pairs),''))

def safe_public_url(url:str)->bool:
    try:
        p=urlsplit(url)
        if p.scheme!='https' or p.username or p.password or p.port not in (None,443):
            return False
        domain=(p.hostname or '').lower().rstrip('.')
        if '.' not in domain or domain in ('localhost','metadata.google.internal'):
            return False
        if domain.endswith(('.local','.internal','.localhost','.test','.invalid')):
            return False
        try:
            ipaddress.ip_address(domain)
            return False
        except ValueError:
            pass
        if any(label in ('localhost','metadata') for label in domain.split('.')):
            return False
        return True
    except ValueError:
        return False

def normalize_topic(hit:dict,theme:str)->Topic|None:
    title=html.unescape(str(hit.get('title') or '').strip())
    url=str(hit.get('url') or '').strip()
    ident=str(hit.get('objectID') or '').strip()
    if not ident or not 12<=len(title)<=135 or not safe_public_url(url):
        return None
    domain=(urlsplit(url).hostname or '').lower().rstrip('.')
    if domain in BAD_DOMAINS or any(domain==s or domain.endswith('.'+s)
                                   for s in LOW_TRUST_SUFFIXES):
        return None
    points=max(0,int(hit.get('points') or 0))
    return Topic(ident,title,canonical_url(url),domain,
                 str(hit.get('created_at') or ''),theme,points)

def age_hours(value:str,now:datetime)->float|None:
    if not value:return None
    try:
        dt=datetime.fromisoformat(value.replace('Z','+00:00'))
        if dt.tzinfo is None:return None
        age=(now-dt.astimezone(timezone.utc)).total_seconds()/3600
        return age if age>=0 else None
    except (ValueError,OverflowError):
        return None

def evidence_gate(topic:Topic,now:datetime,max_hn_hours:int=120)->str:
    age=age_hours(topic.date,now)
    if age is None:return 'missing_or_future_timestamp'
    limit=14*24 if topic.origin=='github_release' else max_hn_hours
    if age>limit:return 'old_discovery_signal'
    if topic.domain in BAD_DOMAINS:return 'excluded_source_domain'
    ts=tokens(topic.headline)
    if topic.origin!='github_release' and len(ts&TOPIC_TERMS)<2:
        return 'generic_or_off_topic_headline'
    # Links to arbitrary sites discovered by HN remain unverified until human review.
    if topic.origin!='github_release' and topic.signal<4 and topic.domain not in OFFICIAL_DOMAINS:
        return 'insufficient_public_interest_signal'
    return ''

def rank(topic:Topic,now:datetime)->float:
    age=age_hours(topic.date,now) or 0
    relevance=min(4,len(tokens(topic.headline)&TOPIC_TERMS))
    fresh=max(0.,1.-age/(24*(14 if topic.origin=='github_release' else 6)))
    official=1.6 if topic.domain in OFFICIAL_DOMAINS else 0.
    # A release receives modest provenance credit, not invented social engagement.
    engagement=math.log1p(min(500,topic.signal))/math.log1p(500)
    informative=len(tokens(topic.headline)-BOILERPLATE)
    generic_penalty=1.8 if informative<4 and topic.origin!='github_release' else 0.
    return round(relevance*.75+fresh*2+official+engagement*1.1-generic_penalty,3)

def _historic_match(topic:Topic,history:list[dict])->str:
    cu=canonical_url(topic.url)
    for old in history[-450:]:
        old_url=old.get('source_url') or old.get('url') or ''
        if old_url and safe_public_url(old_url) and cu==canonical_url(old_url):
            return 'repeated_source_url'
        if similar_title(topic.headline,old.get('source_title') or old.get('title') or '')>=.78:
            return 'similar_previous_story'
    return ''

def select_topic(themes:list[str],seen:set[str],
                 session:requests.Session|None=None,
                 history:list[dict]|None=None,
                 now:datetime|None=None,
                 max_hn_hours:int=120)->tuple[Topic,dict]:
    now=now or datetime.now(timezone.utc)
    http=session or requests.Session()
    history=history or []
    audit={'algorithm':'VELORA_SCOUT_V3_1','discovery_signals':'HN recent story submissions and official GitHub releases',
           'not_verified_claims':True,'queried':[],'rejections':{},
           'candidates_examined':0,'candidates_eligible':0,'top_candidates':[]}
    candidates=[]
    visited=set()
    failures=[]
    for theme in themes:
        for phrase in QUERIES.get(theme,(theme,))[:2]:
            try:
                resp=http.get(HN_API,params={'query':phrase,'tags':'story','hitsPerPage':35},timeout=14)
                resp.raise_for_status()
                hits=resp.json().get('hits',[])
                if not isinstance(hits,list):continue
                audit['queried'].append({'provider':'hacker_news','theme':theme,'query':phrase,'hits':len(hits)})
                for hit in hits:
                    topic=normalize_topic(hit,theme)
                    if topic:
                        candidates.append(topic)
            except (requests.RequestException,ValueError,TypeError) as e:
                failures.append('hacker_news_'+type(e).__name__)
    # Independent official release feed. Only public GitHub repos; no token
    # and no assertion that an HN story is corroborated by a GitHub release.
    for name,theme in GITHUB_RELEASES.items():
        if theme not in themes:continue
        try:
            url='https://api.github.com/repos/'+name+'/releases'
            response=http.get(url,params={'per_page':5},timeout=12,
                              headers={'Accept':'application/vnd.github+json'})
            response.raise_for_status()
            releases=response.json()
            if not isinstance(releases,list):continue
            audit['queried'].append({'provider':'github_releases','repository':name,'hits':len(releases)})
            for release in releases:
                if release.get('draft') or release.get('prerelease'):continue
                url=release.get('html_url','')
                tag=str(release.get('tag_name') or '').strip()[:65]
                if not safe_public_url(url) or not tag:continue
                name_short=name.rsplit('/',1)[-1]
                title=f'{name_short} publishes official release {tag}'
                candidates.append(Topic('release:'+name+':'+tag,title,canonical_url(url),
                                        'github.com',str(release.get('published_at') or ''),
                                        theme,0,'github_release'))
        except (requests.RequestException,ValueError,TypeError) as e:
            failures.append('github_releases_'+type(e).__name__)
    scored=[]
    for topic in candidates:
        audit['candidates_examined']+=1
        reason=('previously_used_id' if topic.id in seen else
                'same_search_result' if (topic.id,canonical_url(topic.url)) in visited else
                evidence_gate(topic,now,max_hn_hours) or _historic_match(topic,history))
        visited.add((topic.id,canonical_url(topic.url)))
        if reason:
            audit['rejections'][reason]=audit['rejections'].get(reason,0)+1
            continue
        audit['candidates_eligible']+=1
        scored.append((rank(topic,now),topic))
    # Deduplicate candidate URLs and semantically repeated headlines across
    # *current* feeds too, so same story syndicated by two feeds ranks once.
    selected=[]
    for score,topic in sorted(scored,key=lambda x:(-x[0],x[1].id)):
        if any(canonical_url(topic.url)==canonical_url(t.url)
               or similar_title(topic.headline,t.headline)>=.78 for _,t in selected):
            audit['rejections']['duplicate_current_story']=audit['rejections'].get('duplicate_current_story',0)+1
            continue
        selected.append((score,topic))
    audit['top_candidates']=[{'headline':t.headline,'source_url':t.url,'theme':t.theme,
                              'origin':t.origin,'score':round(score,2),
                              'discovered_at':t.date}
                             for score,t in selected[:6]]
    if not selected:
        raise RuntimeError('No recent relevant sourced topic passed the editorial gate; '
                           'do not generate filler. Provider issues: '+','.join(sorted(set(failures)))[:100])
    chosen_score,chosen=selected[0]
    audit['chosen']={'headline':chosen.headline,'source_url':chosen.url,
                     'theme':chosen.theme,'origin':chosen.origin,
                     'score':round(chosen_score,2),'discovered_at':chosen.date}
    audit['gate']='SOURCE_DISCOVERY_ONLY_HUMAN_FACT_CHECK_REQUIRED'
    if failures:audit['source_warnings']=sorted(set(failures))
    return chosen,audit

def discover(themes:list[str],seen:set[str],
             session:requests.Session|None=None,**options)->Topic:
    """Backward compatible wrapper; production should call select_topic()."""
    return select_topic(themes,seen,session,**options)[0]
