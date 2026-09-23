"""YouTube publishing safety tests; all Google API responses are synthetic."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from autopilot.youtube import (
  check_oauth_settings,expected_channel,make_marker,validate_manifest,
  upload_one,resumable_insert,CHANNEL_ID
)

ID='UC'+'A'*22
VID='B'*11
PID='20260923T210000Z'
URL='https://github.com/comfyanonymous/ComfyUI/releases/tag/v0.9.0'
def production(origin='github_release',provider='template'):
  return {'id':PID,'source_url':URL,'source_type':origin,
          'script_type':provider,'status':'DRAFT_REVIEW_REQUIRED'}
def config(mode='disabled'):
  return {'channel_name':'deesezrxh','youtube':{
    'upload_enabled':True,'public_mode':mode,'privacy':'private'}}
def creds(channel=ID):
  return {'YT_CLIENT_ID':'client','YT_CLIENT_SECRET':'secret',
          'YT_REFRESH_TOKEN':'refresh','YT_CHANNEL_ID':channel}
def write_film(root,prod):
  dest=root/'output'/PID
  dest.mkdir(parents=True)
  (dest/'short.mp4').write_bytes(b'A'*70_000)
  story={'title':'ComfyUI official release explained','script':' '.join(['test']*41),
         'description':'Official release link '+URL,'source_url':URL,
         'verified':False}
  (dest/'manifest.json').write_text(json.dumps({
    'channel':'deesezrxh','public_youtube_upload':False,
    'paid_video_generation':False,
    'research':{'fact_check_required':True},
    'story':story,
    'production':{'duration_seconds':22.5,
                  'visual_type':'original editorial motion design; NOT AI video'}
  }))
  (dest/'storyboard.json').write_text(json.dumps({
    'director_version':'V3.2','source':{'url':URL},'scenes':[
     {'layout':k} for k in ['hero','split','chapters','steps','source']]
  }))
  (root/'state').mkdir(exist_ok=True)
  (root/'state'/'productions.json').write_text(json.dumps({
    'productions':[prod]}))
  return dest,story

class Reply:
  def __init__(self, data=None,headers=None):
    self.data=data or {};self.headers=headers or {}
  def raise_for_status(self):pass
  def json(self):return self.data

class GoogleFake:
  def __init__(self,privacy='private',exists=False,account=ID):
    self.privacy=privacy;self.exists=exists;self.account=account
    self.posts=[];self.gets=[];self.puts=[]
  def post(self,url,**kw):
    self.posts.append((url,kw))
    if url.endswith('/token'):return Reply({'access_token':'access'})
    if '/upload/youtube/' in url:
      return Reply({},headers={'Location':'https://www.googleapis.com/upload/youtube/v3/videos?upload_id=TEST'})
    raise AssertionError(url)
  def get(self,url,**kw):
    self.gets.append((url,kw))
    if url.endswith('/channels'):
      return Reply({'items':[{'id':self.account,
        'contentDetails':{'relatedPlaylists':{'uploads':'UUfixture'}}}]})
    if url.endswith('/playlistItems'):
      return Reply({'items':[{'contentDetails':{'videoId':VID}}] if self.exists else []})
    if url.endswith('/videos'):
      if self.exists or kw.get('params',{}).get('id')==VID:
        return Reply({'items':[{'id':VID,'snippet':{
          'description':'Sample description\nVELORA-ID: '+PID},
          'status':{'privacyStatus':self.privacy}}]})
      return Reply({'items':[]})
    raise AssertionError(url)
  def put(self,url,**kw):
    self.puts.append((url,kw))
    return Reply({'id':VID})

class YouTubeSafety(unittest.TestCase):
  def test_disabled_or_missing_credentials_do_not_upload(self):
    self.assertEqual(check_oauth_settings(
      {'youtube':{'upload_enabled':False}},{} )['status'],'upload_disabled')
    self.assertEqual(check_oauth_settings(config(),{})['status'],
                     'awaiting_owner_oauth_secrets')
    e=creds();e.pop('YT_CHANNEL_ID')
    self.assertEqual(check_oauth_settings(config(),e)['status'],
                     'awaiting_owner_channel_id')
  def test_channel_lock_blocks_cross_account(self):
    with tempfile.TemporaryDirectory() as d:
      root=Path(d);write_film(root,production())
      http=GoogleFake(account='UC'+'X'*22)
      with patch('autopilot.youtube.verify_mp4'):
        with self.assertRaisesRegex(RuntimeError,'channel mismatch'):
          upload_one(root,config(),creds(),http)
      self.assertEqual(http.puts,[])
  def test_private_default_with_zero_permission_to_public(self):
    with tempfile.TemporaryDirectory() as d:
      root=Path(d);write_film(root,production())
      http=GoogleFake()
      with patch('autopilot.youtube.verify_mp4'):
        result=upload_one(root,config(),creds(),http)
      self.assertEqual(result['status'],'uploaded_private')
      self.assertNotIn(VID,json.dumps(result))
      self.assertNotIn(VID,(root/'state/productions.json').read_text())
      self.assertEqual(http.posts[1][1]['json']['status']['privacyStatus'],'private')
  def test_preflight_refuses_duplicate_second_upload(self):
    with tempfile.TemporaryDirectory() as d:
      root=Path(d);write_film(root,production())
      http=GoogleFake(exists=True)
      with patch('autopilot.youtube.verify_mp4'):
        result=upload_one(root,config(),creds(),http)
      self.assertTrue(result['duplicate_prevented'])
      self.assertEqual(len(http.posts),1)  # refresh, no upload POST
      self.assertEqual(http.puts,[])
  def test_public_requires_release_source_template_and_rights(self):
    with tempfile.TemporaryDirectory() as d:
      root=Path(d);write_film(root,production(origin='hacker_news'))
      with patch('autopilot.youtube.verify_mp4'):
        with self.assertRaisesRegex(RuntimeError,'third-party'):
          upload_one(root,config('official_releases_only'),
                     dict(creds(),YT_ALLOW_PUBLIC_AUTOMATION='I_APPROVE_PUBLIC_UPLOADS',
                          YT_MEDIA_RIGHTS_APPROVED='I_REVIEWED_RIGHTS'),
                     GoogleFake())
  def test_public_requires_separate_media_rights_attestation(self):
    with tempfile.TemporaryDirectory() as d:
      root=Path(d);write_film(root,production())
      with patch('autopilot.youtube.verify_mp4'):
        with self.assertRaisesRegex(RuntimeError,'rights'):
          upload_one(root,config('official_releases_only'),
                    dict(creds(),YT_ALLOW_PUBLIC_AUTOMATION='I_APPROVE_PUBLIC_UPLOADS'),
                    GoogleFake())
  def test_google_forces_private_even_when_public_requested(self):
    with tempfile.TemporaryDirectory() as d:
      root=Path(d);write_film(root,production())
      e=dict(creds(),YT_ALLOW_PUBLIC_AUTOMATION='I_APPROVE_PUBLIC_UPLOADS',
             YT_MEDIA_RIGHTS_APPROVED='I_REVIEWED_RIGHTS')
      http=GoogleFake(privacy='private')
      with patch('autopilot.youtube.verify_mp4'):
        result=upload_one(root,config('official_releases_only'),e,http)
      self.assertEqual(http.posts[1][1]['json']['status']['privacyStatus'],'public')
      self.assertEqual(result['status'],'uploaded_private')
      self.assertNotIn(VID,json.dumps(result))
  def test_public_in_verified_project_records_recoverable_url(self):
    with tempfile.TemporaryDirectory() as d:
      root=Path(d);write_film(root,production())
      e=dict(creds(),YT_ALLOW_PUBLIC_AUTOMATION='I_APPROVE_PUBLIC_UPLOADS',
             YT_MEDIA_RIGHTS_APPROVED='I_REVIEWED_RIGHTS')
      with patch('autopilot.youtube.verify_mp4'):
        result=upload_one(root,config('official_releases_only'),e,
                          GoogleFake(privacy='public'))
      self.assertEqual(result['status'],'published_public')
      self.assertTrue(result['url'].endswith(VID))
  def test_wrong_upload_location_blocked(self):
    with tempfile.TemporaryDirectory() as d:
      file=Path(d)/'test.mp4';file.write_bytes(b'a'*60_000)
      class Evil:
        def post(self,*args,**kw):
          return Reply(headers={'Location':'https://evil.example/upload'})
      with self.assertRaisesRegex(RuntimeError,'unsafe endpoint'):
        resumable_insert(file,{},'token',Evil())
if __name__=='__main__':unittest.main()
