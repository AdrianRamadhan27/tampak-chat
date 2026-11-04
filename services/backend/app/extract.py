"""Bounded extraction subprocess. Geometry always comes from the source parser/OCR."""

import json
import os
import re
import sys
import zipfile
from pathlib import Path

from PIL import Image

Image.MAX_IMAGE_PIXELS = 25_000_000


def box(values, width: float, height: float) -> list[float]:
    x0, y0, x1, y1 = values
    return [
        max(0, min(1, x0 / width)),
        max(0, min(1, y0 / height)),
        max(0, min(1, x1 / width)),
        max(0, min(1, y1 / height)),
    ]


def render_pdf(path: Path, page_number: int, output: Path) -> tuple[int, int]:
    import pypdfium2 as pdfium

    with pdfium.PdfDocument(path) as pdf:
        page = pdf[page_number - 1]
        scale = min(1.6, 1600 / max(page.get_width(), page.get_height()))
        bitmap = page.render(scale=scale)
        image = bitmap.to_pil()
        image.save(output)
        size = image.size
        image.close()
        bitmap.close()
        page.close()
    return size


def native_pdf(path: Path, folder: Path, max_pages: int, options: dict | None = None) -> dict:
    import pdfplumber

    pages, warnings = [], []
    options = options or {}
    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) > max_pages:
            raise ValueError(f"Document exceeds the {max_pages}-page limit.")
        first, last = options.get("page_start", 1), options.get("page_end") or len(pdf.pages)
        if first > len(pdf.pages) or last > len(pdf.pages):
            raise ValueError("The selected page range is outside this PDF.")
        for number, page in enumerate(pdf.pages, 1):
            if not first <= number <= last:
                continue
            blocks = []
            tables = page.find_tables()
            table_boxes = [table.bbox for table in tables]
            for ti, table in enumerate(tables):
                rows = [[cell or "" for cell in row] for row in table.extract()]
                blocks.append(
                    {
                        "id": f"p{number}-t{ti}",
                        "type": "table",
                        "rows": rows,
                        "text": "\n".join(" | ".join(row) for row in rows),
                        "bbox": box(table.bbox, page.width, page.height),
                        "cells": [
                            {"row": ri, "col": ci, "bbox": box(cell, page.width, page.height)}
                            for ri, row in enumerate(table.rows)
                            for ci, cell in enumerate(row.cells)
                            if cell
                        ],
                    }
                )
            words = page.extract_words()
            lines: dict[int, list] = {}
            for word in words:
                if any(
                    t[0] <= word["x0"] <= t[2] and t[1] <= word["top"] <= t[3] for t in table_boxes
                ):
                    continue
                lines.setdefault(round(word["top"] / 3), []).append(word)
            for index, line in enumerate(lines.values()):
                line.sort(key=lambda w: w["x0"])
                coords = (
                    min(w["x0"] for w in line),
                    min(w["top"] for w in line),
                    max(w["x1"] for w in line),
                    max(w["bottom"] for w in line),
                )
                blocks.append(
                    {
                        "id": f"p{number}-l{index}",
                        "type": "text",
                        "text": " ".join(w["text"] for w in line),
                        "bbox": box(coords, page.width, page.height),
                    }
                )
            page_key = f"page-{number}.png"
            render_pdf(path, number, folder / page_key)
            with Image.open(folder / page_key) as raster:
                for index, image in enumerate(page.images[:20]):
                    coords = box(
                        (image["x0"], image["top"], image["x1"], image["bottom"]),
                        page.width,
                        page.height,
                    )
                    if coords[2] <= coords[0] or coords[3] <= coords[1]:
                        continue
                    key = f"figure-{number}-{index}.png"
                    raster.crop(
                        (
                            int(coords[0] * raster.width),
                            int(coords[1] * raster.height),
                            int(coords[2] * raster.width),
                            int(coords[3] * raster.height),
                        )
                    ).save(folder / key)
                    blocks.append(
                        {
                            "id": f"p{number}-i{index}",
                            "type": "figure",
                            "text": "",
                            "bbox": coords,
                            "image": key,
                        }
                    )
            blocks.sort(key=lambda b: (b["bbox"][1], b["bbox"][0]))
            if len("".join(b["text"] for b in blocks)) < 30:
                warnings.append(
                    f"Page {number} has little extractable text. Select OCR or full-page vision."
                )
            pages.append(
                {
                    "number": number,
                    "width": float(page.width),
                    "height": float(page.height),
                    "image": page_key,
                    "blocks": blocks,
                }
            )
    return {
        "format": "pdf",
        "pages": pages,
        "total_pages": len(pdf.pages),
        "warnings": warnings,
        "parser": "pdfplumber",
    }


