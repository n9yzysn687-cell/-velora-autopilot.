"""Feedback loop tests use synthetic measurements; no real YouTube data is invented."""
import json
import tempfile
import unittest
from datetime import date, timedelta, datetime, timezone
from pathlib import Path
from unittest.mock import patch

from autopilot.feedback import (validate_mapping, aggregate, score, learn,
                                discover_own_public_uploads)
from autopilot.main import editorial_plan
from autopilot.writer import template_story
from autopilot.source import Topic

ENV={'YT_CLIENT_ID':'test','YT_CLIENT_SECRET':'test','YT_REFRESH_TOKEN':'test'}

def v(theme, variant, views=400, retention=90, likes=20, subs=3):
    return ({'theme':theme,'variant':variant},
            {'views':views,'averageViewPercentage':retention,
             'likes':likes,'subscribersGained':subs})

class Response:
    def __init__(self, obj):self.obj=obj
    def raise_for_status(self):pass
    def json(self):return self.obj

class FakeYT:
    def __init__(self):self.calls=[]
    def post(self, url, **kwargs):
        self.calls.append(('post',url,kwargs))
        return Response({'access_token':'test-access'})
    def get(self,url,**kwargs):
        self.calls.append(('get',url,kwargs))
        if url.endswith('/channels'):
            return Response({'items':[{'contentDetails':{'relatedPlaylists':{'uploads':'UUtest'}}}]})
        if url.endswith('/playlistItems'):
            return Response({'items':[{'contentDetails':{'videoId':'abc123DEF45'}},
                                      {'contentDetails':{'videoId':'ghi123DEF45'}}]})
        if url.endswith('/videos'):
            return Response({'items':[
                {'id':'abc123DEF45','status':{'privacyStatus':'public'},
                 'snippet':{'description':'Published video. Source https://example.org/a',
                            'publishedAt':'2026-09-10T10:00:00Z'}},
                {'id':'ghi123DEF45','status':{'privacyStatus':'private'},
                 'snippet':{'description':'Source https://example.org/b',
                            'publishedAt':'2026-09-10T10:00:00Z'}}]})
        if url.endswith('/reports'):
            return Response({'columnHeaders':[{'name':x} for x in
                ('views','averageViewPercentage','likes','subscribersGained')],
                'rows':[[410,80,17,3]]})
        raise AssertionError(url)

class FeedbackTests(unittest.TestCase):
    def test_no_oauth_does_not_fake_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            res=learn(Path(tmp),{'themes':['ai']},env={})
            self.assertEqual('awaiting_youtube_readonly_oauth',res['status'])
            self.assertNotIn('preferred_variant',res)
    def test_only_public_mature_valid_mapping(self):
        now=date(2026,9,23)
        rows=[
            {'video_id':'abc123DEF45','published_at':'2026-09-10','theme':'ai','variant':'direct','visibility':'public'},
            {'video_id':'def123DEF45','published_at':'2026-09-21','theme':'ai','variant':'direct','visibility':'public'},
            {'video_id':'zzz123DEF45','published_at':'2026-09-10','theme':'ai','variant':'direct','visibility':'private'},
            {'video_id':'not-a-valid-id','published_at':'2026-09-10','theme':'ai','variant':'direct','visibility':'public'}
        ]
        out=validate_mapping({'videos':rows},now,['ai'])
        self.assertEqual(len(out),1)
        self.assertEqual(out[0]['video_id'],'abc123DEF45')
    def test_balanced_samples_refuse_early_adaptation(self):
        observations=[v('ai','direct',retention=120)]*3 + [v('open','question',retention=20)]*2
        self.assertEqual(aggregate(observations,'theme',100,3).keys(),{'ai'})
    def test_discover_only_matching_public_productions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'state').mkdir()
            (root/'state'/'productions.json').write_text(json.dumps({'productions':[
                {'id':'a','source_url':'https://example.org/a','theme':'ai','variant':'direct'},
                {'id':'b','source_url':'https://example.org/b','theme':'ai','variant':'question'}
            ]}))
            api=FakeYT()
            output=discover_own_public_uploads(root,'test-access',api)
            self.assertEqual(len(output),1)
            self.assertEqual(output[0]['video_id'],'abc123DEF45')
            self.assertEqual(output[0]['visibility'],'public')
            self.assertTrue(all(call[2].get('headers',{}).get('Authorization')=='Bearer test-access'
                for call in api.calls if call[0]=='get'))
    def test_end_to_end_feedback_keeps_private_metrics_out_of_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'state').mkdir()
            (root/'state'/'productions.json').write_text(json.dumps({'productions':[
                {'id':'a','source_url':'https://example.org/a','theme':'ai','variant':'direct'}
            ]}))
            result=learn(root,{'themes':['ai','open']},env=ENV,
                session=FakeYT(),today=date(2026,9,23))
            self.assertEqual(result['status'],'insufficient_comparable_data')
            self.assertEqual(result['measured'],1)
            self.assertNotIn('views',result)
            self.assertNotIn('video_id',result)
            self.assertNotIn('access_token',result)
    def test_exploration_preserved_after_preference(self):
        conf={'themes':['ai','automation','open']}
        pref={'status':'experimental_preference','preferred_theme':'automation',
              'preferred_variant':'direct'}
        normal=datetime(2026,9,23,tzinfo=timezone.utc)
        selections=[editorial_plan(conf,pref,normal+timedelta(days=i))
                    for i in range(9)]
        self.assertGreaterEqual(sum(themes[0]=='automation' for themes,_ in selections),6)
        self.assertTrue(any(themes[0]!='automation' for themes,_ in selections))
    def test_two_variants_produce_distinct_short_writing(self):
        t=Topic('1','A newly released open model for video generation',
                'https://example.org/a','example.org','2026-09-10','ai')
        a=template_story(t,'deesezrxh','question')
        b=template_story(t,'deesezrxh','direct')
        self.assertNotEqual(a['script'],b['script'])
        self.assertEqual(a['variant'],'question')
        self.assertEqual(b['variant'],'direct')

if __name__=='__main__':
    unittest.main()
