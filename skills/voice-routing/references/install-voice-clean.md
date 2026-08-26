# Cleaning recordings — and when not to

Only for recordings with **music or noise under the voice**. A two-stage chain: separate the
voice from everything else, then denoise and de-reverb what is left.

- **Stage 1** — `python-audio-separator` (MIT), a BS-Roformer model, pulls the voice out of a
  mix.
- **Stage 2** — `ClearerVoice-Studio` (Apache-2.0), a 48 kHz speech-enhancement model,
  removes remaining noise and room.

---

## Decide before you install

Measure the source first:

- **Noise floor.** Around −60 dB or lower with real silences between phrases → already clean.
- **Silence gaps.** Continuous audio with *no* silent gaps at a −45 dB threshold means
  something is playing underneath.

**Do not clean audio that is already clean.** These models smooth, and smoothing removes the
character you are trying to capture. A source measured at −67 dB was deliberately left alone
and produced one of the better profiles.

**Measure at several points.** Long recordings are often mixed — music through the first
half, clean in the second. A clean stretch needs no cleaning at all, which is faster *and*
better.

## The install trap: two virtual environments, not one

The two stages have **irreconcilable dependencies**. One requires a major numpy version the
other pins against, plus conflicting versions of a shared helper library. Installed together,
pip quietly downgrades and stage 1 breaks — without an obvious error.

Build **two separate environments** and have stage 1 invoke stage 2 as a subprocess. This is
not tidiness; it is the only arrangement that works.

```bash
python -m venv .venv-sep    # separation
python -m venv .venv-enh    # enhancement
```

Each gets its own torch build. Expect several GB per environment.

## Two more traps worth knowing before you hit them

**A loose dependency pin can break the separator.** A permissive range let a major version of
an audio library in that had removed a keyword argument the separator still used — separation
completed, then died while writing the file, with a message about a missing output rather
than about the library. Pin that dependency below the breaking major, and re-check the pin
after any upgrade.

**The enhancement model may resolve its checkpoint relative to the working directory.** Run
it from elsewhere and it re-downloads a few hundred megabytes into whatever folder you
happened to be in. Force the working directory before invoking it.

## Throughput

Roughly **0.25–0.4× realtime on a mid-range GPU** — an hour of audio in fifteen to
twenty-five minutes. Run sequentially, not in parallel: both stages want the GPU, and
overlapping them is slower.

## Verify the cleaning worked

Do not trust the absence of errors. Re-measure:

- **Silence gaps should reappear.** In one case a horror-narration recording went from *zero*
  detected silences in a two-minute sample to **nineteen** — the background had genuinely
  gone.
- **RMS should barely move.** Measured −18.1 dB before, −18.1 after. A large drop means the
  voice was attenuated along with the noise, and the clip is now worse, not better.

Then listen to a short before/after pair. Machine checks confirm the noise left; only a
person can confirm the *character* survived — and for expressive material such as shouting or
whispered narration, that is exactly what is at risk.

## Model licences differ from code licences

The wrapper code is permissively licensed. **Model weights are licensed separately**, and some
separation variants are non-commercial. Check the licence of every checkpoint you download
before using its output commercially. Weight licences also change more quietly than code
licences, so re-check after updates.
