# Mining speaking styles out of long recordings

You have hours of someone talking and need a handful of short reference clips that capture
their **distinct ways of speaking**. Implemented in `studio/mine.py`.

---

## Choosing source material

Record **situations, not takes**. Ask the speaker for the contexts they actually work in —
explaining, persuading, presenting from notes, presenting from a script, demonstrating a
tool. That labelling is information a machine cannot recover from the waveform, and it turns
out to be the most valuable input in the whole process.

Roughly an hour is plenty. The binding constraint is *selection*, not volume: a profile needs
one clip of 16–19 seconds per style, so an hour is orders of magnitude more than required.

**Keep the recording setup identical across situations.** Mixing microphones or distances
splits the voice into timbre families that no amount of clever clustering will reconcile —
and it will look like the speaker has more range than they do.

## The pipeline

1. **Segment** — find utterances separated by pauses ≥ 250 ms; group consecutive ones into
   12–22 second windows that open and close on utterance boundaries.
2. **Feature** — per window: median pitch, pitch range, speaking rate, energy, pause ratio,
   spectral brightness. **Prosody only.** Nothing about topic or wording.
3. **Cluster** — z-score *within this speaker*, then k-means with `k` chosen by silhouette.
4. **Name** — from the measured axes, not from imagination.
5. **Pick** — three candidates per cluster nearest the centroid, cut with lead-in and a
   correctly-sized silent tail.
6. **Verify** — `verify-gates.md`. First candidate to pass wins.

## Three corrections that changed the results

### Do not span long silences

Window length is measured start-to-end, so a window can be "valid" while being half dead air
— someone paused ten seconds for a drink. That wrecks the pause-ratio feature and yields a
mostly-empty reference clip. **Refuse to join utterances across a gap longer than ~1.2 s.**

### Normalise level per source file, or you cluster by file

Absolute energy does not measure delivery; it measures **recording gain**. One session
recorded roughly 10 dB quieter than the others produced an "expressive cluster" that turned
out to be exactly that one file — the algorithm had grouped by *file*, not by style. The
giveaway was cluster size matching file size almost one to one.

Subtract each file's own median energy first. After that correction, the energy differences
between situations collapsed to near zero, confirming the whole apparent effect had been
gain staging. Leave pitch absolute — for one speaker across sessions it stays meaningful.

### Name clusters after what you measured

The first version matched clusters against a table of hand-written emotion prototypes
(*excited*, *whispering*, and so on). On real data **three of five clusters matched nothing**
and fell through to meaningless auto-numbering. Widening the tolerance was worse: it would
have labelled a demonstrably *fast* cluster "whispering".

Build the name from the axes that actually deviate — high/low, fast/slow, strong/soft — in a
fixed order. `high-slow` says something true and checkable. `excited` is a guess about an
inner state that nobody measured.

## Two kinds of marker, and why both

Acoustic clustering discards the speaker's own labels. Silhouette also favours coarse
partitions, so five carefully recorded situations can collapse into three clusters.

Keep both: **acoustic markers** the data discovers, and **situation markers**, one per source
file, named from the file. The second kind is human context the waveform does not contain,
and in practice they are the easier ones to choose correctly when writing a script.

**De-duplicate at build time.** Both kinds are mined from the same window pool, so two markers
can land on the same segment — observed once, byte-identical. Two names that produce the same
audio waste a slot and mislead whoever writes the script.

## Let the data decide how many

Do not fix the number of styles in advance. Silhouette picks it. If a speaker only has three
distinct registers, three is the honest answer, and inventing a fourth produces a marker that
sounds like one of the others.

## When cleaning is worth it — and when it hurts

Only clean audio that has music or noise **under the voice**. Check the noise floor and
whether real silences exist between phrases: continuous audio with no silent gaps means
something is playing underneath.

**Do not clean already-clean audio.** Separation and denoising models smooth, and smoothing is
exactly what removes the character you are trying to capture. One recording measured at
−67 dB noise floor was left untouched for that reason and produced one of the better profiles.

Long recordings are often mixed: a source can carry music through its first half and be clean
in its second. Measure at several points before deciding — a clean stretch needs no cleaning
at all, which is both faster and better. Setup details in `install-voice-clean.md`.
