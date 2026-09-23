"""YouTube delivery v3.3: OAuth channel lock, review gates and idempotent uploads.

No OAuth keys, private video IDs, or detailed analytics enter the public git
repository. Only an explicitly enabled workflow may upload. Public release is
a separate opt-in limited to original, short, source-constrained release videos.
"""
from __future__ import annotations
import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit
import requests
from .feedback import token_from_refresh

API='https://www.googleapis.com/youtube/v3'
UPLOAD='https://www.googleapis.com/upload/youtube/v3/videos'
VIDEO_ID=re.compile(r'^[A-Za-z0-9_-]{11}$')
CHANNEL_ID=re.compile(r'^UC[A-Za-z0-9_-]{22}$')
PUBLIC_RELEASE_PROVIDERS={'github_release'}
REQUIRED_SCOPES=(
 'https://www.googleapis.com/auth/youtube.upload',
 'https://www.googleapis.com/auth/youtube.readonly',
 'https://www.googleapis.com/auth/yt-analytics.readonly',
)

def enabled(config:dict)->bool:
    return config.get('youtube',{}).get('upload_enabled') is True

def check_oauth_settings(config:dict,env:dict)->dict:
    if not enabled(config):return {'status':'upload_disabled'}
    if not all(env.get(k,'').strip() for k in
               ('YT_CLIENT_ID','YT_CLIENT_SECRET','YT_REFRESH_TOKEN')):
        return {'status':'awaiting_owner_oauth_secrets'}
    expected=env.get('YT_CHANNEL_ID','').strip()
    if not CHANNEL_ID.fullmatch(expected):
        return {'status':'awaiting_owner_channel_id'}
    return {'status':'configured_not_yet_verified'}

def expected_channel(env:dict)->str:
    value=env.get('YT_CHANNEL_ID','').strip()
    if not CHANNEL_ID.fullmatch(value):
        raise RuntimeError('YT_CHANNEL_ID missing or invalid; refusing upload')
    return value

def channel_info(access_token:str,http:requests.Session)->dict:
    r=http.get(API+'/channels',
        params={'part':'id,snippet,contentDetails','mine':'true','maxResults':5},
        headers={'Authorization':'Bearer '+access_token},timeout=25)
    r.raise_for_status()
    items=r.json().get('items',[])
    if len(items)!=1:
        raise RuntimeError('Expected exactly one authorized YouTube channel; stop and select owner account')
    ch=items[0]
    if not CHANNEL_ID.fullmatch(ch.get('id','')):
        raise RuntimeError('Authorized channel returned no valid ID')
    return ch

def make_marker(production:dict)->str:
    identifier=production.get('id','')
    if not re.fullmatch(r'[0-9]{8}T[0-9]{6}Z',identifier):
        raise RuntimeError('Production ID not issued by VELORA')
    return 'VELORA-ID: '+identifier

def verify_mp4(path:Path,meta:dict)->None:
    if not path.is_file() or path.stat().st_size<50_000:
        raise RuntimeError('Video missing or too small')
    import subprocess
    p=subprocess.run(['ffprobe','-v','error','-show_entries',
          'format=duration:stream=codec_name,width,height,codec_type',
          '-of','json',str(path)],capture_output=True,text=True,
          check=True,timeout=25)
    data=json.loads(p.stdout)
    duration=float(data['format']['duration'])
    video=next((s for s in data['streams'] if s.get('codec_type')=='video'),None)
    audio=next((s for s in data['streams'] if s.get('codec_type')=='audio'),None)
    if not video or not audio or video.get('codec_name')!='h264':
        raise RuntimeError('Video/audio or H264 QA failed')
    if (video.get('width'),video.get('height'))!=(720,1280):
        raise RuntimeError('Expected vertical 720x1280')
    if duration<17.5 or duration>29.1:
        raise RuntimeError('Video duration out of validated Shorts range')
    if abs(float(meta.get('duration_seconds',0))-duration)>0.9:
        raise RuntimeError('Manifest/video duration mismatch')

