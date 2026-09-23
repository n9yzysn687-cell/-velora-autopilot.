import subprocess
import tempfile
import json
from hashlib import sha256
from PIL import Image
from pathlib import Path
import unittest
from unittest.mock import patch
from autopilot.source import Topic
from autopilot.writer import template_story
from autopilot.render import render

class RenderRealTests(unittest.TestCase):
    def test_real_mp4_encoder(self):
        topic=Topic('local','Open-source video editing reduces manual work','https://example.org/story','example.org','2026','video')
        story=template_story(topic,'deesezrxh')
        def offline_voice(script,dest,lang):
            subprocess.run(['ffmpeg','-y','-loglevel','error','-f','lavfi','-i','sine=frequency=230:duration=21',str(dest)],check=True)
            return True,'offline QA sine signal (test only)'
        with tempfile.TemporaryDirectory() as d:
            with patch('autopilot.render.voice_audio',side_effect=offline_voice):
                result=render(story,'deesezrxh',Path(d),max_seconds=29)
            self.assertGreater(result['bytes'],10000)
            self.assertGreater(result['duration_seconds'],18)
            self.assertLessEqual(result['duration_seconds'],29.1)
            self.assertEqual(result['director_version'],'V3.2')
            self.assertGreaterEqual(len(set(result['layouts'])),5)
            self.assertEqual(result['scene_count'],len(result['layouts']))
            board=json.loads((Path(d)/'storyboard.json').read_text())
            self.assertEqual(board['scene_count'],result['scene_count'])
            self.assertEqual(round(board['scenes'][-1]['end_seconds'],1),
                             round(result['duration_seconds'],1))
            frames=sorted((Path(d)/'frames').glob('scene_*.png'))
            self.assertEqual(len(frames),result['scene_count'])
            imhash=set()
            for file in frames:
                with Image.open(file) as im:
                    self.assertEqual(im.size,(720,1280))
                    imhash.add(sha256(im.tobytes()).hexdigest())
            self.assertEqual(len(imhash),result['scene_count'])
            print('REAL RENDER QA',result)

if __name__=='__main__':unittest.main()
