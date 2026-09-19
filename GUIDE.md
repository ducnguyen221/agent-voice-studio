# Guide — from recordings to a voice you can direct

The whole path, in order, with the decisions that actually matter called out.

**[Tiếng Việt](GUIDE.vi.md)** · [README](README.md)

---

## 0. Before you record

Two decisions here outweigh everything downstream.

**Record situations, not takes.** Ask the speaker for the contexts they really work in —
explaining something, persuading someone, narrating, reading from a script, demonstrating a
tool. Name the files after those situations. That label is human context a machine cannot
recover from the waveform, and it is the single most valuable thing you will feed the
process.

**Keep the setup identical across situations.** Same microphone, same distance, same room.
Mixing setups splits the voice into timbre families that no clustering can reconcile, and
makes the speaker look like they have range they do not have.

About an hour total is plenty. A profile needs one clip of 16–19 seconds per style; the
constraint is selection, never volume.

## 1. Install

See [`install-omnivoice.md`](skills/voice-routing/references/install-omnivoice.md): venv →
torch for your OS → `omnivoice==0.2.1` → `pip install -e <repo>` → `voice-studio init` →
`voice-studio doctor`. `init` asks where the **voice station** lives — inside the repo
(`embedded`, the default) or outside it (`separate`); every station folder is explained in
[`docs/WORKSPACE.md`](docs/WORKSPACE.md). Output goes to the station, never into the repo's code,
so generated audio can never be committed.

## 2. Clean — only if you need to

Measure the noise floor and whether real silences appear between phrases. Continuous audio
with no silent gaps means something is playing underneath; that needs cleaning. Anything
already clean should be **left alone** — the models smooth, and smoothing removes exactly
the character you are trying to capture.

Long recordings are often mixed. Measure at several points; a clean stretch needs nothing.

Details and the two-environment install trap:
[`install-voice-clean.md`](skills/voice-routing/references/install-voice-clean.md).

## 3. Mine

```bash
voice-studio lab mine --dir recordings/ --name narrator
```

Cuts the audio into utterance-bounded windows, measures prosody, clusters within the speaker,
names each cluster from the axes that actually deviate, and cuts three candidates per cluster.

You get both **acoustic markers** the data discovered and **situation markers**, one per
source file. Both are worth keeping — see
[`mining-protocol.md`](skills/voice-routing/references/mining-protocol.md), which also
explains three corrections that changed the results, including one where the algorithm was
found to be clustering by *recording gain* rather than by delivery.

## 4. Build

```bash
voice-studio lab build --name narrator --mode new
```

Runs six gates over every candidate and keeps the first that passes. Expect rejections —
that is the gate working. Produces the profile plus two things to listen to: one sentence
read through every marker, and a passage that changes marker repeatedly so you can hear the
joins.

**Listen to the joins.** Everything else here is machine-checkable; whether a transition
sounds natural is not.

Gate details: [`verify-gates.md`](skills/voice-routing/references/verify-gates.md).

## 5. Write the script

This is where quality is won or lost, and it is the step people skip.

Prose written to be read with the eyes and prose written aloud are different. Rewrite: short
sentences, one idea each, rhetorical questions, the small connecting words people actually
say. Then apply the pronunciation rules — acronyms separated from numbers, separators spelled
as words — and mark it up by meaning.

The full measured table:
[`vietnamese-tts-script.md`](skills/voice-routing/references/vietnamese-tts-script.md).

## 6. Speak

```bash
voice-studio speak --file script.txt --profile narrator --out out.mp3
```

Splits at markers, then at sentences, pins the seed, normalises levels, fades the joins.

## 7. Check

Synthesize, transcribe back, compare. A character error rate above 0.25 means fix the
*writing* of that passage, not the voice. If a sentence keeps failing, try a different seed —
but only for that sentence.

---

## The mistakes that cost the most time

**Trusting the ear.** Every claim about a voice — is this clip good, did that tag do
anything, does this read correctly — must be settled by measurement. Listening is
unreliable, unreproducible, and it does not scale past a handful of candidates.

**Comparing without pinning the seed.** The engine is not reproducible by default. Two
renders of identical text differ. This was discovered while trying to measure whether an
inline tag did anything — the observed difference contained both the tag's effect and the
noise of two separate draws, inseparably.

**Blaming the engine for a short clip.** A surprising share of "this engine is bad" turns
out to be "this reference clip is four seconds long". Check clip length first.

**Letting a gate proxy for the thing you care about.** One gate tested whether the transcript
ended with punctuation, as a stand-in for "the clip ends cleanly". It measured the
transcriber's punctuation habit instead, and rejected an entire good cluster. Measuring the
audio directly — is the last quarter-second silent — was both correct and simpler.

**Assuming a code path runs.** A crossfade was written, reviewed, and shipped as dead code:
a gap was always inserted first, so the crossfade branch could never execute. Every render
clicked at every join. Verify the branch actually runs.

## Ethics

Clone your own voice, or a voice whose owner agreed in writing. Voice is personal data and
recognisable. This repository ships no audio at all — a deliberate choice, and a reasonable
default for anything you build on top of it.
