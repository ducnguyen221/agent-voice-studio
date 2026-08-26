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

## Install

```bash
git clone https://github.com/ducnguyen221/agent-voice-studio
cd agent-voice-studio
```

Install a speech engine and point one variable at it. Full steps, including two traps that
cost real time, are in [`skills/voice-routing/references/install-omnivoice.md`](skills/voice-routing/references/install-omnivoice.md).

```bash
export OMNIVOICE_DIR=/path/to/engine      # Windows: setx OMNIVOICE_DIR "C:\path\to\engine"
```

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
python studio/mine.py  --dir recordings/ --name narrator   # find the speaking styles
python studio/build.py --name narrator --mode new          # gate clips, build the profile
python studio/speak.py --file script.txt --profile narrator --out out.mp3
```

Mining and building happen once per voice. Writing and speaking happen every time.

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