def image_ocr(path: Path, folder: Path, languages: list[str], force: bool = True) -> dict:
    import pytesseract

    pages = []
    with Image.open(path) as source:
        image = source.convert("RGB")
        image.thumbnail((2000, 2000))
        image.save(folder / "page-1.png")
        blocks = []
        if force:
            data = pytesseract.image_to_data(
                image, lang="+".join(languages), output_type=pytesseract.Output.DICT, timeout=70
            )
            for index, text in enumerate(data["text"]):
                if text.strip():
                    coords = (
                        data["left"][index],
                        data["top"][index],
                        data["left"][index] + data["width"][index],
                        data["top"][index] + data["height"][index],
                    )
                    blocks.append(
                        {
                            "id": f"p1-w{index}",
                            "type": "text",
                            "text": text,
                            "confidence": float(data["conf"][index]) / 100,
                            "bbox": box(coords, image.width, image.height),
                        }
                    )
        blocks.append(
            {
                "id": "p1-image",
                "type": "figure",
                "text": "",
                "image": "page-1.png",
                "bbox": [0, 0, 1, 1],
            }
        )
        pages.append(
            {
                "number": 1,
                "width": image.width,
                "height": image.height,
                "image": "page-1.png",
                "blocks": blocks,
            }
        )
    return {
        "format": "image",
        "pages": pages,
        "warnings": []
        if any(block["type"] == "text" and block["text"].strip() for block in blocks)
        else [
            "No locally recognized text. Use vision interpretation for visual content, and review its output."
        ],
        "parser": "tesseract" if force else "image",
    }


def docx_extract(path: Path, folder: Path) -> dict:
    from docx import Document
    from docx.oxml.ns import qn

    document = Document(path)
    blocks = []
    for index, item in enumerate(document.iter_inner_content()):
        if hasattr(item, "rows"):
            rows = [[cell.text for cell in row.cells] for row in item.rows]
            blocks.append(
                {
                    "id": f"section-{index}",
                    "type": "table",
                    "rows": rows,
                    "text": "\n".join(" | ".join(row) for row in rows),
                    "bbox": None,
                }
            )
        else:
            if item.text.strip():
                blocks.append(
                    {
                        "id": f"section-{index}",
                        "type": "heading" if item.style.name.startswith("Heading") else "text",
                        "text": item.text,
                        "bbox": None,
                    }
                )
            for j, blip in enumerate(item._element.iter(qn("a:blip"))):
                relationship = blip.get(qn("r:embed"))
                if relationship in document.part.related_parts:
                    blob = document.part.related_parts[relationship].blob
                    from io import BytesIO

                    with Image.open(BytesIO(blob)) as image:
                        key = f"figure-section-{index}-{j}.png"
                        image.convert("RGB").save(folder / key)
                        blocks.append(
                            {
                                "id": f"section-{index}-i{j}",
                                "type": "figure",
                                "text": "",
                                "bbox": None,
                                "image": key,
                            }
                        )
    return {
        "format": "docx",
        "parser": "python-docx",
        "pages": [{"number": 1, "blocks": blocks}],
        "warnings": ["DOCX has no stable physical page map. Citations use section anchors."],
    }


