---
name: voice-routing
description: Use when producing speech with a cloned voice — building a voice profile from recordings, writing a script a TTS engine reads correctly (especially Vietnamese numbers, acronyms, dates, foreign names), diagnosing a voice that stutters or mangles words, or setting up the engine. Routes to the one reference the current step needs instead of loading everything.
---

# Voice Studio — one door in

You are producing speech in someone's real voice. Four things can be happening. Find yours,
load **only** that reference, do the work, stop.

| What is happening | Load | Then |
|---|---|---|
| Text needs to be **spoken** — you have a profile already | `references/vietnamese-tts-script.md` | rewrite the text, mark it, synthesize |
| No profile yet — you have **recordings** | `references/mining-protocol.md` | mine → verify → build |
| Voice **sounds wrong** — stutters, mangles numbers, repeats a syllable | `references/engine-limits.md` | diagnose against known engine behaviour |
| **Nothing installed** | `references/install-omnivoice.md` | install engine, then come back |

Load `references/verify-gates.md` whenever you accept or reject a reference clip.
Load `references/profile-and-markers.md` when a profile needs more than one speaking style.
Load `references/install-voice-clean.md` only when a recording has music or noise under the voice.

## Four rules that override everything

**1. Never trust your ear. Measure.**
This whole toolkit exists because listening is unreliable and non-reproducible. Every claim
about a voice — is this clip good, did that tag do anything, is this rendering correct —
gets settled by synthesizing and running ASR back over the output. If you catch yourself
writing "sounds better", you have skipped the step that matters.

**2. Pin the seed or your comparison means nothing.**
The engine is not reproducible by default. Two renders of identical text differ. Any A/B
without a pinned seed measures noise, not the thing you changed. See `engine-limits.md`.

**3. A bad reference clip poisons everything downstream.**
The clip is not an input among many; it is the voice. Six automatic gates exist because
there is usually no human available to listen. Never wave a clip through.

**4. Only clone a voice you own, or one whose owner agreed in writing.**
Not a legal footnote — the reason this repo ships no audio at all.

## The shape of the work

```
recordings ──► mine ──► verify ──► build ──► profile
   (hours)     clips     gates     manifest      │
                                                 ▼
                        raw text ──► script ──► speak ──► audio
                                    (markers,     │
                                     pronunciation)│
                                                  ▼
                                            ASR check
```

Mining and verification happen **once** per voice. Scripting and speaking happen every time.
Most sessions are the bottom row only.

## Commands

Scripts live in `studio/`. They find the engine through `OMNIVOICE_DIR` — see
`install-omnivoice.md`. They never assume the engine sits next to them.

```
python studio/mine.py     --dir <recordings> --name <profile>   # dig out speaking styles
python studio/build.py    --name <profile> --mode new           # gate clips, build profile
python studio/speak.py    --file script.txt --profile <profile> --out out.mp3
python studio/classic.py  --audio rec.wav --start 120 --dur 18 --name <profile>
python studio/verify.py   --wav clip.wav                        # inspect one clip
python studio/split.py    --from <profile> --prefix <p>         # variants → standalone profiles
python studio/organize.py --keep <profile> ... --apply          # tidy the voice store
```

`build.py` and `speak.py` cover most work. The rest are for when something needs a closer look.

## Where things live

The engine, the voice store and your recordings are **yours** and live outside this repo.
This repo holds the method and the scripts. Keep it that way: audio must never enter the
repository — `.gitignore` blocks the whole family by default, and a fixture opens single
files by name only.
