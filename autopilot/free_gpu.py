"""Optional authenticated, quota-limited public Hugging Face ZeroGPU Space adapter.

Not a generic Seedance endpoint. Users must inspect their chosen Space's
agents.md / OpenAPI and configure its ACTUAL argument names and endpoint.
"""
from __future__ import annotations
import os
import shutil
from pathlib import Path
import requests


def replace_placeholders(obj, prompt: str):
    if isinstance(obj,str):
        return obj.replace('{{PROMPT}}',prompt)
    if isinstance(obj,list):
        return [replace_placeholders(x,prompt) for x in obj]
    if isinstance(obj,dict):
        return {k:replace_placeholders(v,prompt) for k,v in obj.items()}
    return obj


def find_mp4(result):
    if isinstance(result,str) and result.lower().split('?')[0].endswith('.mp4'):
        return result
    if isinstance(result,dict):
        for key in ('video','path','url','name'):
            if key in result:
                found=find_mp4(result[key])
                if found:return found
    if isinstance(result,(tuple,list)):
        for entry in result:
            found=find_mp4(entry)
            if found:return found
    return None


def generate_free_clip(settings:dict,prompt:str,output:Path,session=None):
    repo=settings.get('free_hf_space','').strip()
    endpoint=settings.get('free_hf_api_name','').strip()
    mapping=settings.get('free_hf_input_json') or {}
    token=os.environ.get('HF_TOKEN','').strip()
    if not (repo and endpoint and mapping and token):
        raise RuntimeError('ZeroGPU needs Space ID, actual API endpoint/schema, and HF_TOKEN. No unauthenticated mass calls.')
    if not (repo.count('/')==1 and all(part.replace('-','').replace('_','').isalnum() for part in repo.split('/'))):
        raise ValueError('Expected public Hugging Face Space ID owner/space.')
    if not endpoint.startswith('/') or len(endpoint)>100:
        raise ValueError('Space endpoint must look like /predict')
    http=session or requests.Session()
    resp=http.get('https://huggingface.co/api/spaces/'+repo,
                  headers={'Authorization':'Bearer '+token},timeout=20)
    resp.raise_for_status()
    info=resp.json()
    hardware=str((info.get('runtime') or {}).get('hardware') or '').lower()
    if not hardware.startswith('zero') or info.get('private',False):
        raise RuntimeError('Refusing API call: Space is not a public ZeroGPU Space. No paid GPU fallback.')
    try:
        from gradio_client import Client
    except ImportError as error:
        raise RuntimeError('Install optional requirements-zerogpu.txt first.') from error
    client=Client(repo,token=token,verbose=False)
    kwargs=replace_placeholders(mapping,prompt)
    if not isinstance(kwargs,dict):
        raise ValueError('Space API input settings must be a JSON object.')
    result=client.predict(api_name=endpoint,**kwargs)
    location=find_mp4(result)
    if not location:
        raise RuntimeError('Space returned no recognizable MP4; inspect its actual API output schema.')
    output.parent.mkdir(parents=True,exist_ok=True)
    if location.startswith('https://'):
        with http.get(location,stream=True,timeout=90) as media:
            media.raise_for_status()
            with output.open('wb') as f:
                for chunk in media.iter_content(1024*1024):
                    f.write(chunk)
    else:
        source=Path(location)
        if not source.is_file():
            raise RuntimeError('Space media output was not downloaded as a local file.')
        shutil.copyfile(source,output)
    if output.stat().st_size<10000:
        raise RuntimeError('Space returned empty media.')
    return output