def validate_manifest(root:Path,production:dict,config:dict,
                      want_public:bool)->tuple[Path,dict,dict]:
    prod_id=production['id']
    if production.get('status')!='DRAFT_REVIEW_REQUIRED':
        raise RuntimeError('Cannot auto-upload non-draft production')
    run=root/'output'/prod_id
    path=run/'short.mp4'
    if not (run/'manifest.json').is_file() or not (run/'storyboard.json').is_file():
        raise RuntimeError('Missing production QA reports')
    manifest=json.loads((run/'manifest.json').read_text(encoding='utf8'))
    storyboard=json.loads((run/'storyboard.json').read_text(encoding='utf8'))
    meta=manifest.get('production',{})
    verify_mp4(path,meta)
    story=manifest.get('story',{})
    if manifest.get('channel')!=config['channel_name']:
        raise RuntimeError('Cross-channel manifest rejected')
    if manifest.get('public_youtube_upload') is not False:
        raise RuntimeError('Production must originate from review-only engine')
    if not story.get('title') or not story.get('description') or not story.get('script'):
        raise RuntimeError('No validated editorial metadata')
    if story.get('source_url')!=production.get('source_url'):
        raise RuntimeError('Production/source provenance mismatch')
    if story['source_url'] not in story['description']:
        raise RuntimeError('Public source URL missing from description')
    if (len(story['title'])>100 or len(story['description'])>4900
            or len(story['script'].split())<12):
        raise RuntimeError('Invalid title, description or script')
    if storyboard.get('director_version')!='V3.2' or len(storyboard.get('scenes',[]))<5:
        raise RuntimeError('Storyboard quality gate failed')
    if len(set(s['layout'] for s in storyboard['scenes']))<5:
        raise RuntimeError('Repetitive storyboard rejected')
    if manifest.get('paid_video_generation') is not False:
        raise RuntimeError('Unexpected paid generation')
    if 'motion design' not in meta.get('visual_type','').lower():
        raise RuntimeError('Unknown visual assets; auto-upload blocked')
    if want_public:
        # The owner opts into this limited mode at GitHub Variables and confirms
        # the media rights review. The code NEVER asserts third-party rights.
        if config.get('youtube',{}).get('public_mode')!='official_releases_only':
            raise RuntimeError('Public mode is not explicitly enabled in config')
        if production.get('source_type') not in PUBLIC_RELEASE_PROVIDERS:
            raise RuntimeError('Unverified third-party news stays private')
        if production.get('script_type')!='template':
            raise RuntimeError('Unreviewed external LLM scripts stay private')
        if story.get('verified') is not False or not manifest.get('research',{}).get('fact_check_required'):
            raise RuntimeError('Invalid/ambiguous factual review status')
        if storyboard.get('source',{}).get('url')!=story['source_url']:
            raise RuntimeError('Storyboard source mismatch')
        # Require owner attestation, never claim automatic rights clearance.
    return path,manifest,story

def own_uploads(access_token:str,ch:dict,http:requests.Session)->list[dict]:
    uploads=ch.get('contentDetails',{}).get('relatedPlaylists',{}).get('uploads')
    if not uploads:
        raise RuntimeError('Cannot resolve uploads playlist; safe to stop, not retry')
    entries=[]
    page=None
    for _ in range(3):
        params={'part':'contentDetails','playlistId':uploads,'maxResults':50}
        if page:params['pageToken']=page
        r=http.get(API+'/playlistItems',headers={'Authorization':'Bearer '+access_token},
                   params=params,timeout=25)
        r.raise_for_status()
        data=r.json()
        entries.extend(data.get('items',[]))
        page=data.get('nextPageToken')
        if not page:break
    ids=[i.get('contentDetails',{}).get('videoId','') for i in entries]
    ids=[i for i in ids if VIDEO_ID.fullmatch(i)]
    videos=[]
    for i in range(0,len(ids),50):
        r=http.get(API+'/videos',headers={'Authorization':'Bearer '+access_token},
            params={'part':'snippet,status','id':','.join(ids[i:i+50])},timeout=25)
        r.raise_for_status()
        videos.extend(r.json().get('items',[]))
    return videos

