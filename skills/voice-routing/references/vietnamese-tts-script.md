# Writing a script a Vietnamese TTS engine reads correctly

Every rule here was **measured**, not guessed: the text was synthesized, then Whisper
transcribed the audio back, and the "heard" column is what came out. Where a rule was not
measured, it says so.

Measured on OmniVoice 0.2.1 with an 18-second reference clip. Behaviour on other engines
will differ in detail but the *failure shapes* generalise: separators get swallowed,
acronyms fuse with adjacent digits, and short standalone fragments render unstably.

---

## 1. The job

Raw text → a spoken script. **Not a transcription of the written text.** Prose written to be
read with the eyes and prose written to be read aloud are different things; gluing article
sentences together produces the flat, list-reading cadence everyone recognises as machine
narration.

Rewrite first, then apply the rules below, then mark it up, then check.

## 2. The pronunciation table

| Case | Written WRONG | Engine said | Written RIGHT |
|---|---|---|---|
| **Version number** | `GLM-5.3` | "GLM-53" — the `.3` vanished | `GLM phiên bản 5.3` |
| | `GLM 5.3` | "GOM53" — whole cluster mangled | |
| | `GPT 5.2` | "GPT-52" | `GPT phiên bản 5.2` |
| **Clock time** | `14:30` | "14.30" — the word "giờ" lost | `14 giờ 30` |
| **Date** | `22/8/2026` | "22.8.2026" — slashes lost | `22 tháng 8 năm 2026` |
| **Domain** | `Z.ai` | **"Z đây"** — plainly wrong | `Z chấm AI` |
| **Thousands** | — | correct | `2.436` *or* `2436` — both fine |
| **Number in words** | — | correct | `hai nghìn bốn trăm ba mươi sáu` — also fine |
| **Money** | — | correct | `1.250.000 đồng` |
| **Percent** | — | read as "phần trăm" | `15%` |
| **Common English tech terms** | — | correct | `API`, `OpenAI`, `Microsoft`, `Google` — leave alone |

### The rule underneath the table

**An acronym pressed against a number fuses and mangles.** `GLM 5.3` → "GOM53",
`GPT 5.2` → "GPT-52". Put one ordinary word between them and it resolves:
`GLM phiên bản 5.3` reads correctly. This is the single most useful line here — it covers
model names, product versions, standards, anything shaped `LETTERS + digits`.

**Separator characters get swallowed.** `:` `/` `.` inside times, dates and versions
disappear. Spell them as words: `giờ`, `tháng`, `năm`, `chấm`.

**Bare numbers are safe.** Digits and spelled-out words both read correctly, including
Vietnamese-style thousand dots. Leave them alone.

> **A superseded rule, kept because the reason matters.** An earlier version of this note
> insisted numbers must stay as digits because spelled-out numbers got crushed
> ("một nghìn một trăm bốn mươi mốt" collapsing to "141"). Re-measured with a good reference
> clip: **both forms are correct.** The original fault was never the written form — it was a
> reference clip of only a few seconds. A short clip degrades everything, and the symptom
> happened to show up on numbers first. When a rule seems to be about text, check whether it
> is actually about the clip.

**Never enable the engine's text normaliser for Vietnamese.** In OmniVoice, `normalize_text`
routes zh/en through a proper normaliser and everything else through a regex that only knows
`\d+`. Vietnamese thousand-dots come out as fragments — worse than no normalisation at all.
Keep it off.

### Not measured — verify when you hit them

Uncommon foreign proper nouns (one test heard `Claude` as "Cloud", and it was unclear
whether the engine mispronounced it or ASR misheard); acronyms meant to be spelled out
letter by letter; units like `km/h` and `GB`; Roman numerals.

## 3. Markers

```
[marker-name] First sentence. Second sentence.
[other-marker] Now the delivery changes.
```

A marker holds **until the next marker**. Unmarked text uses the profile's neutral clip.

Marker names come from the profile, not from your imagination — read
`voices/<profile>.profile.json` first. A marker that is not in the manifest is stripped and
the passage falls back to whatever is currently in effect, announced only by one line of
console output that is easy to miss.

Choose by **meaning**, not to sprinkle variety: opening hook, emphasis or conclusion,
quiet narration, fast enumeration, ordinary explanation.

**Non-verbal tags** — the engine's own inline sounds such as laughter, sighs and surprise
interjections — pass straight through, and are weak. They are isolated noises; they cannot
express "read this whole paragraph lower". Use them sparingly; in news copy they sound
false very quickly.

## 4. Seeds

Pin one. The engine is not reproducible without it, and an unpinned A/B measures sampling
noise rather than your change. Detail in `engine-limits.md`.

A seed does not improve a voice — it makes a render repeatable. Different draws *are*
better or worse, so seed search is a real technique, but a machine can only **reject broken
draws** (high ASR error). No metric tells you which draw sounds more human. Search seeds
only for sentences that fail the ASR gate; do not search them all.

## 5. Check before handing over

1. No stray brackets — every marker exists in the manifest, every tag is a real engine tag.
2. **No short fragment standing alone.** A title, a label or a bare number rendered by itself
   comes out unstable: the first token distorts or a word is swallowed. Fold it into the
   opening of a longer sentence.
3. Very long sentences (beyond roughly 380 characters) split at commas, never mid-phrase.
4. Synthesize → ASR back → character error rate above 0.25 means fix the *writing* of that
   part and try again.

## 6. Worked example

**Raw:**
> Z.ai công bố GLM-5.3 ngày 14/8/2026. Mô hình đã phát hiện 2.436 lỗ hổng bảo mật, tăng 15% so với bản trước.

**Script:**
```
[hook] Ngày 14 tháng 8 năm 2026, công ty Z chấm AI công bố một mô hình mới.
[neutral] Nó tên là GLM phiên bản 5.3.
[emphasis] Và đây mới là con số đáng chú ý: mô hình này đã phát hiện 2.436 lỗ hổng bảo mật, tăng 15% so với bản trước.
```

Changed: domain spelled out · version separated from its acronym · date written in words ·
split into short sentences · markers assigned by meaning. Left alone: `2.436` and `15%`,
because both were measured correct.

*(Marker names above are placeholders — use the ones in your own manifest.)*
