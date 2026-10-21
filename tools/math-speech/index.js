#!/usr/bin/env node
// SciReader math-speech helper.
// Protocol: one JSON request per line on stdin, one JSON response per line on stdout.
//   request:  {"id": "...", "latex": "E = mc^2", "display": true, "style": "clearspeak"}
//   response: {"id": "...", "mathml": "<math>...</math>", "speech": "E equals m c squared", "error": null}
// Everything runs offline: MathJax (TeX -> MathML) and Speech Rule Engine (MathML -> speech)
// load their data from node_modules.

"use strict";

const readline = require("node:readline");
const { mathjax } = require("mathjax-full/js/mathjax.js");
const { TeX } = require("mathjax-full/js/input/tex.js");
const { liteAdaptor } = require("mathjax-full/js/adaptors/liteAdaptor.js");
const { RegisterHTMLHandler } = require("mathjax-full/js/handlers/html.js");
const { AllPackages } = require("mathjax-full/js/input/tex/AllPackages.js");
const { STATE } = require("mathjax-full/js/core/MathItem.js");
const { SerializedMmlVisitor } = require("mathjax-full/js/core/MmlTree/SerializedMmlVisitor.js");
const SRE = require("speech-rule-engine");

const adaptor = liteAdaptor();
RegisterHTMLHandler(adaptor);
// "noundefined"/"noerrors" make MathJax report problems instead of rendering error nodes silently.
const packages = AllPackages.filter((p) => p !== "noundefined" && p !== "noerrors" && p !== "bussproofs");
const tex = new TeX({ packages, formatError: (_jax, err) => { throw err; } });
const html = mathjax.document("", { InputJax: tex });
const visitor = new SerializedMmlVisitor();

function texToMathml(latex, display) {
  const node = html.convert(latex, { display: display !== false, end: STATE.CONVERT });
  return visitor.visitTree(node);
}

let currentStyle = null;
async function ensureStyle(style) {
  const domain = style || "clearspeak";
  if (currentStyle === domain) return;
  await SRE.setupEngine({ locale: "en", domain, modality: "speech", style: "default" });
  await SRE.engineReady();
  currentStyle = domain;
}

async function handle(req) {
  const out = { id: req.id ?? null, mathml: null, speech: null, error: null };
  try {
    out.mathml = req.mathml || texToMathml(req.latex || "", req.display);
    if (req.speech !== false) {
      await ensureStyle(req.style);
      out.speech = SRE.toSpeech(out.mathml);
    }
  } catch (err) {
    out.error = String((err && err.message) || err);
  }
  return out;
}

async function main() {
  await ensureStyle("clearspeak");
  const rl = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
  process.stdout.write(JSON.stringify({ ready: true }) + "\n");
  for await (const line of rl) {
    if (!line.trim()) continue;
    let req;
    try {
      req = JSON.parse(line);
    } catch (err) {
      process.stdout.write(JSON.stringify({ id: null, error: "bad json: " + err.message }) + "\n");
      continue;
    }
    const res = await handle(req);
    process.stdout.write(JSON.stringify(res) + "\n");
  }
}

main().catch((err) => {
  process.stderr.write(String(err && err.stack ? err.stack : err) + "\n");
  process.exit(1);
});