def find_previous(access_token:str,ch:dict,http:requests.Session,marker:str)->dict|None:
    for video in own_uploads(access_token,ch,http):
        desc=video.get('snippet',{}).get('description','')
        if marker in desc.splitlines() and VIDEO_ID.fullmatch(video.get('id','')):
            return video
    return None

def resumable_insert(path:Path,body:dict,token:str,
                     http:requests.Session)->dict:
    # After session creation, upload timeouts are AMBIGUOUS: do not blindly
    # retry on any exception, because it can create duplicate publications.
    r=http.post(UPLOAD,
        params={'uploadType':'resumable','part':'snippet,status'},
        headers={'Authorization':'Bearer '+token,'Content-Type':'application/json',
                 'X-Upload-Content-Type':'video/mp4',
                 'X-Upload-Content-Length':str(path.stat().st_size)},
        json=body,timeout=30)
    r.raise_for_status()
    location=r.headers.get('Location','')
    parts=urlsplit(location)
    if parts.scheme!='https' or parts.hostname not in ('www.googleapis.com','youtube.googleapis.com'):
        raise RuntimeError('Google upload session returned unsafe endpoint')
    with path.open('rb') as source:
        response=http.put(location,data=source,
            headers={'Authorization':'Bearer '+token,'Content-Type':'video/mp4',
                     'Content-Length':str(path.stat().st_size)},
            timeout=240)
    response.raise_for_status()
    resource=response.json()
    if not VIDEO_ID.fullmatch(resource.get('id','')):
        raise RuntimeError('YouTube did not return a valid uploaded video ID')
    return resource

