# SciReader pronunciation datasets

Text-to-speech voices mispronounce scientific terms: they read `PEGDA` letter by letter,
`Tg` as a word, `PA12` as "pa twelve". A pronunciation dataset tells SciReader how to say a term.
`science-en.json` is the **SciReader list** that ships with the app: the seed of an open science
pronunciation dataset (polymers, additive manufacturing, characterization, chemistry, ML, ...).

`proposed-en.json` holds proposals nobody has listened to yet (`"checked": false`): terms the voice
says wrong without help, found by comparing its phonemes with and without each entry. They are
reviewed by ear in the app (Pronunciation → Review them) before they join the SciReader list.

## Your own dataset

Every user has one personal dataset file (`.data/pronunciations.json`). It starts as a copy of the
SciReader list and grows over time:

- **Give a term a pronunciation** on the Pronunciation screen (the terms the open paper suggests, or
  any term you type) and it goes into your dataset at once, for every paper.
- **Updates of the SciReader list flow in**: new terms are added (unless you removed them), and
  entries still as the list had them take its new pronunciation. Entries you changed are never
  overwritten.
- **Import** a dataset from a file or from a link someone shared online (the only step that needs
  internet), and **export** yours as one file anyone can import.
- **Two entries for the same term** with different pronunciations (after an import, say) both stay,
  marked "2 entries", until you choose one; until then the first one is spoken.

The SciReader list, a personal dataset, an export and a list shared online are the same format, so a
dataset moves from one user to another as one file.

## Format

```json
{
  "format": "scireader-pronunciations",
  "version": 2,
  "language": "en",
  "name": "SciReader science pronunciations (English)",
  "license": "CC BY 4.0",
  "updated": "2026-10-22",
  "base_hash": null,
  "removed": [],
  "entries": [
    {
      "term": "PEGDA",
      "say_as": "peg-dah",
      "ipa": null,
      "case_sensitive": true,
      "tags": ["polymers", "monomers"],
      "source": "base",
      "note": "poly(ethylene glycol) diacrylate",
      "kind": "acronym",
      "checked": true,
      "added": "2026-10-21"
    }
  ]
}
```

| Field | Meaning |
|---|---|
| `term` | Text as it appears in papers. Matched as a whole word (`PEG` does not match inside `PEGDA` or `PEGs`). Longer terms win. |
| `say_as` | Plain respelling the voice reads well, such as `"peg-dah"` or `"T G"`; `null` means "read as written" (checked, and it already sounds right). Spell letters with hyphens (`"P-L-A"`, `"P-A twelve"`): the English voice reduces a lone `A` to the article "uh", and hyphens prevent that. |
| `ipa` | Optional exact phonemes (misaki/Kokoro IPA, for example `"pˈɛɡdə"`). When set, it wins over `say_as`, and the text is sent to the voice as misaki's inline markup `[PEGDA](/pˈɛɡdə/)` (checked with misaki 0.9.4). |
| `case_sensitive` | `true` for acronyms (`Tg` is not `TG`); `false` for ordinary words (`photoinitiator`, `Photoinitiator`). |
| `tags` | Field(s), used to build field packs (`polymers`, `additive-manufacturing`, `characterization`, `machine-learning`, `units`, ...). |
| `source` | `base` (the SciReader list), `me` (you gave it), or `import:<dataset>` (where an imported entry came from). |
| `note` | What the term means, or why it is spelled this way. |
| `kind` | `acronym`, `word`, `molecule`, `formula`, `unit`, `symbol`, `name` or `other`. |
| `checked` | `false` for a proposal or an import nobody has listened to yet; the Pronunciation screen lists them as "to check". |
| `added` | When the entry entered this dataset. |

At the top, `removed` lists SciReader-list terms the user removed (so updates don't bring them back)
and `base_hash` which version of the list the dataset last took updates from; both are ignored on
import. Older lexicon files (`{"version": 1, "entries": [...]}`) and bare lists of entries import too.

## Contributing

Pronunciations are community knowledge. If a term is read wrong, give it a pronunciation, add a
`note` (what the term is) and `tags` (its field), and listen to it in SciReader before sharing.
Entries in this folder are released under **CC BY 4.0** (attribution: the SciReader contributors),
so they can feed other open tools and a shared science pronunciation dataset.
