# Browser voice input

The persistent Start listening / Stop listening control uses ElevenLabs Scribe v2 Realtime. The existing Python server must have `ELEVENLABS_API_KEY` in its environment before it starts. Keep the permanent key outside browser files and source control. No automatic .env loading is added.

Start the local server with `python3 scripts/serve.py` after setting the environment variable in the same shell. Open `/learn/` on localhost and choose Start listening. Browser microphone permission is required. The server's same-origin `POST /api/voice-token` returns only a temporary single-use token. Audio streams directly from the browser to ElevenLabs. There is no app-side recording or transcript-history store; the current transcript is displayed in memory. Story responses enter the existing session as unconfirmed text, with teacher confirmation still required.

Implemented commands:

- Open Explore / Practice / Guess / Match / Letters / Story mode / About me; Go home; Go back.
- Repeat / Read this page; Help; Stop listening.
- In Practice: choose a letter, including spoken letter aliases; in Guess: submit a spoken answer through the same form used for typed answers.
- In Match or Explore: choose an object currently listed on screen. Explore retains its separate camera-recognition and physical-device status.
- Start camera / Stop camera.
- In Story mode: Open Peter Rabbit. In a book: Play / Pause / Resume automatic page turns; Next page / Previous page / Continue story. These commands control page turns, not audiobook playback.
- During a live teacher-coach question: speak a response, request Help, or Repeat. The existing `submit_response` tool captures unconfirmed text; it does not grade the learner or record an independent outcome. Continue story skips/resumes via the existing teacher action.

Only final transcripts execute actions. Local silence detection commits each utterance with its captured UI/session context; delayed or duplicate responses cannot borrow a newer context. Actions use existing controls, including disabled-state checks and server revision validation. Microphone audio is replaced by silence while browser speech output plays, and transcript dispatch is blocked. Hidden tabs stop capture. Disconnects and API errors close the microphone and require an explicit restart.

The initial command interpreter is bounded and deterministic; unrestricted conversational interpretation, language translation, physical Braille execution, and always-on wake words are not implemented. Browser and microphone quality determine recognition performance; the local energy threshold may need adjustment in noisy rooms.

Validation: `npm run check:voice`, `npm run check:story`, and `npm run check`. Browser layout was checked in Practice and the Peter Rabbit player. Live ElevenLabs transcription remains unverified until a key is supplied to the server environment and microphone speech is tested.

## Basic navigation and packaged voice

Visible navigation names are recognized directly: Home, Explore, Practice, Story mode, About me, and Connections. Open/go-to prefixes are also accepted. The global commands Back, Help, Repeat, Stop speech and Stop listening remain distinct from activity answers.

The opt-in Spoken navigation checkbox controls short page-orientation prompts and is available inside the book player. The setting is stored locally. Navigation focuses the new page and updates its accessible announcement. Stop speech is always reachable without microphone input. Packaged playback also suppresses microphone dispatch to prevent echo commands.

Run `npm run package:voice` with ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID in the repository-root .env to generate the fixed prompts using the cane-vision ElevenLabs cache. Environment variables take precedence; voice/model settings fall back to the harness configuration. The local server also loads these private settings at startup. The generated browser assets contain audio and a manifest, never the key. Once generated, navigation prompts play locally without live transcription or a TTS API call. Until clips exist, spoken navigation uses browser speech. Nine ElevenLabs navigation clips have now been generated in this checkout using the configured voice.

## Quiet Story controls

An open book suppresses automatic navigation announcements and successful voice confirmations, even with Spoken navigation enabled. Responses remain visible and teacher confirmation is still required. Help, Repeat and action errors can speak on request. Turning off Spoken navigation stops only its own cached clip or browser fallback; it does not cancel an independently requested reading or teacher prompt.

Read story page reads the visible spread using browser speech, with separate Pause reading / Resume reading controls. It is not an ElevenLabs audiobook narrator. Stop speech stops all output. Commands Read story, Pause reading and Resume reading use these same controls. Automatic page turns remain a separate control. Reading suppresses microphone commands while speaking to prevent echo; paused reading allows commands: pause reading or stop speech with the visible keyboard-accessible controls before speaking.

Voice controls now sit inside one collapsed Voice disclosure. Open it for microphone start/stop, reading controls, spoken-navigation preferences and command help. Its compact label always shows microphone state, including when listening is paused for speech output.
