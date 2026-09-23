"""VELORA V3.2 original editorial motion-design film renderer (CPU, no AI credits).

No fabricated screenshots/dashboards or generated-model footage claims.
Scene captions are tied to the Director's own verbatim script partitions.
"""
from __future__ import annotations
from hashlib import sha256
import math
import os
import shutil
import subprocess
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from .director import make_storyboard, allocate_frames,shorten

FONT_BOLD=['/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
           '/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf']
FONT_REG=['/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
          '/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf']
WIDTH,HEIGHT=720,1280
BG='#081725';WHITE='#F7FAFE';MUTED='#B6C9CE'
DEEP='#0E2735';CARD='#15313E'
FPS=24

def font(size:int,bold:bool=False):
    for path in (FONT_BOLD if bold else FONT_REG):
        if os.path.isfile(path):
            return ImageFont.truetype(path,size)
    return ImageFont.load_default()

def wrap(draw,text,fnt,width,lines=4):
    words=str(text).split()
    result=[];line=''
    for word in words:
        candidate=(line+' '+word).strip()
        if draw.textbbox((0,0),candidate,font=fnt)[2]<=width:
            line=candidate
        else:
            if line:
                result.append(line)
                line=word
            else:
                result.append(word)
                line=''
    if line:result.append(line)
    if len(result)>lines:
        result=result[:lines]
        result[-1]=shorten(result[-1],max(3,len(result[-1])-2))
    return result

def text(draw,content,x,y,max_width,*,size=35,color=WHITE,
         bold=True,max_lines=4,step=None):
    content=' '.join(str(content).split())
    sz=size
    while sz>=18:
        f=font(sz,bold)
        lines=wrap(draw,content,f,max_width,max_lines)
        all_words=' '.join(lines).replace('…','')
        if len(lines)<=max_lines and len(all_words)>=min(len(content),len(content)*.78):
            break
        sz-=2
    f=font(sz,bold)
    lines=wrap(draw,content,f,max_width,max_lines)
    stride=step or int(sz*1.45)
    for n,line in enumerate(lines):
        draw.text((x,y+n*stride),line,font=f,fill=color)
    return y+stride*len(lines)

def box(draw,coords,fill=CARD,outline=None,radius=24,width=2):
    draw.rounded_rectangle(coords,radius=radius,fill=fill,outline=outline,width=width)

def background(accent,index,seed):
    im=Image.new('RGB',(WIDTH,HEIGHT),BG)
    d=ImageDraw.Draw(im)
    for y in range(0,HEIGHT,4):
        f=y/HEIGHT
        rgb=(int(8+10*f),int(23+14*f),int(37+13*f))
        d.rectangle((0,y,WIDTH,y+3),fill=rgb)
    # Original deterministic editorial grain / network particles.
    for n in range(40):
        xx=35+(n*137+seed*11+index*39)%650
        yy=175+(n*223+seed*5+index*83)%950
        d.ellipse((xx,yy,xx+2,yy+2),fill='#2D6570')
    return im,d

