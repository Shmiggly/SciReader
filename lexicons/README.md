# SciReader pronunciation lexicons

Text-to-speech voices mispronounce scientific terms: they read `PEGDA` letter by letter,
`Tg` as a word, `PA12` as "pa twelve". A lexicon tells SciReader how to say a term.
`science-en.json` ships with the app and is the seed of an open science pronunciation
dataset (polymers, additive manufacturing, characterization, ML).

## Format

```json
{
  "version": 1,
  "language": "en",
  "name": "SciReader science pronunciations (English)",
  "entries": [
    {
      "term": "PEGDA",
      "say_as": "peg-dah",
      "ipa": null,
      "case_sensitive": true,
      "tags": ["polymers", "monomers"],
      "source": "shipped",
      "note": "poly(ethylene glycol) diacrylate"
    }
  ]
}
```

| Field | Meaning |
|---|---|
| `term` | Text as it appears in papers. Matched as a whole word (`PEG` does not match inside `PEGDA` or `PEGs`). Longer terms win. |
| `say_as` | Plain respelling the voice reads well, such as `"peg-dah"` or `"T G"`. Spell letters with hyphens (`"P-L-A"`, `"P-A twelve"`): the English voice reduces a lone `A` to the article "uh", and hyphens prevent that. |
| `ipa` | Optional exact phonemes (misaki/Kokoro IPA, for example `"pˈɛɡdə"`). When set, it wins over `say_as`, and the text is sent to the voice as misaki's inline markup `[PEGDA](/pˈɛɡdə/)` (checked with misaki 0.9.4). |
| `case_sensitive` | `true` for acronyms (`Tg` is not `TG`); `false` for ordinary words (`photoinitiator`, `Photoinitiator`). |
| `tags` | Field(s), used to build field packs (`polymers`, `additive-manufacturing`, `characterization`, `machine-learning`, `units`, ...). |
| `source` | `shipped`, `user`, or where an imported entry came from. |
| `note` | What the term means, or why it is spelled this way. |

## User lexicon and overrides

Your own entries live in a separate user lexicon file. When a user entry has the same
`term` as a shipped entry, the user entry wins. Removing it brings the shipped one back.
The shipped file is never modified by the app.

## Sharing and importing

- **Export** writes the merged lexicon (shipped + your overrides) to a JSON file in this format.
- **Import** reads someone else's file: new terms are added to your user lexicon,
  identical ones are skipped, and terms you already pronounce differently are listed as
  conflicts so you can choose "keep mine" or "take theirs" for each.

## Contributing

Pronunciations are community knowledge. If a term is read wrong, add an entry with a
`note` (what the term is) and `tags` (its field), and check it in SciReader before
submitting. Lexicon entries and annotations in this folder are released under
**CC BY 4.0** (attribution: the SciReader contributors), so they can feed other open
tools and a shared science pronunciation dataset.
