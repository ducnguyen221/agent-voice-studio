# Profiles with more than one speaking style

A profile is **one voice identity holding several reference clips**, switched by markers
inside the text. Whoever writes a script sees a single name; the delivery changes where the
script says it should.

This shape is forced by the engine, not chosen for elegance: one generate call uses exactly
one clip, and there is no emotion parameter. See `engine-limits.md`.

---

## On disk

```
voices/
    <name>.wav  .txt  .prompt.pt      ← neutral clip, FLAT, non-negotiable
    <name>.profile.json               ← manifest
    <name>.variants/
        <marker>.wav  .txt  .prompt.pt
```

**The neutral clip stays flat in `voices/`.** Simple loaders read exactly
`voices/<name>.wav` + `.txt`, and pipelines pin voices by name. Keeping that contract means a
multi-style profile also works everywhere a plain profile works — it just speaks in its
neutral voice. Profile subfolders do not pollute the profile list, because listing scans for
`*.wav` at the top level only.

Manifest per variant: relative wav path, its transcript, an optional speed, the source
(file and offset), the measured features, and a build timestamp. Source and timestamp matter
more than they look — months later they are the only way to answer "where did this clip come
from, and which batch added it".

## Speed defaults to 1.0 and should stay there

The clip already carries its own tempo. Adding a speed factor counts it twice. The field
exists for hand-tuning after listening, not for the builder to guess at.

## Synthesis

Split the text at markers; each span uses its marker's clip; unmarked text uses the neutral
clip. **Split every span into sentences and generate them one at a time** — matching how
production narration pipelines already work, and avoiding a single call swallowing a long
passage.

Joining spans needs three things:

- **Normalise each span's level to the neutral clip's RMS.** Different clips have different
  loudness; without this the joins step audibly.
- **Fade ~30 ms at each span edge before inserting silence.** A synthesized sentence usually
  ends at non-zero amplitude, so butting it against a block of zeros is a discontinuity — a
  click on *every* join of *every* render. This one was shipped as dead code once: the
  crossfade branch was written but could never execute, because a gap was always inserted
  first. Verify such a branch actually runs.
- **Insert a longer silence when the marker changes** than between sentences sharing one.

## Unknown markers must be stripped, never spoken

A marker not in the manifest has to disappear from the text. The worst outcome is a bracketed
word being read aloud in a published file. Strip it, fall back to whatever is in effect, and
report it — but do not let it through.

Engine-native inline tags are the opposite: leave them in place, the engine consumes them.

## Adding styles later

Build supports an **add** mode from the start: merge new variants into an existing manifest
without touching existing clips and without changing the neutral clip unless explicitly told.

Write that mode before you need it. The second batch of recordings always arrives, and
retrofitting merge semantics into a builder that only knows how to start from scratch is the
kind of rework worth avoiding once.

Two guards belong in add mode:

- Overwriting an existing marker requires an explicit force flag.
- Force-overwriting the **neutral** marker without also updating the flat copy would leave two
  divergent base voices — the marker-aware path reading one, plain loaders reading the other,
  silently. Refuse it.

## Build atomically

Stage everything, then commit in one move. A build that writes variants as it goes and then
aborts — because the neutral cluster failed, say — leaves new clips on disk beside an old
manifest that describes different ones. Nothing warns you; the manifest simply lies.

## Guard the existing voice store

Refuse to overwrite a name that already exists as a plain profile without a manifest. Voice
stores are usually not in version control, so a mistyped name is unrecoverable, and pipelines
pin voices by exactly the name a typo would destroy.

## Standalone profiles from variants

Sometimes you want the styles as separate named profiles instead — to pick one per run, or to
compare them. Extract each variant into a plain profile; the multi-style original stays
intact. The two shapes serve different needs: **markers** change delivery *within* one piece;
**separate profiles** choose a voice *for* a piece.