def draw_layout(d,scene,identity,index,total):
    accent=identity['accent'];layout=scene['layout'];headline=scene['headline']
    topic=identity.get('source_headline','')
    domain=scene.get('source_domain','source')
    y0=425
    if layout=='hero':
        for radius,c in [(254,'#103844'),(194,'#1B5260'),(130,accent)]:
            d.ellipse((360-radius,740-radius,360+radius,740+radius),outline=c,width=4)
        box(d,(94,666,626,821),DEEP,accent,27,3)
        text(d,headline,122,690,480,size=42,max_lines=3)
        d.ellipse((605,650,632,677),fill=accent)
    elif layout=='split':
        box(d,(62,435,658,670),CARD,accent,25)
        text(d,'SOURCE',87,464,530,size=22,color=accent,max_lines=1)
        text(d,domain,87,515,520,size=39,max_lines=2)
        box(d,(62,694,658,890),DEEP,'#417280',25)
        text(d,'L’ANGLE',87,719,530,size=22,color=accent,max_lines=1)
        text(d,headline,87,766,530,size=34,max_lines=3)
    elif layout=='chapters':
        for i,(tag,word) in enumerate((('01','OBSERVATION'),
                                        ('02','EXPLICATION'),('03','VÉRIFICATION'))):
            x=62+i*205
            box(d,(x,456,x+190,881),('#15313E' if i!=1 else '#204353'),accent if i==1 else '#376875',18)
            text(d,tag,x+20,490,150,size=47,color=accent,max_lines=1)
            d.line((x+20,574,x+170,574),fill=accent,width=3)
            text(d,word,x+16,625,160,size=21,max_lines=3)
            d.arc((x+37,760,x+150,874),0,285,fill=accent,width=5)
    elif layout=='steps':
        for i,name in enumerate(('IDÉE','SOURCE','TEST','REVUE')):
            x=116 if i%2==0 else 400
            y=470+(i//2)*220
            box(d,(x-39,y-23,x+210,y+142),CARD,'#346B77',20)
            d.ellipse((x-21,y+10,x+24,y+55),fill=accent)
            text(d,str(i+1),x-8,y+18,40,size=19,color=BG,max_lines=1)
            text(d,name,x+45,y+14,170,size=25,max_lines=2)
        d.line((358,494,358,817),fill='#346B77',width=3)
        d.line((162,690,556,690),fill='#346B77',width=3)
    elif layout=='spotlight':
        d.ellipse((30,437,690,1040),outline='#245F68',width=5)
        d.ellipse((100,502,620,974),outline=accent,width=3)
        box(d,(97,597,623,842),DEEP,accent,30,3)
        text(d,headline,131,638,470,size=42,max_lines=4)
        text(d,'UN ANGLE À EXPLORER',138,841,475,size=20,color=accent,max_lines=1)
    elif layout=='source':
        box(d,(72,451,648,887),'#173744',accent,27)
        box(d,(105,490,615,548),DEEP,'#3D7C7B',15)
        text(d,'SOURCE À VÉRIFIER',122,505,465,size=21,color=accent,max_lines=1)
        text(d,domain,106,595,493,size=34,max_lines=3)
        d.line((110,741,611,741),fill=accent,width=3)
        text(d,'Lien original dans la description',109,773,488,size=23,color=MUTED,max_lines=2)
        text(d,'PAS UNE PREUVE AUTOMATIQUE',93,915,540,size=19,color=accent,max_lines=1)
    elif layout=='cards':
        labels=('SUJET','CONTEXTE','À VÉRIFIER')
        for i,label in enumerate(labels):
            y=452+i*143
            box(d,(74,y,647,y+122),CARD,accent if i==1 else '#3B7782',20)
            d.ellipse((93,y+39,125,y+71),fill=accent)
            text(d,label,143,y+27,475,size=30,max_lines=2)
    elif layout=='finale':
        for radius in (260,198,143):
            d.ellipse((360-radius,686-radius,360+radius,686+radius),outline='#285F6B',width=3)
        box(d,(71,602,649,796),CARD,accent,30,3)
        text(d,'DEES EZRXH'.replace(' ',''),116,641,475,size=51,max_lines=1,color=WHITE)
        text(d,'LE PROCHAIN TEST ARRIVE',106,743,510,size=24,max_lines=1,color=accent)
        text(d,'SOURCE ET CONTEXTE EN DESCRIPTION',72,889,580,size=20,color=MUTED,max_lines=2)
    else:raise ValueError('Unknown storyboard layout: '+str(layout))

def scene_image(index:int,story:dict,channel:str,out:Path,width=720,height=1280,
                storyboard:dict|None=None):
    if (width,height)!=(WIDTH,HEIGHT):
        raise ValueError('V3.2 layout is designed for 720x1280 safe areas')
    board=storyboard or make_storyboard(story,channel)
    if not 0<=index<len(board['scenes']):
        raise IndexError('Storyboard scene index')
    scene=board['scenes'][index]
    ident=dict(board['identity'],source_headline=board['source']['headline'])
    accent=ident['accent']
    seed=sha256(board['source']['headline'].encode()).digest()[2]
    im,d=background(accent,index,seed)
    text(d,channel.upper(),60,59,570,size=28,color=accent,max_lines=1)
    d.line((60,116,659,116),fill='#397880',width=2)
    text(d,f'FILM 01  /  SCÈNE {index+1:02d}',60,171,510,size=21,color=accent,max_lines=1)
    # Episode header changes with actual story. Truncated source text is never
    # represented as a quote from the article.
    text(d,board['source']['headline'],60,239,591,size=33,max_lines=3)
    draw_layout(d,scene,ident,index,len(board['scenes']))
    # Safe reading zone: no text below 1140 due to mobile Shorts overlays.
    box(d,(56,984,664,1152),DEEP,'#3E7D83',18)
    text(d,scene['caption'],78,1003,564,size=27,bold=True,max_lines=4)
    d.line((60,1190,658,1190),fill='#32767A',width=2)
    text(d,'VELORA / DIRECTOR V3.2',60,1215,520,size=18,color=MUTED,max_lines=1)
    text(d,f'{index+1:02d}/{len(board["scenes"]):02d}',585,1215,72,size=18,color=accent,max_lines=1)
    im.save(out,optimize=True)

def command(args:list[str]):
    subprocess.run(args,check=True,capture_output=True,text=True,timeout=180)

def voice_audio(script:str,dest:Path,lang='fr')->tuple[bool,str]:
    try:
        from gtts import gTTS
        gTTS(script,lang=lang).save(str(dest))
        return True,'gTTS (online speech synthesis)'
    except Exception as error:
        offline=shutil.which('espeak-ng') or shutil.which('espeak')
        if offline:
            command([offline,'-v','fr','-s','170','-w',str(dest.with_suffix('.wav')),script])
            return True,'eSpeak (offline fallback)'
        return False,f'No narration available: {type(error).__name__}'

def probe_duration(path:Path)->float:
    r=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration',
        '-of','default=noprint_wrappers=1:nokey=1',str(path)],
        text=True,capture_output=True,check=True,timeout=30)
    return float(r.stdout.strip())

