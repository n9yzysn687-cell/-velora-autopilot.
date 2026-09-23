from pathlib import Path
import tempfile
import unittest
from autopilot.free_gpu import replace_placeholders,find_mp4,generate_free_clip

class FakeResponse:
    def __init__(self,obj):self.obj=obj
    def raise_for_status(self):pass
    def json(self):return self.obj
class Http:
    def __init__(self,hardware):self.hardware=hardware
    def get(self,*args,**kwargs):return FakeResponse({'runtime':{'hardware':self.hardware},'private':False})

class FreeGpuTests(unittest.TestCase):
    def test_placeholders(self):
        self.assertEqual(replace_placeholders({'prompt':'x {{PROMPT}}','seed':0},'shot'),{'prompt':'x shot','seed':0})
    def test_recognizes_gradio_video_shape(self):
        self.assertEqual(find_mp4({'video':'/tmp/output.mp4','subtitles':None}),'/tmp/output.mp4')
    def test_refuses_a_non_zero_gpu(self):
        import os
        with tempfile.TemporaryDirectory() as folder:
            old=os.environ.get('HF_TOKEN');os.environ['HF_TOKEN']='test-token'
            try:
                with self.assertRaisesRegex(RuntimeError,'not a public ZeroGPU'):
                    generate_free_clip({'free_hf_space':'x/y','free_hf_api_name':'/predict','free_hf_input_json':{'prompt':'{{PROMPT}}'}},'shot',Path(folder)/'x.mp4',Http('a10g-large'))
            finally:
                if old is None:os.environ.pop('HF_TOKEN',None)
                else:os.environ['HF_TOKEN']=old

if __name__=='__main__':unittest.main()
