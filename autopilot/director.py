"""VELORA Director v3.2, deterministic zero-credit editorial storyboard.

Plans use the actual sourced headline and spoken script; graphic representations
are labelled as illustrations, never evidence or fabricated product interfaces.
Subtitles are scene-time approximations, not claimed word-level ASR alignment.
"""
from __future__ import annotations
from hashlib import sha256
import math
import re
from urllib.parse import urlsplit

LAYOUTS=('hero','split','chapters','steps','spotlight','source','finale','cards')
ACCENTS=('#7EE3D0','#83B9FA','#EDBD91','#B8A0F9')
WHITE='#F7FAFE'
BG='#081725'
SAFE_BOUNDS={'left':64,'right':656,'top':165,'bottom':1150}
MIN_SCENES=5
MAX_SCENES=8

def words(value:str)->list[str]:
    return re.findall(r'\S+',value.strip())

def shorten(value:str,maximum:int=95)->str:
    clean=' '.join(str(value).split())
    if len(clean)<=maximum:return clean
    return clean[:maximum-1].rsplit(' ',1)[0].rstrip(' .,:;')+'…'

def split_spoken(script:str,count:int)->list[str]:
    """Partition every word exactly once, balancing line length."""
    ws=words(script)
    if len(ws)<count:
        raise ValueError('Script too short to assign an audible passage to every scene.')
    result=[]
    for i in range(count):
        start=(len(ws)*i)//count
        end=(len(ws)*(i+1))//count
        result.append(' '.join(ws[start:end]))
    if ' '.join(result)!=' '.join(ws):
        raise RuntimeError('Director has lost spoken script content')
    return result

def choose_layouts(headline:str,variant:str,count:int)->list[str]:
    # Deterministic variation with reproducibility in the manifest.
    digest=sha256((headline+'|'+variant).encode()).digest()
    middles=list(LAYOUTS[1:-1])
    shift=digest[0]%len(middles)
    middles=middles[shift:]+middles[:shift]
    if digest[1]%2:middles=list(reversed(middles))
    return ['hero']+middles[:count-2]+['finale']

def make_storyboard(story:dict, channel:str, *,
                    approximate_seconds:float|None=None)->dict:
    script=str(story.get('script') or '').strip()
    headline=str(story.get('source_title') or story.get('title') or '').strip()
    source=str(story.get('source_url') or '').strip()
    if not headline or not source or not script:
        raise ValueError('Director requires script, real source title and URL.')
    count=max(MIN_SCENES,min(MAX_SCENES,math.ceil(len(words(script))/10)))
    count=min(count,len(words(script)))
    parts=split_spoken(script,count)
    layouts=choose_layouts(headline,str(story.get('variant','question')),count)
    theme=sha256(headline.encode()).digest()[0]%len(ACCENTS)
    accent=ACCENTS[theme]
    host=(urlsplit(source).hostname or 'source').removeprefix('www.')
    scenes=[]
    for i,(text,layout) in enumerate(zip(parts,layouts)):
        focus=(headline if i==0 else
               'Ce que l’on sait' if layout=='source' else
               'À suivre' if i==count-1 else
               shorten(' '.join(words(text)[:9]),58))
        prompt=('Original editorial abstract scene. '+
                headline+'. Visual chapter: '+focus+'. '+
                'Deep navy and mint, deliberate camera movement, '+
                'no fake interfaces, no logos, no readable generated text.')
        scenes.append({
            'scene_id':f'{i+1:02d}','layout':layout,'beat':('hook' if i==0 else
                 'outro' if i==count-1 else 'body'),
            'headline':shorten(focus,92),
            'voice_excerpt':text,
            'caption':text,
            'source_domain':shorten(host,45),
            'visual_prompt':prompt,
            'approximation_warning':'captions timed to scene, not word-level audio',
            'motion':'slow_center_zoom' if i%2==0 else 'slow_center_zoom_reverse',
            'weight':max(1,len(words(text)))
        })
    return {
      'director_version':'V3.2','identity':{'channel':channel,'background':BG,
        'text':WHITE,'accent':accent,'safe_bounds_720x1280':SAFE_BOUNDS},
      'claims_verified':False,
      'visual_material':'original editorial illustration; no claim of actual AI model footage',
      'source':{'headline':headline,'url':source,'domain':host},
      'spoken_word_count':len(words(script)),
      'scene_count':count,
      'planned_seconds':approximate_seconds,
      'caption_timing':'scene-level approximation by spoken word allocation',
      'scenes':scenes
    }

def allocate_frames(storyboard:dict,duration:float,fps:int=24)->list[int]:
    if duration<17.5 or fps<12:
        raise ValueError('Director requires an acceptable final duration and fps.')
    items=storyboard['scenes']
    total_frames=round(duration*fps)
    if total_frames<len(items)*fps*2:
        raise ValueError('Insufficient duration for legible scenes.')
    # Reserve 1 frame/scene so rounding cannot omit a scene.
    weights=[max(1,int(s['weight'])) for s in items]
    remaining=total_frames-len(items)*fps*2
    if remaining<0:raise ValueError('Scenes below minimum length.')
    allocations=[fps*2+remaining*sum(weights[:i])//sum(weights)
                 for i in range(len(items))]
    # Compute differences of cumulative proportional allocation.
    allocations=[fps*2+remaining*sum(weights[:i+1])//sum(weights)-
                 remaining*sum(weights[:i])//sum(weights)
                 for i in range(len(items))]
    assert sum(allocations)==total_frames
    return allocations