def upload_one(root:Path,config:dict,env:dict|None=None,
               session:requests.Session|None=None)->dict:
    env=os.environ if env is None else env
    status=check_oauth_settings(config,env)
    if status['status']!='configured_not_yet_verified':
        return status
    ledger_file=root/'state'/'productions.json'
    if not ledger_file.exists():
        return {'status':'awaiting_first_production'}
    ledger=json.loads(ledger_file.read_text(encoding='utf8'))
    items=ledger.get('productions',[])
    remaining=[p for p in items if p.get('status')=='DRAFT_REVIEW_REQUIRED']
    if not remaining:return {'status':'no_pending_draft'}
    # On scheduled runs only the MP4 rendered on this runner exists. Do not
    # silently scan old artifacts or change somebody else's YouTube videos.
    match=next((p for p in reversed(remaining)
                if (root/'output'/p['id']/'short.mp4').is_file()),None)
    if match is None:return {'status':'awaiting_render_artifact'}
    mode=config['youtube'].get('public_mode','disabled')
    public_requested=(mode=='official_releases_only'
         and env.get('YT_ALLOW_PUBLIC_AUTOMATION','')=='I_APPROVE_PUBLIC_UPLOADS')
    rights_owner_approved=env.get('YT_MEDIA_RIGHTS_APPROVED')=='I_REVIEWED_RIGHTS'
    want_public=public_requested and rights_owner_approved
    video_path,manifest,story=validate_manifest(root,match,config,want_public)
    if public_requested and not rights_owner_approved:
        raise RuntimeError('Public upload requires separate media-rights owner approval')
    # A risky public candidate is NOT silently uploaded in private if its
    # origin is ineligible: private staging remains a safe option.
    privacy='public' if want_public else 'private'
    if privacy=='public' and match.get('source_type') not in PUBLIC_RELEASE_PROVIDERS:
        raise RuntimeError('Refusing public upload of unverified news')
    http=session or requests.Session()
    token=token_from_refresh(env,http)
    ch=channel_info(token,http)
    if ch['id']!=expected_channel(env):
        raise RuntimeError('YouTube channel mismatch; refusing cross-channel upload')
    marker=make_marker(match)
    previous=find_previous(token,ch,http,marker)
    if previous:
        vid=previous['id']
        privacy=previous.get('status',{}).get('privacyStatus','unknown')
        matched=True
    else:
        body={'snippet':{
                  'title':story['title'][:100],
                  'description':story['description'][:4800]+'\n\n'+marker,
                  'categoryId':'28','defaultLanguage':'fr',
                  'tags':['deesezrxh','IA','open source','VELORA']
              },'status':{
                  'privacyStatus':privacy,
                  'selfDeclaredMadeForKids':False,
                  # True is a conservative owner-facing disclosure.
                  'containsSyntheticMedia':True
              }}
        response=resumable_insert(video_path,body,token,http)
        vid=response['id']
        matched=False
    # Read actual YouTube visibility. Unverified API projects may be forced
    # private even when videos.insert requested public.
    verify=http.get(API+'/videos',headers={'Authorization':'Bearer '+token},
                    params={'part':'status','id':vid},timeout=25)
    verify.raise_for_status()
    verified=verify.json().get('items',[])
    if len(verified)!=1 or verified[0].get('id')!=vid:
        raise RuntimeError('Cannot verify YouTube upload; stop before marking published')
    privacy=verified[0].get('status',{}).get('privacyStatus','')
    if privacy not in ('public','private','unlisted'):
        raise RuntimeError('Unknown final YouTube privacy status; stop')
    # Never print/store private IDs in the public repository or Actions logs.
    match['status']='PUBLISHED' if privacy=='public' else 'UPLOADED_PRIVATE'
    match.pop('video_id',None)
    match['publication_visibility']=privacy
    if privacy=='public':
        match['video_id']=vid
        result={'status':'published_public','url':'https://www.youtube.com/shorts/'+vid,
                'production_id':match['id'],'duplicate_prevented':matched}
    else:
        result={'status':'uploaded_private','production_id':match['id'],
                'duplicate_prevented':matched,
                'next':'Review private upload in YouTube Studio; no public audience data yet'}
    ledger_file.write_text(json.dumps(ledger,ensure_ascii=False,indent=2)+'\n',
                           encoding='utf8')
    return result

def connection_check(config:dict,env:dict|None=None,
                     session:requests.Session|None=None)->dict:
    env=os.environ if env is None else env
    state=check_oauth_settings(config,env)
    if state['status']!='configured_not_yet_verified':
        return state
    http=session or requests.Session()
    token=token_from_refresh(env,http)
    ch=channel_info(token,http)
    if ch['id']!=expected_channel(env):
        raise RuntimeError('Owner authorized a different YouTube channel')
    return {'status':'connected','channel_lock_ok':True,
            'requested_visibility':'private' if config['youtube'].get('public_mode')!='official_releases_only'
                                 else 'gated_public_opt_in'}

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description='VELORA YouTube safe connection or upload')
    parser.add_argument('--check',action='store_true',
                        help='Check owner identity and OAuth without uploading')
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    config=json.loads((root/'config.json').read_text(encoding='utf8'))
    try:
        result=connection_check(config) if args.check else upload_one(root,config)
    except (RuntimeError,ValueError,KeyError,requests.RequestException) as exc:
        # Do not leak Google responses, OAuth secrets or private video IDs.
        result={'status':'connection_or_delivery_blocked',
                'error_class':type(exc).__name__,
                'next':'Check OAuth channel choice and safety gates privately'}
        (root/'state'/'last_upload.json').write_text(
            json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        print('VELORA YouTube: BLOCKED',type(exc).__name__,flush=True)
        raise SystemExit(1)
    if not args.check:
        (root/'state'/'last_upload.json').write_text(
            json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('VELORA YouTube:',result['status'],flush=True)
