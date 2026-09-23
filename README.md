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


## Feedback loop v0.2 · YouTube data → next production

This edition distinguishes **render QA** from actual **audience performance**. The bot never invents view counts, watch times, subscription metrics or YouTube "trends". Before a YouTube owner grants read-only access, `state/feedback.json` deliberately says `awaiting_youtube_readonly_oauth`; the existing free daily draft loop still works.

Once an authorized account is connected, each run uses YouTube Data API to discover *your own public videos*, links them only to VELORA productions whose **exact source URL** appears in the published description, and obtains YouTube Analytics for each video's *first seven days*. Video IDs for private or unlisted uploads, access/refresh tokens and raw per-video analytics are **never committed** to this public repository. The published description must retain the source URL generated in `story.json` for automatic matching. Recent uploads need at least nine days to mature, and only the latest 50 channel uploads are searched each day. You can optionally provide public video mappings in `data/published.json`.

**Owner connection, not currently configured:** enable YouTube Data API v3 and YouTube Analytics API for a Google Cloud OAuth client; authorize the channel owner with *read-only* scopes `https://www.googleapis.com/auth/youtube.readonly` and `https://www.googleapis.com/auth/yt-analytics.readonly`. Save three values as **GitHub Actions repository secrets** named `YT_CLIENT_ID`, `YT_CLIENT_SECRET` and `YT_REFRESH_TOKEN`. Never paste them in an issue, README, public GitHub file or chat. Google OAuth consent and token creation require your own explicit account authorization, and the agent cannot generate or infer these secrets. See [Google's YouTube Analytics authentication guide](https://developers.google.com/youtube/analytics/authorization).

The comparison uses the same seven-day exposure window, a minimum of 100 views for each included video and at least three eligible videos **per option**. It tests two editorial openings (`question` and `direct`) and channel theme categories. Only if the measured comparison shows the configured minimum score gap does `state/feedback.json` save a provisional preference. VELORA explores another option on roughly one third of days to keep testing new ideas. This is a heuristic for controlled iteration, **not proof of causation or a forecast**. The public file contains only aggregate experimental preferences and sample counts, not detailed YouTube measurements.

`state/productions.json` now links each generated MP4 draft to its source URL, theme, opening variant and creation timestamp. The feedback run executes *before* the daily writer; that is the actual data handoff in the loop:

`public upload → read-only analytics → comparable 7-day cohorts → minimum-sample gate → experimental editorial preference → theme + hook planning → new review-only MP4 → repeat`.

No automatic Google posting, paid model fallback, unauthorized scraping, copyright bypass or unlimited free GPU use is enabled. Your channel's real video analytics remain unavailable until OAuth is connected **and the channel has suitable published, sufficiently old videos**. GitHub Actions failures are shown in Actions, with no fake success reporting.


## V3.1 · Scout and production memory (live source code)

The research stage no longer accepts the first search result. It samples up to two English-language Hacker News searches for each configured French editorial theme and public official releases from ComfyUI and Hugging Face Diffusers. It compares eligible candidates based on topical relevance, recency of the **HN submission** (not the source article's original publication date), public HN points as a *discovery signal only*, and a disclosed provenance preference. A GitHub release is checked against the official repository release listing.

The quality gate excludes generic/off-topic headlines, link farms and common user-blog platforms, unsafe URLs, repeated source URLs, semantically repeated headlines, topics already marked completed and stale HN submissions. The bot stops with a documented error if all candidates fail rather than producing filler. **No selection score certifies that an article's claims are true or predicts a video's YouTube results.** Source URLs and factual claims remain review-required.

Each completed film now includes a `research.json` with the selected source, top alternative candidates, input sources, rejected-candidate counts and reason for requiring human fact-checking. The `manifest.json` carries the source origin and source timestamp meaning; `state/productions.json` carries the persistent production memory: theme, hook experiment, source URL, source origin, clip duration, engine and quality selection score. This log is used in future Scout runs to prevent duplicate ideas even if reposted with a new HN ID. The run's results, including source and review status, are also in `state/last_run.json`.

The first automated batch retains the existing free CPU motion-design renderer and human review before publishing. V3.1 improves research and memory, **not yet video-model connection, YouTube OAuth or visual cinematography**. Research score, HN points and selection preferences are not fake YouTube performance measurements.


## V3.2 · Director, visual treatment, scene-time captions

The autonomous job now constructs a deterministic, topic-specific `storyboard.json` from the *actual* narration, source headline, channel identity and variant, before rendering. The count varies from 5 to 8 scenes. The director uses distinct original editorial arrangements (hero, split, chapters, process, spotlight, source card, finale, etc.), topic-seeded accent colors, brand-safe margins, and layout-specific visual prompts. The voice is partitioned without dropping a word. Every scene's **verbatim script excerpt** appears on screen; scene start/end estimates are derived from the measured narration's total duration and word allocations. These are **approximate scene-level captions, not phoneme-level or YouTube-approved subtitles**.

`render.py` creates a different 720×1280 illustration for each scene using Pillow, adds restrained FFmpeg camera movement, records `storyboard.json` with scene timings, and validates the resulting H.264 MP4 duration/resolution. A caller supplying genuine external footage sees it contained with padding, not cropped. The optional ZeroGPU provider remains unconfigured by default. No invented user-interface screenshots, model-demo clips, data visuals, metrics or quotes are presented as authentic. Research/source facts still require review before publication.

The seven-day GitHub Actions production artifact now contains `short.mp4`, `storyboard.json`, `research.json`, `story.json`, `manifest.json`, and PNG scene previews. The final file remains review-only and zero paid-generation budget. The Director supports richer editorial direction without falsely claiming cinematic generative AI output or live YouTube analytics.
