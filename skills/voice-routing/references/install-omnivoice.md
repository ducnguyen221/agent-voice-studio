# Installing the speech engine

This repo brings the method and the scripts. **You bring the engine and your own voice.**

Reference engine: **OmniVoice** (k2-fsa, Apache-2.0) — offline, multilingual, zero-shot voice
cloning. Everything here was measured against it. Another engine can be substituted; the
`vietnamese-tts-script.md` rules will still apply in shape, though the exact failures differ.

---

## What you need

- **Python 3.12**
- **An NVIDIA GPU** for practical speed. CPU works but is slow enough to change how you work.
- **~4 GB of disk** for model weights, cached on first run.
- Internet **once** — for the model download and, if you use automatic transcription, the ASR
  model. After that it runs offline.

## Install

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install torch --index-url https://download.pytorch.org/whl/cu126   # match your CUDA
pip install omnivoice
pip install librosa soundfile scikit-learn
```

**Torch must be recent enough.** The engine pulls a transformers version that needs a dtype
introduced in torch 2.7; older torch fails at import with an error that does not obviously
point at the version.

**Do not install the optional text-normalisation extra on Windows.** One of its dependencies
has no wheel and needs a full MSVC build chain. You do not want that extra anyway — see the
normaliser warning in `vietnamese-tts-script.md`.

## Point the scripts at it

The scripts find the engine through `OMNIVOICE_DIR`, which must contain the engine's
`voice_profiles.py`:

```powershell
setx OMNIVOICE_DIR "C:\path\to\omnivoice"
```
```bash
export OMNIVOICE_DIR=/path/to/omnivoice
```

A user-scope variable is deliberate: every agent harness, shell and scheduler inherits it,
and nothing has to be reconfigured per tool.

Optional:

| Variable | Meaning | Default |
|---|---|---|
| `VOICES_DIR` | where profiles live | `<engine>/voices` |
| `VOICE_STUDIO_WORK` | scratch output | `./out` |

**Set `VOICE_STUDIO_WORK` somewhere outside this repository.** Generated audio is real
voice data; keeping it out of the working tree removes any chance of committing it.

Without the variable the scripts search upward from the current directory and from their own
location for a folder containing `voice_profiles.py`, then try a couple of conventional
locations, then fail with instructions. They never guess.

## Verify

```bash
python studio/verify.py --wav some-clip.wav
```

Loads the engine, builds a clone prompt, synthesizes, transcribes back. If that works, the
whole toolkit works.

## Keep your voices out of version control

Reference clips are biometric-adjacent personal data. Whatever store you use, either keep it
private or exclude it. This repository blocks the entire audio family by default — see
`.gitignore` — and its public example ships **no audio at all**, deliberately.

**Clone only your own voice, or one whose owner agreed in writing.**
