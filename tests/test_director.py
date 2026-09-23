"""V3.2 Director: verifiable visual variety and exact script coverage."""
from pathlib import Path
from tempfile import TemporaryDirectory
from hashlib import sha256
import unittest
from PIL import Image
from autopilot.director import make_storyboard,allocate_frames,split_spoken
from autopilot.render import scene_image,wrap,font
from autopilot.source import Topic
from autopilot.writer import template_story

def story(title):
    topic=Topic('one',title,'https://example.org/source','example.org',
                '2026-09-23T09:00:00Z','création vidéo IA')
    return template_story(topic,'deesezrxh','direct')

class DirectorTests(unittest.TestCase):
    def test_all_spoken_words_kept_in_storyboard(self):
        s=story('Wan open source AI video generation with new workflows')
        p=make_storyboard(s,'deesezrxh')
        self.assertEqual(' '.join(x['voice_excerpt'] for x in p['scenes']),
                         ' '.join(s['script'].split()))
        self.assertTrue(all(x['voice_excerpt']==x['caption'] for x in p['scenes']))
        self.assertTrue(all('visual_prompt' in x for x in p['scenes']))
        self.assertTrue(p['caption_timing'].startswith('scene-level'))
    def test_five_to_eight_distinct_layouts(self):
        p=make_storyboard(story('A creative Wan AI video edit system'),'deesezrxh')
        styles=[s['layout'] for s in p['scenes']]
        self.assertGreaterEqual(len(styles),5)
        self.assertLessEqual(len(styles),8)
        self.assertEqual(len(set(styles)),len(styles))
        self.assertEqual(styles[0],'hero')
        self.assertEqual(styles[-1],'finale')
    def test_topic_changes_design_not_only_title_overlay(self):
        a=make_storyboard(story('Wan video AI generator studio'),'deesezrxh')
        b=make_storyboard(story('ComfyUI workflows for local AI video rendering'),'deesezrxh')
        # Brand stays stable, subject visibly changes in different chapters.
        self.assertNotEqual(a['source']['headline'],b['source']['headline'])
        self.assertTrue(any(x['headline']!=y['headline']
            for x,y in zip(a['scenes'],b['scenes'])))
    def test_word_coverage_variable_lengths(self):
        for n in (36,44,58,72,99):
            parts=split_spoken(' '.join('word'+str(i) for i in range(n)),
                               min(8,max(5,(n+9)//10)))
            self.assertEqual(len(' '.join(parts).split()),n)
            self.assertTrue(all(parts))
    def test_exact_timing_no_missing_frames(self):
        p=make_storyboard(story('Wan AI video workflows explained'),'deesezrxh')
        for length in (18.,21.4,28.7):
            f=allocate_frames(p,length)
            self.assertEqual(sum(f),round(length*24))
            self.assertTrue(all(x>=48 for x in f))
    def test_renderer_saves_unique_shots_in_phone_safe_bounds(self):
        p=make_storyboard(story('New open source video generation engine'),'deesezrxh')
        with TemporaryDirectory() as d:
            digests=set()
            for i in range(p['scene_count']):
                file=Path(d)/f'scene{i}.png'
                scene_image(i,story('New open source video generation engine'),
                            'deesezrxh',file,storyboard=p)
                with Image.open(file) as image:
                    self.assertEqual(image.size,(720,1280))
                    digests.add(sha256(image.tobytes()).hexdigest())
            self.assertEqual(len(digests),p['scene_count'])
    def test_reject_missing_source_or_short_script(self):
        with self.assertRaisesRegex(ValueError,'script'):
            make_storyboard({'source_title':'Video engine',
                             'source_url':'https://example.org',
                             'script':''},'deesezrxh')
        with self.assertRaisesRegex(ValueError,'too short'):
            make_storyboard({'source_title':'Video engine',
                             'source_url':'https://example.org',
                             'script':'bonjour'},'deesezrxh')
if __name__=='__main__':unittest.main()
