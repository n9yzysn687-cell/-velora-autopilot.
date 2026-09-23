# VELORA AUTOPILOT v0.1 · deesezrxh

**Runs unattended on GitHub Actions, including when your iPhone is off.** This is an actual working CPU motion-design pipeline. It is **not** a Seedance/Wan generator, an autonomous YouTube uploader, or an unlimited free GPU service. Only original editorial video drafts are produced. No payments, API credits, or public uploads occur.

## What happens each day

At 07:17 UTC the scheduled workflow wakes up in a fresh GitHub Linux runner:

`discover topic with attributable link → check duplicate IDs → write sourced editorial brief → generate 6 original motion-design scenes → generate French narration → FFmpeg assemble vertical H.264 MP4 → duration/file QA → upload MP4 as Actions artifact → persist state to repository → wait until next day`.

It stops at **1 Short a day**, **max €0 in paid inference**, retries an unusable source at most twice, and refuses to publish automatically. If no fresh article is found, or an external service fails, it records the reason and waits for the next scheduled run. `GEMINI_API_KEY` is optional; with no key it writes a conservative template-style commentary. If you choose Gemini in config, check your account's current free limits; 429 stops and never switches to paid credits. The voice normally uses online Google Translate speech (gTTS); if that is unavailable it tries offline `espeak-ng`, whose voice sounds less natural.

## Start from iPhone

1. In GitHub, create a **NEW public repository** just for this bot (do not add it to an existing unrelated repository). Never put passwords, API keys, tokens, private scripts, private media or personal information in public commits.
2. Upload **all the contents of this folder**, including the **hidden `.github/workflows/autopilot.yml`** path. GitHub's website may require desktop mode on iPhone for nested folder upload. A code editor connected to GitHub or GitHub's browser file editor can create individual files. GitHub's native ZIP upload does not unpack a ZIP into a repo; uploading only this archive is not activation.
3. Open **Actions → VELORA Autopilot → Run workflow** once. On a successful run open its artifact `deesezrxh-production-...` to download `short.mp4`, `story.json`, and `manifest.json`.
4. Scheduled runs will then take over (07:17 UTC ≈ 09:17 in Belgium in summer, 08:17 in winter). GitHub may delay scheduled runs and may disable schedules in public repos after 60 days of inactivity. Inspect Actions occasionally.
5. Tune `config.json`: channel, themes, cadence and script provider. To use an optional Gemini free-tier key, save it ONLY as GitHub Actions repository **Secret `GEMINI_API_KEY`**; set `providers.script` to `gemini` and set GitHub Actions variable `GEMINI_FREE_ONLY_CONFIRMED=true` **only if your Gemini project is genuinely free-only, without linked billable fallback**. An API key by itself never guarantees free requests. Do not paste secrets into files or chat.

**GitHub Actions cost:** Standard GitHub-hosted runners in public repositories are free subject to GitHub's usage policies, but artifact storage has limits. Private repositories have metered free-minute and artifact quotas. Scheduled jobs are not guaranteed to run at the exact minute. GPU-backed Seedance/Wan models do not run on these CPU runners.

## Control / kill switch

Set `shorts_per_day` to `0` to pause outputs; or use GitHub → Actions → select workflow → Disable workflow. `max_daily_paid_eur: 0` is hard enforced and any positive value is intentionally rejected in this edition. Workflow runs at most one video each launch. Keep `youtube.upload_enabled: false` until account OAuth, source validation, copyright checks and explicit upload approval are integrated.

## Source licensing / commercial use

Original graphics rendered by Pillow, original code in this package licensed MIT. FFmpeg, fonts and optional downstream model weights each have their own licenses. Source links are **attributions for review, not permission to copy footage or full articles**. Do not make claims about the articles without opening and checking them. No fake metrics, no fabricated dashboards, no copyrighted music embedded. gTTS uses an unofficial speech frontend and is not a production SLA; use a licensed provider for commercial reliability.

## Optional real open-model scene: Hugging Face ZeroGPU

After confirming a particular public Space supports **text → video** through its exposed API, set `providers.video` to `hf_zerogpu` in `config.json`, configure `providers.free_hf_space` (`owner/name`), `providers.free_hf_api_name` (`/actual_endpoint`), and `providers.free_hf_input_json` (its **actual parameter names**, with `{{PROMPT}}` in the prompt value). Add your own **HF_TOKEN** as a GitHub Actions secret, never a file. The agent refuses non-public or non-ZeroGPU hardware, quota failure, missing token and incompatible output instead of falling back to paid generation. It imports one real MP4 as the 4th scene. Model availability, licenses and the quota for your own account must be checked; **no generic Space settings are invented here**.

Example only, NOT a ready-made configuration for every Space:

`"free_hf_input_json": {"prompt": "{{PROMPT}}", "num_inference_steps": 4}`

## Interfaces for VELORA

The bot emits `manifest.json` plus `story.json`. You can import/copy them into VELORA Channel Studio. `manifest.json` explicitly marks human review required. Your existing VELORA web app remains separate: there is **no live YouTube OAuth or hosted GPU connection in this ZIP**. A future bridge can sync drafts, results, and approval states across the two systems.

## Offline check

With Python 3.11+ and FFmpeg: `pip install -r requirements.txt && python -m unittest discover -s tests -v`.

## ZeroGPU / Seedance integration boundary

Hugging Face documents agent access to Spaces using a per-user HF_TOKEN and `/agents.md` + `/gradio_api/info`. To add a GPU model to the loop, choose a Space with an official API, inspect its input schema, authenticate with **your own token**, respect quota/errors, and store output as a new scene file. You need to wire the specific Space input/output contract; **there is no universal `Seedance free API key` and no quota bypass in this repository**.

Official reference: https://huggingface.co/docs/hub/spaces-agents
