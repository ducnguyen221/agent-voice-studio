# What the engine can and cannot do

Six facts established by measurement. Every one of them changed a design decision, and
several contradict what the API surface suggests.

---

## 1. One generate call = one clip = one delivery

The reference clip does not merely supply timbre; it supplies the *whole* delivery — pitch
register, tempo, energy, how the speaker phrases. There is no way to ask one clip to read
one passage brightly and the next passage low.

**Consequence:** "a profile with a range of emotion" cannot be built from a single clip. It
has to be several clips inside one identity, switched by markers in the text. That is the
entire reason `profile-and-markers.md` exists.

## 2. There is no emotion parameter

The `instruct` field accepts a **closed vocabulary** — gender, age band, pitch level,
whisper, accent. Emotion words are rejected outright with a `ValueError`.

## 3. `instruct` is weak once a clip is cloned

Measured median F0 on identical text:

| | F0 |
|---|---|
| plain | 159.9 Hz |
| `instruct = high pitch` | 172.3 Hz (+12) |
| `instruct = low pitch` | **164.0 Hz — moved the wrong way** |

The clone prompt dominates. Do not build anything on `instruct` when a reference clip is in
play; it is not an emotion axis and, combined with cloning, barely a pitch axis.

## 4. Generation is NOT reproducible without an explicit seed

Same text, same profile, three runs → **three different audio hashes**. Durations matched,
because duration is estimated from the text, which is exactly what makes this easy to miss:
the output *looks* stable in the logs.

The generation config has **no seed parameter**, and the token-sampling temperature is
already zero. The randomness comes from position selection during iterative unmasking and
from diffusion initialisation. Seeding the tensor library before each call makes output
identical **to the byte**.

**Consequence — the important one:** any comparison run without a pinned seed is measuring
sampling noise. This was caught the hard way while trying to measure whether an inline tag
did anything; the difference turned out to contain both the tag's effect and the noise of
two separate draws, inseparably.

**Seeding does not make a voice better.** It makes a render repeatable. Different draws *are*
better and worse — so searching seeds is legitimate — but a machine can only reject broken
draws via ASR error. Nothing measures "more human". Search seeds only for sentences that
fail the gate.

Vary the seed per sentence (`seed + sentence_index`) so sentences do not share one noise
pattern while the whole render stays reproducible.

## 5. Inline non-verbal tags are real but weak in Vietnamese

The engine's bracketed sounds — laughter, sigh, surprise interjections, question sounds —
run without error on Vietnamese text and do widen pitch range slightly. They are isolated
noises, not a delivery control: nothing in that vocabulary expresses "read this paragraph
lower". Use sparingly.

## 6. The text normaliser is unsafe for Vietnamese

It routes Chinese and English through a real normaliser and everything else through a regex
that only recognises bare integers. Vietnamese thousand-separators come out as fragments —
worse than leaving the text alone. **Keep it off.**

---

## Diagnosing a voice that sounds wrong

| Symptom | Almost always | Fix |
|---|---|---|
| A syllable from nowhere at the start of every clip | reference clip ends mid-word | re-cut the clip at a sentence boundary with a silent tail — see `verify-gates.md` |
| Numbers, acronyms or dates mangled | how the text is written | `vietnamese-tts-script.md` |
| Short lines render unstably, first word swallowed | fragment rendered alone | fold it into a longer sentence |
| Same input, different output each run | no seed pinned | fact 4 |
| Delivery flat and identical everywhere | one clip doing all the work | multiple clips + markers |
| Voice quality poor in general | reference clip too short | re-cut at 16–19 seconds from clean audio |

The last row is worth internalising: **an unexpectedly large share of "the engine is bad"
turns out to be "the clip is short".** Check clip length before blaming anything else.
