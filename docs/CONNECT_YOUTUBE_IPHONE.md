# Connect deesezrxh to VELORA Autopilot (iPhone, owner only)

VELORA v3.3 supports **real YouTube OAuth, channel locking, private staging, upload recovery, API-confirmed visibility and read-only analytics**. It is not connected until **you** authorize Google and save credentials in **GitHub Actions Secrets**, never a public file or ChatGPT message.

## What is active by default?

- `youtube.upload_enabled=true`, but without owner OAuth credentials **no video leaves GitHub**.
- `youtube.public_mode=disabled`: after owner connection, successful new films upload **PRIVATE** to YouTube, not public.
- Real audience metrics start only after you publish a video and the API has comparable observation windows.
- Public automation is separately locked; see below.

## On iPhone, connect your own Google/YouTube account

1. In Google Cloud Console (console.cloud.google.com), create a project you own. Enable **YouTube Data API v3** and **YouTube Analytics API** in *APIs & Services > Library*. Check quota and Google billing settings yourself.
2. Under Google Auth Platform configure your OAuth consent audience. Create an **OAuth client of type Web application** with authorized redirect URI `https://developers.google.com/oauthplayground`. An OAuth application left in **Testing** can have its refresh token expire in seven days. Production may require Google's verification.
3. Open Google's [OAuth 2.0 Playground](https://developers.google.com/oauthplayground/) in Safari. In its gear/options panel tick **Use your own OAuth credentials** and enter your own project's client ID and secret. Ensure **Access type Offline**, force consent, then request these **exact scopes**:

   `https://www.googleapis.com/auth/youtube.upload`
   
   `https://www.googleapis.com/auth/youtube.readonly`
   
   `https://www.googleapis.com/auth/yt-analytics.readonly`

   Select the Google account / **Brand Account that owns deesezrxh**. Exchange the authorization code for a refresh token. Never include tokens in a shareable Playground link. Playground tokens issued without your own OAuth credentials may be short-lived/revoked.
4. Open this repository's [Actions secrets settings](https://github.com/n9yzysn687-cell/-velora-autopilot./settings/secrets/actions). Add the exact three **repository secrets** `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`. Their *values* are your own Cloud OAuth client ID, client secret and refresh token respectively.
5. Add repository **variable** `YT_CHANNEL_ID` whose value is the real YouTube channel ID starting `UC...`, **not** `@deesezrxh`. Find it in [YouTube's channel advanced settings](https://www.youtube.com/account_advanced) while signed into the intended channel. The program refuses a channel mismatch.
6. Visit [GitHub Actions](https://github.com/n9yzysn687-cell/-velora-autopilot./actions), open **VELORA Autopilot**, choose **Run workflow**. Its **Check YouTube connection** job checks identity without uploading. Never share OAuth values, upload private video IDs, job environment settings, or screenshots containing secrets.

After successful connection, at most one new Short/day is delivered to the **matching channel as Private**. Look in YouTube Studio to review it. A file/source/voice/format failure stops the upload.

## Public autonomous publishing: separate owner-controlled launch

The program must not publish arbitrary HN news as verified. To enable limited, owner-approved public mode **after successfully testing private uploads**, three independent switches must be configured:

- `config.json` → `youtube.public_mode`: `official_releases_only`
- Actions variable `YT_ALLOW_PUBLIC_AUTOMATION`: `I_APPROVE_PUBLIC_UPLOADS`
- Actions variable `YT_MEDIA_RIGHTS_APPROVED`: `I_REVIEWED_RIGHTS` (only set after checking rights for **all automatically used** original artwork, TTS voice, music/footage and their license terms).

The public mode only accepts the primary official release source plus source-constrained **template** script and validated original motion design. A third-party or unverified news story is blocked from going public. A separate **realistic synthetic-media disclosure** flag is sent to YouTube. Never treat this checklist as a legal or factual guarantee. YouTube may enforce **private uploads** from an API project created after July 28, 2020 that has not passed the required YouTube API Services audit; VELORA reads the *actual* YouTube visibility after upload instead of claiming successful publication.

**Once activated, public posting is unattended; you take responsibility for the channel.** Do not enable it if you need approval for each individual Short. Keep default private during testing.

## Repeatable operating cycle

`Scout → source gate → script → Director storyboard → voice/MP4 & FFprobe QA → OAuth + owner channel lock → upload with exact VELORA-ID → YouTube status readback → public-only YouTube Analytics on comparable first-seven-day windows → cautious experimental preference → Scout next cycle`.

The upload ID marker protects against duplicates after uncertain network retries. A Google error, privacy/rights mismatch, no suitable source, failed FFprobe, missing owner authorization or excessive duration blocks the relevant stage. No external video-model payments or unverified public YouTube actions are invoked automatically.

*Google references:* YouTube Data API [videos.insert](https://developers.google.com/youtube/v3/docs/videos/insert), [videos.list](https://developers.google.com/youtube/v3/docs/videos/list), [Analytics channel reports](https://developers.google.com/youtube/analytics/channel_reports), and [OAuth Playground](https://developers.google.com/oauthplayground/).
