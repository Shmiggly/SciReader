// Copy pdf.js cMaps and standard fonts into public/ so the viewer works offline (no CDN).
import { cpSync, existsSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const src = join(root, "node_modules", "pdfjs-dist");
const dest = join(root, "public", "pdfjs");
if (!existsSync(src)) process.exit(0);
mkdirSync(dest, { recursive: true });
for (const dir of ["cmaps", "standard_fonts"]) {
  if (existsSync(join(src, dir))) cpSync(join(src, dir), join(dest, dir), { recursive: true });
}
console.log("pdf.js assets copied to public/pdfjs");
