"""No-credit motion-design renderer. CPU only: Pillow + FFmpeg, with honest limitations."""
from __future__ import annotations
import math
import os
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

FONT_BOLD = ['/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
             '/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf']
FONT_REG = ['/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            '/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf']
SCENE_KEYS = [
    ('L’IDÉE', 'WHAT IF'), ('LE SUJET', 'RESEARCH'),
    ('LE PROBLÈME', 'CONTEXT'), ('LA MÉTHODE', 'PROCESS'),
    ('LE CONTRÔLE', 'REVIEW'), ('LA SUITE', 'NEXT'),
]

def font(sz: int, bold=False):
    for path in FONT_BOLD if bold else FONT_REG:
        if os.path.isfile(path):
            return ImageFont.truetype(path, sz)
    return ImageFont.load_default()


def wrap(draw: ImageDraw.ImageDraw, text: str, fnt, width: int, lines=4):
    words = text.split()
    result, line = [], ''
    for word in words:
        candidate = f'{line} {word}'.strip()
        if draw.textbbox((0, 0), candidate, font=fnt)[2] > width and line:
            result.append(line)
            line = word
        else:
            line = candidate
    if line:
        result.append(line)
    return result[:lines]


def scene_image(index: int, story: dict, channel: str, out: Path, width=720, height=1280):
    im = Image.new('RGB', (width, height), '#091621')
    d = ImageDraw.Draw(im)
    white, teal, grey = '#F3F9FA', '#78DDC9', '#ABC9CC'
    title, english = SCENE_KEYS[index]
    for ring in range(4):
        r = 130 + ring * 72
        d.ellipse((width//2-r, height//2+130-r, width//2+r, height//2+130+r),
                  outline=('#144D56','#24636A','#276F70','#338984')[ring], width=3)
    for n in range(30):
        x, y = 45+(n*179)%630, 185+(n*431+index*19)%970
        d.ellipse((x,y,x+2,y+2), fill='#4D9892')
    d.text((54,53),channel.upper(),font=font(22,True),fill=teal)
    d.line((54,112,666,112),fill='#337E79',width=2)
    d.text((54,154),f'0{index+1}   /   {english}',font=font(22,True),fill=teal)
    d.text((54,245),title,font=font(59,True),fill=white)
    raw = [
        story['hook'], story['source_title'],
        'Quel besoin réel ce sujet peut-il résoudre ?',
        'Vérifier la source. Comprendre. Tester.',
        'Les faits. Les droits. La qualité.',
        'On explore la suite ensemble.',
    ][index]
    size=31 if index == 1 else 39
    lines=wrap(d,raw,font(size,True),600,5)
    for j,one in enumerate(lines):
        d.text((58,430+j*size*1.55),one,font=font(size,True),fill=white)
    if index in (2,3,4):
        for j,sub in enumerate((['SOURCES','TESTS','DÉCISION'] if index==3 else ['RECHERCHE','ANALYSE','REVUE'])):
            yy=825+j*83
            d.rounded_rectangle((55,yy,664,yy+62),radius=13,fill='#1A3540',outline='#357E79',width=2)
            d.text((80,yy+13),sub,font=font(25,True),fill=teal)
    d.line((54,1190,666,1190),fill='#337E79',width=2)
    d.text((54,1211),'VELORA  /  AUTOPILOT',font=font(22,True),fill=grey)
    d.text((629,1211),str(index+1).zfill(2),font=font(22,True),fill=teal)
    im.save(out,optimize=True)


def command(args: list[str]):
    subprocess.run(args, check=True, capture_output=True, text=True,timeout=180)


def voice_audio(script: str, dest: Path, lang='fr') -> tuple[bool,str]:
    try:
        from gtts import gTTS
        gTTS(script,lang=lang).save(str(dest))
        return True,'gTTS (online speech synthesis)'
    except Exception as error:
        # An offline fallback keeps the autonomous workflow from getting stuck
        # just because public online speech synthesis is rate limited.
        import shutil
        offline = shutil.which('espeak-ng') or shutil.which('espeak')
        if offline:
            command([offline,'-v','fr','-s','170','-w',str(dest.with_suffix('.wav')),script])
            return True, 'eSpeak (offline fallback)'
        return False,f'No narration available: {type(error).__name__}'


def probe_duration(path: Path) -> float:
    r=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','default=noprint_wrappers=1:nokey=1',str(path)],
                     text=True,capture_output=True,check=True,timeout=30)
    return float(r.stdout.strip())


def render(story: dict, channel: str, dest: Path, max_seconds=29, lang='fr', generated_clip: Path|None=None):
    dest.mkdir(parents=True,exist_ok=True)
    frames=dest/'frames';frames.mkdir(exist_ok=True)
    for i in range(len(SCENE_KEYS)):
        scene_image(i,story,channel,frames/f'scene_{i:02}.png')
    audio=dest/'narration.mp3'
    voice_ok,voice_provider=voice_audio(story['script'],audio,lang)
    if not audio.exists() and (dest/'narration.wav').exists():
        audio=dest/'narration.wav'
    if not voice_ok:
        raise RuntimeError(f'No accessible TTS engine; video draft stopped: {voice_provider}')
    narration_secs=probe_duration(audio)
    if narration_secs > max_seconds-1.1:
        raise RuntimeError(f'Narration {narration_secs:.1f}s exceeds {max_seconds}s short; shorten script instead of truncating speech.')
    duration=min(float(max_seconds),max(18.0,narration_secs+1.5))
    secs=duration/len(SCENE_KEYS)
    segments=[]
    for i in range(len(SCENE_KEYS)):
        path=dest/f'segment_{i:02}.mp4'
        frames_per=int(math.ceil(secs*24))
        if i==3 and generated_clip is not None:
            # Replace exactly one diagram shot with the model's genuine footage.
            # Cropping is deliberate only for external cinematic scenes, never docs/UI.
            command(['ffmpeg','-hide_banner','-loglevel','error','-y','-stream_loop','-1',
                     '-i',str(generated_clip),'-vf',
                     'scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,fps=24,format=yuv420p',
                     '-t',str(frames_per/24),'-an','-c:v','libx264','-preset','ultrafast','-crf','27','-r','24',str(path)])
        else:
            command(['ffmpeg','-hide_banner','-loglevel','error','-y','-loop','1',
                     '-i',str(frames/f'scene_{i:02}.png'),'-vf',
                     f"scale=720:1280,zoompan=z='min(zoom+0.0006,1.06)':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d={frames_per}:s=720x1280:fps=24,format=yuv420p",
                     '-frames:v',str(frames_per),'-an','-c:v','libx264','-preset','ultrafast','-crf','27','-r','24',str(path)])
        segments.append(path)
    join=dest/'join.txt'
    join.write_text(''.join(f"file '{x.as_posix()}'\n" for x in segments),encoding='utf8')
    target=dest/'short.mp4'
    args=['ffmpeg','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(join)]
    if voice_ok:
        args+=['-i',str(audio),'-map','0:v:0','-map','1:a:0']
    else:
        args+=['-map','0:v:0']
    args+=['-t',str(duration),'-c:v','copy']
    if voice_ok:
        args+=['-c:a','aac','-b:a','128k']
    args+=['-movflags','+faststart',str(target)]
    command(args)
    if not target.exists() or target.stat().st_size<10000:
        raise RuntimeError('MP4 failed QA: missing or empty.')
    measured=probe_duration(target)
    if not (17.5<=measured<=max_seconds+.10):
        raise RuntimeError(f'MP4 failed duration QA: {measured}s')
    return {'video':str(target),'duration_seconds':round(measured,2),'bytes':target.stat().st_size,'voice':voice_provider,
            'visual_type':'one authenticated ZeroGPU generated scene + motion design' if generated_clip else 'original motion design, NOT generative photorealistic video'}
