# Agent Voice Studio

A voice-production process an AI agent runs end to end: from hours of raw recordings to a
verified speaking voice whose delivery you control from inside the script.

**[Tiếng Việt](README.vi.md)** · [Guide](GUIDE.md) · MIT

---

## What this is

Cloning a voice is easy. Getting a voice that reads *your* text correctly, sounds different
when the meaning is different, and does the same thing twice — that is the hard part, and
that is what this is.

Four things it gives you:

**A way to find the styles already in someone's voice.** People do not have one delivery.
They explain, they persuade, they narrate, they demonstrate. Mining separates those out of
long recordings by measured prosody rather than by guesswork.

**Six automatic gates instead of a human ear.** A reference clip is not an input among many —
it *is* the voice, and everything downstream inherits its faults. Every candidate is checked
by machine, including a round trip through speech recognition.

**Delivery control from inside the script.** Markers in the text switch which reference clip
speaks each passage. The caller picks one profile name; the writing decides the delivery.

**A Vietnamese pronunciation ruleset that was measured, not guessed.** Every rule was
established by synthesizing text and transcribing the audio back. The measurements are in
the table, including the ones that overturned an earlier belief.

## What it is not

Not an engine — you install that yourself. Not a hosted service. Not a source of voices:
this repository contains **no audio at all**, by design.

Also not one piece of a suite you have to install whole. This repository stands alone:
install it when you need a speaking voice, and only then. A content pipeline (for example
`agent-marketing-studio`) *can* call it through the shared contract — exit code plus a final
JSON line on stdout — when it is present, but that pipeline runs fine without it and says
plainly that the voice capability is missing rather than failing mid-run. There is no
required install order and no bundle.

## Install

```bash
git clone https://github.com/ducnguyen221/agent-voice-studio
cd agent-voice-studio
```

Create a venv, install torch for your OS plus `omnivoice==0.2.1`, then install the package and
set up a voice station. Full steps (Vietnamese), including the weights licence warning
(CC-BY-NC) and two traps that cost real time, are in
[`skills/voice-routing/references/install-omnivoice.md`](skills/voice-routing/references/install-omnivoice.md).

```bash
pip install -e .          # inside the engine venv — provides the voice-studio command
voice-studio init         # asks: station inside the repo (embedded, recommended) or outside (separate)
voice-studio doctor       # tells you what is still missing
```

`init` **presents a two-option table before doing anything**, rather than asking an open
question. `embedded` — station at `<repo>/workspace/`, configuration in `<repo>/.env` — is
the **recommendation**: press Enter and you are done, with no environment variables to set.
Choose `separate` when you work across machines, are comfortable with the technical side, or
this repository is your own public fork. With nobody to answer (CI, a scheduled task) `init`
prints that table and **exits with code 2 without writing a byte** — an installing agent must
show the table to the user instead of choosing silently.

`embedded` means clone-and-run: `init` lays down the station tree and copies `.env.example`
to `<repo>/.env` for you to fill in. Both `workspace/` and `.env` are blocked by
`.gitignore` and again by the `pre-commit` hook. `.env` holds **paths and configuration**,
never tokens.

The station holds your venv, voices, background music and output — every folder is described in
[`docs/WORKSPACE.md`](docs/WORKSPACE.md). Generating background music: [`docs/bgm-generation.md`](docs/bgm-generation.md).

As an agent plugin:

```bash
# Claude Code
claude plugin marketplace add ducnguyen221/agent-voice-studio
claude plugin install agent-voice-studio@agent-voice-studio

# Codex
codex plugin marketplace add ducnguyen221/agent-voice-studio
codex plugin install agent-voice-studio@agent-voice-studio
```

## Use

```bash
voice-studio lab mine  --dir recordings/ --name narrator   # find the speaking styles
voice-studio lab build --name narrator --mode new          # gate clips, build the profile
voice-studio speak --file script.txt --profile narrator --out out.mp3
```

Mining and building happen once per voice. Writing and speaking happen every time.

### The `voice-studio` command (package `voice_studio`)

The same tools behind one command, run with the engine venv's python
(`python -m voice_studio …` until the command is installed):

```bash
voice-studio speak --text "Xin chào" --profile narrator --out a.wav --json   # for other pipelines
voice-studio narrate --video silent.mp4 --file script.txt --out final.mp4 --json
voice-studio make-profile --audio rec.wav --start 120 --dur 18 --name narrator
voice-studio clone --file talk.m4a --name narrator --consent
voice-studio clean recording.mp3                 # isolate voice + denoise (see voice_studio/clean/README.md)
voice-studio lab mine|build|split|organize …     # the multi-style builder above
voice-studio doctor                              # tells you what is still missing
voice-studio export --personal --out voices.zip  # move machines: voices + music + station.json
voice-studio backup --out station.zip            # back up the station · update = git pull --ff-only
```

`speak`/`narrate` are the **stable contract** for other pipelines: `--json` prints exactly one
JSON line as the last line of stdout, logs go to stderr, exit codes `0` ok · `1` engine error ·
`2` bad call/config (missing profile, empty text) · `3` station/engine not installed. The old
`python studio/*.py` commands still work (they are aliases). `clone` and `make-profile` are for
**consented** voices only — see rule 4.

An agent with the plugin installed reads `skills/voice-routing/SKILL.md` and loads only the
reference the current step needs.

## Four rules

1. **Never trust your ear — measure.** Synthesize, transcribe back, compare. "Sounds better"
   is not a result.
2. **Pin the seed.** The engine is not reproducible by default. An unpinned comparison
   measures sampling noise.
3. **A bad reference clip poisons everything built from it.** Never wave one through.
4. **Clone only your own voice, or one whose owner agreed in writing.**

## Acknowledgments

This project orchestrates engines you install yourself; it bundles none of their code.

- [OmniVoice](https://github.com/k2-fsa/OmniVoice) (k2-fsa) — Apache-2.0 — synthesis and cloning
- [ClearerVoice-Studio](https://github.com/modelscope/ClearerVoice-Studio) (modelscope) — Apache-2.0 — enhancement
- [python-audio-separator](https://github.com/nomadkaraoke/python-audio-separator) (nomadkaraoke) — MIT — separation

**Model weights are licensed separately from the code that loads them**, and some separation
variants are non-commercial. Check the licence of every checkpoint you download before using
its output commercially.

## Licence

MIT — see [LICENSE](LICENSE).