def probe_video(path:Path)->dict:
    import json
    proc=subprocess.run(['ffprobe','-v','error','-select_streams','v:0',
        '-show_entries','stream=codec_name,width,height,avg_frame_rate',
        '-of','json',str(path)],text=True,capture_output=True,check=True,timeout=30)
    streams=json.loads(proc.stdout).get('streams') or []
    if not streams:raise RuntimeError('MP4 has no video stream')
    v=streams[0]
    if (int(v['width']),int(v['height']))!=(WIDTH,HEIGHT):
        raise RuntimeError('MP4 failed 9:16 resolution QA')
    if v.get('codec_name')!='h264':
        raise RuntimeError('MP4 failed H.264 compatibility QA')
    return v

def render(story:dict,channel:str,dest:Path,max_seconds=29,lang='fr',
           generated_clip:Path|None=None,storyboard:dict|None=None):
    dest.mkdir(parents=True,exist_ok=True)
    board=storyboard or make_storyboard(story,channel)
    if board.get('director_version')!='V3.2':
        raise RuntimeError('Unrecognized director storyboard version')
    scenes=board['scenes']
    if not 5<=len(scenes)<=8 or len(set(s['layout'] for s in scenes))<5:
        raise RuntimeError('Director QA: repetitive or insufficiently varied storyboard')
    narration=dest/'narration.mp3'
    voice_ok,voice_provider=voice_audio(story['script'],narration,lang)
    if not narration.exists() and (dest/'narration.wav').exists():
        narration=dest/'narration.wav'
    if not voice_ok or not narration.exists():
        raise RuntimeError('No voice engine; no silent misleading video delivered: '+voice_provider)
    narration_secs=probe_duration(narration)
    if narration_secs>float(max_seconds)-1.1:
        raise RuntimeError(f'Narration {narration_secs:.1f}s exceeds {max_seconds}s short; shorten script instead of truncating speech.')
    duration=min(float(max_seconds),max(18.0,narration_secs+1.5))
    frames=allocate_frames(board,duration,FPS)
    frames_dir=dest/'frames'
    frames_dir.mkdir(exist_ok=True)
    segments=[]
    cursor=0
    for i,scene in enumerate(scenes):
        scene['start_seconds']=round(cursor/FPS,3)
        cursor+=frames[i]
        scene['end_seconds']=round(cursor/FPS,3)
        image=frames_dir/f'scene_{i:02}.png'
        scene_image(i,story,channel,image,storyboard=board)
        path=dest/f'segment_{i:02}.mp4'
        if i==len(scenes)//2 and generated_clip is not None:
            # Contain footage: do not crop logos, interface panels or references.
            filt=(f'scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,'
                  f'pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2:color=0x081725,'
                  f'fps={FPS},format=yuv420p')
            command(['ffmpeg','-hide_banner','-loglevel','error','-y',
                     '-stream_loop','-1','-i',str(generated_clip),'-vf',filt,
                     '-frames:v',str(frames[i]),'-an','-c:v','libx264',
                     '-preset','ultrafast','-crf','27','-r',str(FPS),str(path)])
        else:
            filt=(f'scale={WIDTH}:{HEIGHT},zoompan='
                  f"z='min(zoom+0.00014,1.027)':"
                  f"x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':"
                  f'd={frames[i]}:s={WIDTH}x{HEIGHT}:fps={FPS},format=yuv420p')
            command(['ffmpeg','-hide_banner','-loglevel','error','-y',
                     '-loop','1','-i',str(image),'-vf',filt,
                     '-frames:v',str(frames[i]),'-an','-c:v','libx264',
                     '-preset','ultrafast','-crf','27','-r',str(FPS),str(path)])
        segments.append(path)
    import json
    (dest/'storyboard.json').write_text(
        json.dumps(board,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    join=dest/'join.txt'
    join.write_text(''.join(f"file '{x.as_posix()}'\n" for x in segments),encoding='utf8')
    target=dest/'short.mp4'
    command(['ffmpeg','-hide_banner','-loglevel','error','-y',
             '-f','concat','-safe','0','-i',str(join),
             '-i',str(narration),'-map','0:v:0','-map','1:a:0',
             '-t',str(duration),'-c:v','copy','-c:a','aac',
             '-b:a','128k','-movflags','+faststart',str(target)])
    if not target.exists() or target.stat().st_size<10000:
        raise RuntimeError('MP4 failed QA: missing or empty')
    measured=probe_duration(target)
    if not 17.5<=measured<=max_seconds+.15:
        raise RuntimeError(f'MP4 failed duration QA: {measured}s')
    probe_video(target)
    return {'video':str(target),'duration_seconds':round(measured,2),
            'bytes':target.stat().st_size,'voice':voice_provider,
            'director_version':'V3.2','scene_count':len(scenes),
            'layouts':[s['layout'] for s in scenes],
            'storyboard_file':'storyboard.json',
            'subtitle_method':'verbatim scene-level approximate, not forced alignment',
            'visual_type':('one authenticated external generated scene + original editorial '
                           'motion design' if generated_clip else
                           'original editorial motion design; NOT generative AI model footage')}
