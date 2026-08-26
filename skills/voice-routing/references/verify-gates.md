# Six gates every reference clip must pass

A reference clip is not one input among many — **it is the voice**. Everything generated
from it inherits its faults. These gates exist because there is usually no human available
to listen, and because listening does not scale to dozens of candidates anyway.

Implemented in `studio/verify.py`. A clip failing **any** gate is rejected and the next
candidate is tried.

---

| # | Gate | Rejects when | Catches |
|---|---|---|---|
| 1 | Clipping | peak ≥ −0.5 dB | distorted recording |
| 2 | Too quiet | RMS < −34 dB | unusable signal-to-noise |
| 3 | Pitch tracking | > 35 % of frames fail | leftover music, or two people talking over each other |
| 4 | **Silent tail** | last 250 ms not ≥ 18 dB below clip RMS | clip ends mid-word |
| 5 | Round trip | synthesize 2 probe sentences, ASR back, CER > 0.25 | clip that produces garbled speech |
| 6 | Leak probe | first syllable of output equals last syllable of the reference | the bug gate 4 prevents, caught directly |

Gates 1–4 are cheap; run them first and skip the GPU work when they fail.

## Why gate 4 replaced an obvious-looking check

The first version tested whether the **transcript** ended with punctuation, reasoning that a
clip ending mid-sentence is a clip cut badly.

It rejected an entire cluster — three of three candidates — and stopped the build.

The cause: Vietnamese ASR routinely omits a final full stop. The gate measured **the
transcriber's punctuation habit**, not the clip. The thing actually worth measuring is
whether the audio *ends in silence*, and audio can be measured directly. Rewritten as gate
4, it immediately rejected three genuinely bad clips across three different clusters —
which is what a gate is for.

**The lesson generalises:** when a gate proxies for the property you care about, check what
it is really measuring. A missing full stop is a fact about the transcriber. Silence at the
end is a fact about the clip.

## Gates 5 and 6 — the bug worth naming

If a reference clip stops **mid-word or mid-phrase**, the model treats generation as a
continuation of that unfinished sound, and splices the leftover syllable onto the front of
**every clip it ever generates from that profile**. One bad reference, and every future
render opens with a stray syllable.

It is easy to miss when you listen casually and impossible to miss once you know the shape.
Gate 4 prevents it structurally; gate 6 tests for it directly. Keep both — gate 4 can be
satisfied by silence that still follows a clipped word.

## Cutting clips so they pass

- Open and close on **utterance boundaries** — a pause of at least 250 ms on both sides.
- Add a short lead-in (~0.15 s) and a silent tail.
- **Tail must never exceed the real gap.** A fixed 0.40 s tail is longer than a 0.25 s pause
  threshold, so with a short gap the tail swallows the first sound of the next sentence —
  recreating the exact bug the gates exist to prevent. Measure the actual following gap and
  take `min(0.40, gap − 0.05)`.
- Target **16–19 seconds**. Shorter clips degrade everything; longer ones stop helping.
- Internal pauses are fine and natural. Only the two ends matter.

## Transcript quality matters less than you expect

Reference text should match the audio, and hand-correcting obvious ASR errors is worth the
minute it takes. But a clip cut from fast, energetic speech — where ASR does noticeably
worse — still cloned cleanly, passing round-trip at CER 0.00. **Boundaries first,
transcript second.**

## Do not wave clips through

Rejecting a candidate is cheap: take the next one. Accepting a bad one is expensive: every
downstream render carries the fault, and you find out weeks later on published audio.