def docling_pdf(path: Path, folder: Path, options: dict, max_pages: int) -> dict:
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import (
        PdfPipelineOptions,
        TableFormerMode,
        TesseractCliOcrOptions,
    )
    from docling.document_converter import DocumentConverter, ImageFormatOption, PdfFormatOption
    from pypdf import PdfReader

    from app.config import settings

    is_image = path.suffix.lower() != ".pdf"
    total_pages = 1 if is_image else len(PdfReader(path).pages)
    if total_pages > max_pages:
        raise ValueError(f"Document exceeds the {max_pages}-page limit.")
    first, last = options.get("page_start", 1), options.get("page_end") or total_pages
    if first > total_pages or last > total_pages:
        raise ValueError("The selected page range is outside this document.")
    pipeline = PdfPipelineOptions(
        do_ocr=True,
        do_table_structure=True,
        generate_picture_images=True,
        document_timeout=150,
        enable_remote_services=False,
        ocr_options=TesseractCliOcrOptions(
            lang=options.get("languages", ["eng"]),
            mode="full_page" if options.get("force_ocr") else "default",
        ),
    )
    pipeline.table_structure_options.mode = (
        TableFormerMode.ACCURATE
        if options.get("table_mode", "accurate") == "accurate"
        else TableFormerMode.FAST
    )
    artifacts = settings().storage / "docling-models"
    if (artifacts / "docling-project--docling-models").exists() and (
        artifacts / "docling-project--docling-layout-heron"
    ).exists():
        pipeline.artifacts_path = artifacts
    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline),
            InputFormat.IMAGE: ImageFormatOption(pipeline_options=pipeline),
        }
    )
    result = converter.convert(path, max_num_pages=max_pages, page_range=(first, last))
    document = result.document
    pages = {}
    for page_no, page in document.pages.items():
        key = f"page-{page_no}.png"
        if is_image:
            with Image.open(path) as image:
                image.convert("RGB").save(folder / key)
        else:
            render_pdf(path, page_no, folder / key)
        pages[page_no] = {
            "number": page_no,
            "width": page.size.width,
            "height": page.size.height,
            "image": key,
            "blocks": [],
        }
    warnings = []
    for index, (item, _) in enumerate(document.iterate_items()):
        if not item.prov:
            continue
        for pi, prov in enumerate(item.prov):
            page = pages.get(prov.page_no)
            if not page:
                continue
            bbox = prov.bbox.to_top_left_origin(page_height=page["height"])
            coords = box((bbox.l, bbox.t, bbox.r, bbox.b), page["width"], page["height"])
            label = str(item.label.value)
            block = {
                "id": f"d{index}-{pi}",
                "type": "text",
                "text": getattr(item, "text", ""),
                "bbox": coords,
            }
            if label == "table":
                block["type"] = "table"
                grid = item.data.grid
                rows = [[cell.text for cell in row] for row in grid]
                cells = []
                for cell in item.data.table_cells:
                    cell_box = (
                        cell.bbox.to_top_left_origin(page_height=page["height"])
                        if cell.bbox
                        else None
                    )
                    cells.append(
                        {
                            "row": cell.start_row_offset_idx,
                            "col": cell.start_col_offset_idx,
                            "row_span": cell.row_span,
                            "col_span": cell.col_span,
                            "text": cell.text,
                            "column_header": cell.column_header,
                            "bbox": box(
                                (cell_box.l, cell_box.t, cell_box.r, cell_box.b),
                                page["width"],
                                page["height"],
                            )
                            if cell_box
                            else None,
                        }
                    )
                block.update(
                    rows=rows, cells=cells, text="\n".join(" | ".join(row) for row in rows)
                )
            elif label == "picture":
                block["type"] = "figure"
                key = f"figure-{index}-{pi}.png"
                image = item.get_image(document)
                if image:
                    image.save(folder / key)
                    block["image"] = key
            elif label in {"title", "section_header"}:
                block["type"] = "heading"
            page["blocks"].append(block)
    for page in pages.values():
        if not any(b["text"].strip() for b in page["blocks"]):
            warnings.append(f"No text recovered on page {page['number']}.")
    return {
        "format": "image" if is_image else "pdf",
        "total_pages": total_pages,
        "parser": "docling+tesseract",
        "pages": list(pages.values()),
        "warnings": warnings,
    }


def extract(path: Path, folder: Path, options: dict, max_pages: int = 50) -> dict:
    folder.mkdir(parents=True, exist_ok=True)
    suffix = path.suffix.lower()
    if suffix in {".docx", ".xlsx"}:
        with zipfile.ZipFile(path) as archive:
            if sum(item.file_size for item in archive.infolist()) > 60_000_000:
                raise ValueError("Expanded Office file exceeds 60 MB.")
            if len(archive.infolist()) > 6000:
                raise ValueError("Too many Office archive entries.")
    if suffix == ".pdf":
        if options.get("method") in {"auto", "layout", "ocr"}:
            return docling_pdf(
                path,
                folder,
                options
                | {"force_ocr": options.get("method") == "ocr" or options.get("force_ocr", False)},
                max_pages,
            )
        return native_pdf(path, folder, max_pages, options)
    if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
        if options.get("method") in {"auto", "layout", "ocr"}:
            return docling_pdf(
                path, folder, options | {"force_ocr": options.get("method") == "ocr"}, max_pages
            )
        return image_ocr(
            path, folder, options.get("languages", ["eng"]), options.get("method") != "vision"
        )
    if suffix == ".docx":
        return docx_extract(path, folder)
    if suffix in {".txt", ".md"}:
        text = path.read_text(encoding="utf-8-sig", errors="strict")
        blocks = [
            {"id": f"section-{i}", "type": "text", "text": part, "bbox": None}
            for i, part in enumerate(re.split(r"\n\s*\n", text))
            if part.strip()
        ]
        return {
            "format": "text",
            "parser": "utf8",
            "pages": [{"number": 1, "blocks": blocks}],
            "warnings": [],
        }
    if suffix in {".csv", ".xlsx"}:
        from app.analytics import profile_file

        return profile_file(path, folder)
    raise ValueError("Unsupported file type.")


if __name__ == "__main__":
    # Isolate native parsers and model downloads from API/worker event loops.
    os.environ.setdefault("OMP_NUM_THREADS", "2")
    try:
        if sys.platform != "win32":
            import resource

            resource.setrlimit(resource.RLIMIT_CPU, (170, 175))
            resource.setrlimit(resource.RLIMIT_NOFILE, (512, 512))
        path, folder = Path(sys.argv[1]), Path(sys.argv[2])
        result = extract(path, folder, json.loads(sys.argv[3]), int(sys.argv[4]))
        (folder / "extraction.json").write_text(json.dumps(result))
    except Exception as error:
        print(f"{type(error).__name__}: {str(error)[:600]}", file=sys.stderr)
        raise SystemExit(1) from error
