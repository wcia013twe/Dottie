# Local book narration

This optional build step turns an edited narration script into local passage audio. It uses the
[ElevenLabs create-speech API](https://elevenlabs.io/docs/api-reference/text-to-speech/convert),
requesting 24 kHz PCM and wrapping it in standard mono, 16-bit WAV files. No SDK, cloud deployment,
Databricks table, or browser API key is needed. The build requires an ElevenLabs key and an accessible
voice; playback needs only the generated local files.

## Full Peter Rabbit book

The included edition has 28 clips: an original, newly written narrator introduction on the title
page, followed by 27 passages of Beatrix Potter's original story. The reader opens at the title
(chapter 2, page 1); “Once upon a time” is page 2, with its own matching recording. Publication
front matter moves into a separate Publication details section. The EPUB, cover and license remain
intact. Existing bookmarks are backed up in `previousReadingPosition` during the one-time move to
the title; later visits resume normally. Stable `page-03` through `page-29` audio IDs retain their
original source numbering, rather than the new displayed page numbers.

Regenerate the editable script and audio with:

```sh
npm run prepare:narration:peter
npm run build:narration -- story_mode/narration/peter-rabbit.json
```

The edition-specific extractor follows illustration boundaries; it is not a general EPUB importer.
On 2026-10-11, all 28 clips were regenerated using the updated local voice setting. Audio stays
local and git-ignored; the full narration script is versioned. Credentials and generated voice
metadata are not committed.

## Build and play

1. Copy `peter-rabbit.example.json` and edit the script. The example contains **two excerpts**, not
   a complete audiobook. Use the reader's book ID (`builtin-peter-rabbit` for the included book).
2. Put your credentials in the repository-root `.env` (outside the served `web/` directory):

   ```dotenv
   ELEVENLABS_API_KEY=your-api-key
   ELEVENLABS_VOICE_ID=your-voice-id
   ```

   See `env.example`. The wrapper loads these two settings automatically; `.env` is git-ignored.
   Existing shell variables take precedence, and `--voice-id` overrides both. Quoted values, comments
   and an optional `export` prefix are supported; shell commands and variable expansion are never
   executed. Keep the key out of scripts and manifests.
3. Preview work without credentials or network calls:

   ```sh
   npm run build:narration -- story_mode/narration/peter-rabbit.example.json --voice-id preview --dry-run
   ```

4. With the actual voice ID configured, build:

   ```sh
   npm run build:narration -- story_mode/narration/peter-rabbit.example.json
   python3 scripts/serve.py
   ```

Open the book. A **Recorded narration** audio control appears only on a uniquely matched passage.
Narration starts automatically when a matched page opens, stops automatic page turning, and pauses
on navigation or teacher interaction. If the browser blocks autoplay, the player prompts the reader
to press play. Page turns include a short, locally synthesized paper rustle. Native audio controls
remain available for pausing and volume adjustment.
The existing decision-preparation request starts when the passage opens, so it can run while audio
plays. There is no model call or ElevenLabs request at playback time. Audio does not automatically
advance the story or approve a teaching activity. Pages without audio remain readable.

The default output is `web/learn/narration/<book_id>/`. Generated files are git-ignored. Use
`--output-root` for another local location; the built-in reader only loads the default web location.
`--voice-id` overrides the environment. Back up scripts and generated audio together if needed.

## Local format 1.0

The source has exactly `schema_version`, `book_id`, `script_version`, `model_id`, `voice_settings`,
and `passages`. Each passage has a unique safe `id`, literal `match_text` from the visible book, and
`text` containing the actual narration. IDs and versions use letters, digits, underscores and hyphens.
Match text is normalized for case and whitespace in the reader. Ambiguous matches play nothing.
Use a distinct snippet per displayed passage; keep clips aligned with the page boundaries in this
reader. Recheck matches after editing the book. This wrapper does not extract or paginate ebooks. Prepare page-aligned script entries first, then
generate one clip per entry and reuse it. It does not generate one long audiobook and cut it afterward.

Choose voice settings explicitly in the script: stability, similarity_boost and style between 0–1,
and use_speaker_boost as a boolean. Each script passage is limited to 4,000 characters; split longer
passages before building. This is a local wrapper limit, not a claim about every provider model.

The published `manifest.json` preserves the source metadata and adds `voice_id`, `source_format`,
`format`, and passage fields `audio` (relative filename), `duration_seconds`, and `cache_key`.
Duration is calculated from the WAV samples. The format is consumed by `web/learn/narration.js`;
unsupported versions, foreign book IDs, ambiguous matches and unsafe audio paths are rejected.
This is an additive local asset format; existing deployed decision and learning schemas are unchanged.

Audio filenames include a hash of narration text, voice ID, model ID, settings and output format.
Unchanged valid WAVs are reused. Editing text or voice settings generates new files; changing only
script_version or matching text reuses the existing audio. Old files are retained so an interrupted
build cannot break an existing manifest. Run one build per book at a time. Files are immutable cache
artifacts: to regenerate a clip, remove its generated WAV or change the relevant generation inputs.

Each audio file is written atomically; the manifest is replaced only after all passages succeed.
A failed build leaves the previous playable manifest intact and preserves completed clips for retry.
No automatic retry loop can repeatedly call the paid provider. Provider errors omit response bodies
and credentials. The wrapper sends narration text and voice settings, never student history.

## Verification

`npm run check:narration` covers request shape, cache reuse/invalidation, malformed data, missing
credentials, interrupted builds, corrupt files, manifest matching and safe local paths. Browser
verification used synthetic silence to check decoding, duration and pause-on-navigation. The full Peter Rabbit script has also been generated through the live ElevenLabs endpoint and
checked for page alignment and browser playback. Pronunciation and performance still merit a human
listening review.
