# Generated walkthrough video

Produces `out/walkthrough.mp4`: a narrated (~6 min) tour of the app and code.

How it works: `narration.json` holds one script per scene. `tts.ps1` renders it with the
offline Windows voice, and `record.mjs` drives Chrome with Playwright, recording each
scene for at least as long as its narration. ffmpeg (via `ffmpeg-static`) then lays
each clip at its scene's start time and muxes everything into an MP4.

```bash
# needs the app running at APP_URL (default http://127.0.0.1:8000/) and Google Chrome
npm install
powershell -NoProfile -ExecutionPolicy Bypass -File tts.ps1 -OutDir out/audio
node record.mjs            # FAST=1 for a quick dry run with one screenshot per scene
```

The same narration is in `docs/LOOM_SCRIPT.md` as a script for recording live in Loom.
