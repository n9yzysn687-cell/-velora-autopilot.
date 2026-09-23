import json
from datetime import datetime,timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from autopilot.source import normalize_topic,discover,Topic
from autopilot.writer import template_story
from autopilot.main import run

T=Topic('id-1','A plausible open-source video workflow announcement',
        'https://example.org/story','example.org','2026-09-23T15:00:00Z','open source')

class FakeResponse:
    def raise_for_status(self):return None
    def json(self):
        now=datetime.now(timezone.utc).isoformat()
        return {'hits':[{'objectID':'id-1','title':T.headline,'url':T.url,'created_at':now,'points':14},
                        {'objectID':'id-2','title':'Follow-up open-source model announcement','url':'https://example.org/second','created_at':now,'points':14}]}
class FakeSession:
    def get(self,*args,**kwargs):return FakeResponse()

class SourceTests(unittest.TestCase):
    def test_invalid_http_rejected(self):
        self.assertIsNone(normalize_topic({'objectID':'id','title':'A worthwhile technology headline','url':'http://example.com'},'ai'))
    def test_duplicate_skipped(self):
        t=discover(['ai'],{'id-1'},FakeSession())
        self.assertEqual('id-2',t.id)
    def test_explicit_source_in_script(self):
        text=template_story(T,'deesezrxh')
        self.assertIn(T.url,text['description'])
        self.assertFalse(text['verified'])

class LoopTests(unittest.TestCase):
    def make_root(self,path,daily=1):
        (path/'state').mkdir(exist_ok=True)
        (path/'config.json').write_text(json.dumps({'channel_name':'deesezrxh','themes':['ai'],
             'shorts_per_day':daily,'max_daily_paid_eur':0,'max_seconds':29,
             'providers':{'script':'template','video':'motion_design'}}))
        (path/'fixture.json').write_text(json.dumps(T.__dict__))
    def test_run_persists_and_stops_at_daily_cap(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.make_root(root)
            def fake_render(story,channel,out,*args):
                (out/'short.mp4').write_bytes(b'fake-video')
                return {'video':str(out/'short.mp4'),'duration_seconds':23,'bytes':10,'voice':'test','visual_type':'test'}
            with patch('autopilot.main.render',side_effect=fake_render):
                first=run(root,root/'fixture.json')
                second=run(root,root/'fixture.json')
            self.assertEqual(first['status'],'draft_ready')
            self.assertEqual(second['status'],'daily_limit_reached')
            self.assertEqual(json.loads((root/'state/state.json').read_text())['seen_ids'],['id-1'])
            manifest=json.loads(Path(first['manifest']).read_text())
            self.assertFalse(manifest['public_youtube_upload'])
            self.assertFalse(manifest['script_verified'])
            self.assertTrue(Path(first['research_report']).exists())
            self.assertEqual(manifest['research']['report_file'],'research.json')
            self.assertEqual(manifest['source']['provenance'],'hacker_news')
            memory=json.loads((root/'state/productions.json').read_text())
            self.assertEqual(len(memory['productions']),1)
            self.assertEqual(memory['productions'][0]['source_url'],T.url)
            self.assertEqual(memory['productions'][0]['status'],'DRAFT_REVIEW_REQUIRED')
    def test_zero_budget_enforced(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.make_root(root)
            conf=json.loads((root/'config.json').read_text())
            conf['max_daily_paid_eur']=2
            (root/'config.json').write_text(json.dumps(conf))
            with self.assertRaisesRegex(RuntimeError,'Paid rendering'):
                run(root,root/'fixture.json')
    def test_error_recorded_without_marking_seen(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.make_root(root)
            with patch('autopilot.main.render',side_effect=RuntimeError('No encoder')):
                report=run(root,root/'fixture.json')
            self.assertEqual(report['status'],'paused_after_error')
            data=json.loads((root/'state/state.json').read_text())
            self.assertFalse(data.get('seen_ids'))
            self.assertEqual(data['failed_topics']['id-1'],1)

if __name__=='__main__':unittest.main()
