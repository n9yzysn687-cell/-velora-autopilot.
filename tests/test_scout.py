"""V3.1 Scout: synthetic source fixtures, no assumed live-trend data."""
from datetime import datetime, timezone, timedelta
import unittest
from autopilot.source import (
    Topic, normalize_topic, select_topic, similar_title, canonical_url,
    evidence_gate, safe_public_url, rank,
)

NOW=datetime(2026,9,23,18,tzinfo=timezone.utc)
def hit(ident,title,domain='github.com',age=3,points=25,url=None):
    return {'objectID':ident,'title':title,
            'url':url or 'https://'+domain+'/article/'+ident,
            'created_at':(NOW-timedelta(hours=age)).isoformat(),
            'points':points}

class FakeResponse:
    def __init__(self,payload):self.payload=payload
    def raise_for_status(self):return None
    def json(self):return self.payload

class FakeSources:
    def __init__(self,hits,releases=None):
        self.hits=hits;self.releases=releases or []
        self.calls=[]
    def get(self,url,**kwargs):
        self.calls.append((url,kwargs))
        if 'releases' in url:return FakeResponse(self.releases)
        return FakeResponse({'hits':self.hits})

class ScoutTests(unittest.TestCase):
    def test_excludes_social_and_generic_blog(self):
        for domain in ('blogspot.com','abc.blogspot.com','medium.com','x.com'):
            self.assertIsNone(normalize_topic(hit('a','New open source AI video engine',domain), 'ai'))
    def test_requires_safe_public_https(self):
        for url in ('http://github.com/a','https://127.0.0.1/data',
                    'https://169.254.169.254/','https://user:pass@example.com/',
                    'https://service.local/x','https://localhost/a',
                    'https://example.org:8443/data'):
            self.assertFalse(safe_public_url(url),url)
    def test_canonicalizes_campaign_tracking(self):
        self.assertEqual(canonical_url('https://EXAMPLE.org/a/?utm_source=one&ref=2&v=5#x'),
                         'https://example.org/a?v=5')
    def test_non_substantive_off_topic_rejected(self):
        t=normalize_topic(hit('a','Your ultimate guide for 2026',
                             domain='example.org',points=90),'ai')
        self.assertEqual(evidence_gate(t,NOW),'generic_or_off_topic_headline')
    def test_stale_engagement_does_not_revive_old_story(self):
        t=normalize_topic(hit('a','New open source AI video engine',
                             age=200,points=500),'ai')
        self.assertEqual(evidence_gate(t,NOW),'old_discovery_signal')
    def test_bad_trend_data_rejected(self):
        t=normalize_topic(hit('a','Open source AI video framework',
                             domain='example.org',points=1),'ai')
        self.assertEqual(evidence_gate(t,NOW),'insufficient_public_interest_signal')
    def test_rank_not_first_seen_and_audit(self):
        first=hit('first','New open source AI video model',domain='example.org',points=5)
        better=hit('better','ComfyUI open source AI video workflow',domain='github.com',points=100)
        sources=FakeSources([first,better])
        winner,audit=select_topic(['intelligence artificielle'],set(),
                                  session=sources,now=NOW)
        self.assertEqual(winner.id,'better')
        self.assertEqual(audit['chosen']['origin'],'hacker_news')
        self.assertGreaterEqual(audit['candidates_examined'],2)
        self.assertTrue(audit['not_verified_claims'])
        self.assertGreaterEqual(len(audit['queried']),1)
    def test_semantic_memory_blocks_rephrased_story(self):
        old={'source_title':'ComfyUI launches open source AI video workflows',
             'source_url':'https://github.com/something/old'}
        hits=[hit('one','ComfyUI launches open source AI video workflows',
                  url='https://github.com/something/new'),
              hit('two','LTX AI video runtime supports new workflow',points=40)]
        winner,audit=select_topic(['intelligence artificielle'],set(),
                                  FakeSources(hits),history=[old],now=NOW)
        self.assertEqual(winner.id,'two')
        self.assertGreater(audit['rejections'].get('similar_previous_story',0),0)
    def test_url_tracking_difference_not_a_new_story(self):
        old={'source_title':'A different video headline',
             'source_url':'https://github.com/org/ai?utm_source=email'}
        h=hit('one','New open source AI video research study',
              url='https://github.com/org/ai?utm_medium=mail')
        winner,audit=select_topic(['intelligence artificielle'],set(),
                                  FakeSources([h,hit('two','New LTX video model published',points=30)]),
                                  history=[old],now=NOW)
        self.assertEqual(winner.id,'two')
        self.assertGreaterEqual(audit['rejections']['repeated_source_url'],1)
        self.assertGreaterEqual(audit['rejections'].get('same_search_result',0),1)
    def test_fallback_to_verified_official_release_entry(self):
        release={'draft':False,'prerelease':False,'html_url':
                 'https://github.com/comfyanonymous/ComfyUI/releases/tag/v0.9.0',
                 'tag_name':'v0.9.0',
                 'published_at':(NOW-timedelta(days=1)).isoformat()}
        winner,audit=select_topic(['outils open source'],set(),
                                  FakeSources([],releases=[release]),now=NOW)
        self.assertEqual(winner.origin,'github_release')
        self.assertEqual(winner.domain,'github.com')
        self.assertEqual(audit['gate'],'SOURCE_DISCOVERY_ONLY_HUMAN_FACT_CHECK_REQUIRED')
    def test_all_rejected_halts_instead_of_filler(self):
        old=hit('one','Open source AI video generation old',age=600)
        with self.assertRaisesRegex(RuntimeError,'do not generate filler'):
            select_topic(['intelligence artificielle'],set(),
                         FakeSources([old]),now=NOW)
    def test_reports_social_signal_not_youtube_analytics(self):
        t=normalize_topic(hit('one','Open source AI video model',points=19),'ai')
        self.assertEqual(t.signal,19)
        self.assertEqual(t.origin,'hacker_news')
        self.assertGreater(rank(t,NOW),0)
    def test_similarity_is_order_invariant(self):
        self.assertGreater(similar_title('Wan AI video generator published',
                                         'Published Wan video AI generator'),.90)

if __name__=='__main__':unittest.main()
