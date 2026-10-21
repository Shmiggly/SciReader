"""Docling adapter: PDF → DoclingDocument (layout, reading order, formula LaTeX), then → Document JSON."""

from __future__ import annotations

import gc
import threading
import time
from pathlib import Path
from typing import Any

from .builder import Progress, build_document

_lock = threading.Lock()


def _make_converter(ocr: bool = False) -> Any:
    from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    try:
        import torch

        device = AcceleratorDevice.CUDA if torch.cuda.is_available() else AcceleratorDevice.CPU
    except Exception:  # noqa: BLE001
        device = AcceleratorDevice.CPU
    opts = PdfPipelineOptions()
    opts.do_ocr = ocr
    if ocr:
        from docling.datamodel.pipeline_options import RapidOcrOptions

        # Scanned/old papers: full-page OCR with RapidOCR on the torch backend (no extra runtime needed).
        opts.ocr_options = RapidOcrOptions(backend="torch", force_full_page_ocr=True)
    opts.do_table_structure = True
    opts.do_formula_enrichment = True
    opts.accelerator_options = AcceleratorOptions(device=device)
    return DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)})


class DoclingParser:
    name = "docling"

    def convert(self, pdf_path: Path, progress: Progress | None = None) -> Any:
        say = progress or (lambda msg, frac: None)
        ocr = needs_ocr(pdf_path)
        with _lock:  # one parse at a time on the GPU
            say("No text layer found: this looks like a scanned PDF, running OCR (slower)" if ocr else "Loading layout models", 0.03)
            conv = _make_converter(ocr)
            say("Running OCR, layout, equations and tables (Docling)" if ocr else "Analyzing layout, equations and tables (Docling)", 0.08)
            t0 = time.time()
            result = conv.convert(str(pdf_path))
            doc = result.document
            say(f"Layout done in {time.time() - t0:.0f} s", 0.7)
            del conv, result
            _free_gpu()
            return doc

    def parse(self, pdf_path: Path, doc_id: str, source: dict, progress: Progress | None = None,
              docling_cache: Path | None = None) -> tuple[dict, dict]:
        from docling_core.types.doc import DoclingDocument

        if docling_cache is not None and docling_cache.exists():
            doc = DoclingDocument.load_from_json(docling_cache)
        else:
            doc = self.convert(pdf_path, progress)
            if docling_cache is not None:
                doc.save_as_json(docling_cache)
        return build_document(doc, str(pdf_path), doc_id, source, progress)


def _free_gpu() -> None:
    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:  # noqa: BLE001
        pass


def needs_ocr(pdf_path: Path) -> bool:
    """True when most pages have (almost) no extractable text: a scanned or image-only PDF."""
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        n = len(pdf)
        empty = 0
        for i in range(n):
            tp = pdf[i].get_textpage()
            if tp.count_chars() < 40:
                empty += 1
            tp.close()
        return n > 0 and empty / n >= 0.6
    finally:
        pdf.close()
