"""A bounded scheduled iteration; GitHub Actions supplies the recurring loop.

This process never loops indefinitely or spends credits. One invocation creates
at most one Shorts draft. On success the state file is committed by CI.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import sys
import traceback
from .source import Topic,select_topic
from .writer import generate_story
from .render import render
from .director import make_storyboard
from .free_gpu import generate_free_clip


def editorial_plan(config:dict, feedback:dict, day:datetime)->tuple[list[str],str]:
    themes=list(config['themes'])
    if not themes:
        raise ValueError('At least one editorial theme required')
    tick=day.date().toordinal()
    start=tick % len(themes)
    exploratory=themes[start:]+themes[:start]
    preferred=feedback.get('preferred_theme') if feedback.get('status')=='experimental_preference' else None
    if preferred in themes and tick%3!=0:
        themes=[preferred]+[t for t in exploratory if t!=preferred]
    else:
        themes=exploratory
    preferred_variant=feedback.get('preferred_variant') if feedback.get('status')=='experimental_preference' else None
    variant=preferred_variant if preferred_variant in ('direct','question') and tick%3!=0 else ('question' if tick%2==0 else 'direct')
    return themes,variant

ROOT=Path(__file__).resolve().parents[1]

def read_json(path:Path,default):
    try:
        return json.loads(path.read_text(encoding='utf8'))
    except FileNotFoundError:
        return default

def safe_write(path:Path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    temp.replace(path)

def run(root:Path=ROOT, fixture:Path|None=None) -> dict:
    config=read_json(root/'config.json',None)
    if config is None:
        raise RuntimeError('Missing config.json')
    daily=int(config.get('shorts_per_day',1))
    spend=float(config.get('max_daily_paid_eur',0))
    if daily not in range(0,5) or spend < 0:
        raise ValueError('Invalid limits; shorts_per_day must be 0-4, budget >=0.')
    if spend>0:
        # Payment backend is deliberately absent in this no-surprise-cost edition.
        raise RuntimeError('Paid rendering is deliberately disabled; set max_daily_paid_eur to 0.')
    path=root/'state'/'state.json'
    state=read_json(path,{'seen_ids':[], 'runs':{}})
    day=datetime.now(timezone.utc).date().isoformat()
    used=int(state.get('runs',{}).get(day,0))
    if daily==0 or used>=daily:
        state.update(last_status='daily_limit_reached',last_error='')
        safe_write(path,state)
        return {'status':'daily_limit_reached','count_today':used}
    feedback=read_json(root/'state'/'feedback.json',{})
    themes,variant=editorial_plan(config,feedback,datetime.now(timezone.utc))
    failures=state.get('failed_topics',{})
    ledger_file=root/'state'/'productions.json'
    ledger=read_json(ledger_file,{'productions':[]})
    history=list(ledger.get('productions',[]))
    if state.get('last_source'):
        history.append({'source_url':state['last_source'],
                        'source_title':state.get('last_topic','')})
    seen=set(state.get('seen_ids',[])) | {ident for ident,c in failures.items() if c>=2}
    try:
        if fixture:
            obj=read_json(fixture,None)
            if not obj:
                raise RuntimeError('Missing offline fixture')
            topic=Topic(**obj)
            research={'algorithm':'OFFLINE_FIXTURE_FOR_TESTS','chosen':{'headline':topic.headline,
                       'source_url':topic.url},'gate':'HUMAN_FACT_CHECK_REQUIRED'}
        else:
            topic,research=select_topic(themes,seen,history=history,
                max_hn_hours=int(config.get('research',{}).get('max_hn_age_hours',120)))
        if topic.id in seen:
            raise RuntimeError('Topic already processed, skipping safely.')
        story=generate_story(topic,config['channel_name'],config.get('language','fr'),config['providers']['script'],variant=variant)
        stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        out=root/'output'/stamp
        out.mkdir(parents=True,exist_ok=True)
        safe_write(out/'story.json',story)
        storyboard=make_storyboard(story,config['channel_name'])
        safe_write(out/'research.json',research)
        gpu_clip=None
        if config['providers'].get('video')=='hf_zerogpu':
            gpu_prompt=(f"Cinematic editorial documentary, {topic.headline}. "
                        'Abstract visualization, photorealistic lighting and deliberate camera movement, '
                        'no captions, no simulated dashboards, no fabricated visible logos, 9:16.')
            gpu_clip=generate_free_clip(config['providers'],gpu_prompt,out/'zerogpu_scene.mp4')
        elif config['providers'].get('video')!='motion_design':
            raise RuntimeError('Unrecognized video engine. Paid API fallback is forbidden.')
        video=render(story,config['channel_name'],out,config.get('max_seconds',29),config.get('language','fr'),gpu_clip,storyboard)
        # Only mark the topic as used once an MP4 passes QA.
        state.setdefault('seen_ids',[]).append(topic.id)
        state['seen_ids']=state['seen_ids'][-1000:]
        state.setdefault('runs',{})[day]=used+1
        state['runs']={k:v for k,v in state['runs'].items() if k>=day[:7]}
        state.update(last_status='draft_ready',last_topic=topic.headline,last_source=topic.url,
                     last_research_score=research.get('chosen',{}).get('score'),
                     last_research_origin=topic.origin,
                     last_error='',last_time=stamp)
        safe_write(path,state)
        manifest={
          'channel':config['channel_name'],'status':'DRAFT_REVIEW_REQUIRED',
          'public_youtube_upload':False, 'paid_video_generation':False,
          'source':{'title':topic.headline,'url':topic.url,'date':topic.date,
                    'timestamp_type':'official_release_published_at' if topic.origin=='github_release' else 'hacker_news_submission_at',
                    'provenance':topic.origin,'research_quality_score':research.get('chosen',{}).get('score')},
          'research':{'report_file':'research.json','fact_check_required':True,
                      'candidates_examined':research.get('candidates_examined'),
                      'candidates_eligible':research.get('candidates_eligible')},
          'editorial_experiment':{'theme':topic.theme,'variant':variant,'feedback_status':feedback.get('status','not_connected')},
          'script_verified':False,'media_rights_checked':False,'mp4_watched':False,
          'production':video,'story':story,
          'director':{'version':'V3.2','storyboard_file':'storyboard.json',
                      'scene_count':video.get('scene_count',storyboard['scene_count']),
                      'scene_layouts':[s['layout'] for s in storyboard['scenes']],
                      'captions':'verbatim script excerpts allocated per scene, timing approximate',
                      'film_fact_checked':False},
          'visual_note':('One actual authenticated ZeroGPU scene plus motion design.' if gpu_clip else 'Stylized graphic motion design. Not Seedance/Wan or photorealistic AI clips.'),
          'next':'Watch the video, verify sources and rights, then publish manually or configure an authorized uploader.'
        }
        safe_write(out/'manifest.json',manifest)
        ledger.setdefault('productions',[]).append({'id':stamp,'source_url':topic.url,
            'source_title':topic.headline,'theme':topic.theme,'variant':variant,
            'source_type':topic.origin,
            'research_score':research.get('chosen',{}).get('score'),
            'script_type':config['providers']['script'],
            'video_engine':config['providers'].get('video'),
            'duration_seconds':video.get('duration_seconds'),
            'director_version':'V3.2',
            'scene_count':storyboard['scene_count'],
            'layout_sequence':[x['layout'] for x in storyboard['scenes']],
            'status':'DRAFT_REVIEW_REQUIRED','created_at':stamp})
        ledger['productions']=ledger['productions'][-200:]
        safe_write(ledger_file,ledger)
        result={'status':'draft_ready','video':video['video'],
                'manifest':str(out/'manifest.json'),
                'research_report':str(out/'research.json'),
                'storyboard':str(out/'storyboard.json'),
                'topic':topic.headline,
                'source':topic.url,'quality_gate':research.get('gate','HUMAN_FACT_CHECK_REQUIRED')}
        safe_write(root/'state'/'last_run.json',result)
        print(json.dumps(result,ensure_ascii=False),flush=True)
        return result
    except Exception as exc:
        err=f'{type(exc).__name__}: {str(exc)[:380]}'
        if 'topic' in locals():
            failures[topic.id]=failures.get(topic.id,0)+1
            state['failed_topics']=failures
        state.update(last_status='paused_after_error',last_error=err)
        safe_write(path,state)
        safe_write(root/'state'/'last_run.json',{'status':'paused_after_error','message':err})
        print('AUTOPILOT PAUSED:',err,file=sys.stderr)
        return {'status':'paused_after_error','message':err}

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--root',type=Path,default=ROOT)
    p.add_argument('--fixture',type=Path,default=None,help='offline fixture, tests only')
    args=p.parse_args()
    r=run(args.root,args.fixture)
    sys.exit(0 if r['status'] in ('daily_limit_reached','draft_ready') else 1)
