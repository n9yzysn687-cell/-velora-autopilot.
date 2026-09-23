import subprocess
import tempfile
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
            print('REAL RENDER QA',result)

if __name__=='__main__':unittest.main()
