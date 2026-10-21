# Demo video script (≤ 4 min, your own voice, not sped up)

Draft by the agent; adjust to your words. Record with OBS or Snipping Tool at 1440×900, SciReader in its app window (`./scripts/dev.ps1`). Before recording: open the flagship once (so the parse is cached and equations/figures are prepared), delete `qwen3.5:4b` in ▦ Models so the download is real, and clear your user lexicon entry for "GPJet" if you saved one.

| Time | On screen | You say |
|---|---|---|
| 0:00–0:15 | Your face or the title card, then a PDF in a generic reader | "It's easy to lose your place in long text. Audiobooks fixed that for books. For papers, nothing did." |
| 0:15–0:30 | A generic TTS reading a paper: "[12]", the running header, an equation as gibberish, "1.12 eV at 300 K" → "ee-vee… kay" | "Generic readers read the page numbers, the citation brackets, mangle the units, and turn equations into noise." |
| 0:30–0:50 | SciReader start screen → open the polymer jet-printing paper from Recent | "This is SciReader. Open-source, and it runs entirely on my laptop. The paper stays exactly as published." |
| 0:50–1:15 | Click a sentence in the introduction; sentence + word highlight, focus mode, auto-scroll | "I click where I want to start. The highlight follows the voice, everything else dims, and it skips citations, headers and the reference list." |
| 1:15–1:45 | Page 13: play equation 22; click its ✓ badge; show the popover (equation, spoken text, "written back exactly") | "Equations are where AI narration gets dangerous: it sounds right even when it's wrong. So a second, independent model writes the narration back as LaTeX, and SciReader checks it's the same equation. Verified gets a check mark; anything it can't verify falls back to a rule-based reading." |
| 1:45–2:10 | Page 5: the "Fig. 3b" sentence; the figure pops up with the panel-b description | "When the text mentions a figure, it pops up right there and I hear a description of just the panel it mentions, clearly labeled as AI." |
| 2:10–2:30 | ✦ AI → Explain on a dense sentence → click a citation chip | "If a sentence loses me, I ask for an explanation. It only uses the paper and points to its sources." |
| 2:30–2:45 | Aa Pronunciation: ▶ "PEGDA" (or GPJet) sounds wrong → type "peg-dah" → Save → replay a sentence | "It finds the terms the voice will get wrong. I fix one once, and it's fixed in every paper. You can share these lexicons." |
| 2:45–3:00 | ▦ Models: download qwen3.5:4b with the progress bar; Wi-Fi off (show the tray icon); keep reading | "Models download in one click. And with Wi-Fi off, everything keeps working, so I can use it on unpublished work." |
| 3:00–3:35 | The SciSpeech-Bench figure (`bench/figures/faithfulness.png`), then the marimo notebook | "We measured it. On 220 equations from arXiv papers, a local LLM silently changed about one equation in three. Our verification catches four in five of those errors: faithful readings go from 64 to 89 percent. And a generic reader mispronounces almost half of the units and formulas we tested; SciReader none." |
| 3:35–4:00 | README / GitHub page | "SciReader is open source, local and private. It's for researchers with dyslexia, ADHD or low vision, non-native readers, and anyone who wants to listen to a paper on the way to the lab. Next: more fields, more languages, and a phone app." |

Tips: keep the mouse slow; zoom the PDF to ~130 %; use the "Sun" highlight preset for contrast on video; record the benchmark segment from `bench/analysis.html` in a browser.
