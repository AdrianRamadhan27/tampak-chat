# Tampak Chat document processing research

Research date: 4 November 2026. Status: proposed implementation choices, not benchmark results.

## Recommendation and first delivery

Make document processing a configurable part of upload. Use **Docling with layout analysis, OCR when needed, and accurate table extraction** as the default for PDFs and images. Offer a faster native-text path, forced OCR, optional VLM figure descriptions, and full-page VLM parsing. Keep the original file and a structured extraction result so the owner can inspect and reprocess a document before replacing its active index.

This is a proposed baseline, not a claim that Docling wins on every document. Native extraction can preserve clean text more faithfully; OCR can misread characters; VLMs can omit or invent content. Select defaults using a representative local benchmark.

The local delivery target is **today, 4 November 2026, Asia/Jakarta**, after the required design review. The same-day target includes working **native**, **layout and OCR**, **VLM figure enrichment**, and **full-page VLM parsing** choices. Vision features require a configured, tested vision-capable provider; a disabled control must explain that dependency and cannot be counted as a working delivery. Unstructured and PaddleOCR remain optional additional engine adapters. They do not replace or defer the required processing choices. This is a target for implementation, not a claim that the work or quality checks are already complete.

## Modes available at upload

These are Tampak-Chat product recommendations. The verified library capabilities follow in the next section.

| User-facing mode | Initial implementation | Appropriate use | Visible limitations |
| --- | --- | --- | --- |
| Fast text | Native PDF text extraction with pypdf; format-native handling for text, Markdown and supported office files | Clean searchable documents and quick ingestion | Does not interpret figures or reliably reconstruct complex PDF tables; scanned pages need OCR |
| Layout and OCR | Docling standard PDF/image pipeline, accurate tables, Tesseract OCR when needed | Mixed text, scans, columns, tables and embedded figures | More CPU and memory; reading order, OCR and table structure still need inspection |
| Force OCR | Same layout pipeline with full-page OCR, selected languages | Broken text layers, scans and screenshots | May degrade clean native text; report the chosen route |
| Describe figures | Layout and OCR plus VLM descriptions of detected figures | Diagrams, charts and screenshots whose meaning is absent from surrounding text | Adds model-generated content, cost and possible mistakes |
| Vision document parsing | Docling VLM pipeline against a tested vision profile, processing page images | Difficult visual layouts and a deliberate alternative to the standard pipeline | Generic Markdown output may have only page-level provenance; extraction can hallucinate |

Choose the mode per file in a batch. Advanced controls should expose the actual library/engine, OCR language and policy, table mode, figure enrichment, page range and vision profile. Show only supported combinations. Explain which pages or crops leave the machine when a remote model is selected; show an estimate and a processing cap before starting. Do not silently replace the selected engine after failure.

## Verified capabilities and their implications

### Docling standard extraction

Docling exposes OCR, table structure recognition, page and picture images, and enrichment options. Its documentation distinguishes fast and accurate TableFormer modes and exposes cell matching. These support the proposed default; exact option names must match the pinned version. [Pipeline options](https://docling-project.github.io/docling/reference/pipeline_options/), [advanced table settings](https://docling-project.github.io/docling/usage/advanced_options/).

For English and Indonesian OCR, select Tesseract’s `eng` and `ind` language data. Both language codes are present in the official supported-language list. The `tessdata_best` repository provides a quality-oriented alternative to faster data; benchmark its runtime on the local machine rather than promising an accuracy gain on every page. [Language list](https://tesseract-ocr.github.io/tessdoc/Data-Files-in-different-versions.html), [trained models](https://github.com/tesseract-ocr/tessdata_best).

`DoclingDocument` represents text, tables, pictures, hierarchy, furniture and provenance, with geometry where available. Its typed schema includes page numbers, bounding boxes, character spans, table row/column offsets and spans; a table-cell box may be absent. Preserve this structured result instead of storing only flattened Markdown. [Document model](https://docling-project.github.io/docling/concepts/docling_document/), [provenance and table-cell schema](https://docling-project.github.io/docling/reference/docling_document/).

**Proposed default:** automatic OCR with Tesseract `eng+ind`, accurate tables, extracted figure crops and page previews; VLM enrichment off until deliberately selected. Cache the exact local model artifacts and record their revisions. Enforce worker memory, page, raster-resolution and runtime limits rather than processing inside the upload request.

### Vision enrichment and full-page parsing

Docling supports picture-description enrichment through OpenAI-compatible chat-completions services. A current example also shows preserving returned usage payloads. Capture those fields when present; do not display invented token counts when an endpoint omits them. [Picture description API example](https://docling-project.github.io/docling/_generated/examples/pictures_description_api/), [usage capture example](https://docling-project.github.io/docling/_generated/examples/picture_description_api_usage/).

Its `VlmPipeline` supports end-to-end conversion with DocTags, Markdown or HTML output and local or remote inference. A remote service must support the required image-input contract; model-specific output formats still matter. A generic OpenAI-compatible text endpoint is insufficient. [Vision models and remote inference](https://docling-project.github.io/docling/usage/vision_models/).

**Proposed integration:** use a separate admin-configured vision parsing profile, even when it shares a provider with chat. Test image acceptance, requested model, timeout behavior and output parsing before enabling it. Prefer grounded structured output when the selected model supplies it. For ordinary Markdown output, preserve the page image and page reference; display region geometry as unavailable. Never manufacture element or cell boxes from ungrounded text.

Figure captions generated by a VLM must be stored as `generated_description`, with their source crop, model/profile version, prompt version and timestamp. Keep extracted printed captions and OCR text as separate elements. Retrieval can include generated descriptions with an explicit label, while the answer’s citation opens the original figure. Numerical chart interpretation needs a visible review warning when unsupported or uncertain.

### Native extraction

pypdf extracts PDF text and offers a layout-oriented text mode. Its documentation explains that image-only pages need OCR and warns that difficult PDF content can use substantial memory. It does not supply the semantic table and figure understanding required for the richer path. [Text extraction and limits](https://pypdf.readthedocs.io/en/stable/user/extract-text.html).

Use this as an intentional quick path and benchmark baseline. A low text yield should produce a recommendation to retry with OCR rather than mark an empty scan ready. For DOCX and Markdown, preserve structural anchors such as section or paragraph identifiers; do not invent stable PDF-style page coordinates when the source format does not provide them.

### Later engine adapters

**Unstructured:** its open-source partitioner emits typed document elements and supports multiple formats. PDF/image strategies include `auto`, `fast`, `hi_res` and `ocr_only`, with layout and table options. This makes it a credible adapter for comparing classifications and format coverage, but does not establish superior quality on our corpus. Keep the open-source library distinct from the vendor’s hosted products and enrichment features. [Partitioner](https://docs.unstructured.io/open-source/core-functionality/partitioning), [strategy definitions](https://docs.unstructured.io/open-source/concepts/partitioning-strategies).

**PaddleOCR PP-StructureV3:** the documented pipeline combines layout, reading order, OCR, tables and formulas, with structured results and Markdown export. Its output includes recognition scores and table-cell geometry. Consider it for a second local processing engine after measuring installation size, runtime, language fit and extraction quality. Individual module confidence is not a calibrated probability that an answer is correct. [Pipeline tutorial and output fields](https://paddlepaddle.github.io/PaddleOCR/main/en/version3.x/pipeline_usage/PP-StructureV3.html).

**Marker:** retain as a research candidate rather than the default dependency. Its current code and model licenses differ, and upstream versions have changed their terms over time. The current model license includes commercial thresholds, competing-service restrictions, and output attribution/share-alike language. These terms need a specific adoption review; permissive code licensing alone does not settle its suitability. [Current README](https://github.com/datalab-to/marker/blob/master/README.md), [model license](https://github.com/datalab-to/marker/blob/master/MODEL_LICENSE).

## Licensing and artifact inventory

| Component | Verified code terms | Model or deployment considerations |
| --- | --- | --- |
| Docling | [MIT](https://github.com/docling-project/docling/blob/main/LICENSE) | Its models have separate terms. The inspected [Docling models repository](https://huggingface.co/docling-project/docling-models) lists CDLA Permissive 2.0 and Apache 2.0; [Heron layout model](https://huggingface.co/docling-project/docling-layout-heron) lists Apache 2.0. Pin the actual artifacts and preserve their terms. |
| Tesseract | [Apache 2.0](https://github.com/tesseract-ocr/tesseract/blob/main/LICENSE) | The inspected [tessdata_best license](https://github.com/tesseract-ocr/tessdata_best/blob/main/LICENSE) is also Apache 2.0. Bundle only the selected language files with notices. |
| pypdf | [BSD 3 Clause](https://github.com/py-pdf/pypdf/blob/main/LICENSE) | No OCR model is included by this native-text choice. |
| Unstructured library | [Apache 2.0](https://github.com/Unstructured-IO/unstructured/blob/main/LICENSE.md) | Review separately downloaded inference models and optional dependencies; hosted services have their own terms and costs. |
| PaddleOCR | [Apache 2.0](https://github.com/PaddlePaddle/PaddleOCR/blob/main/LICENSE) | Official [PP-DocLayout-L](https://huggingface.co/PaddlePaddle/PP-DocLayout-L) and [SLANet_plus](https://huggingface.co/PaddlePaddle/SLANet_plus) cards list Apache 2.0. This does not automatically cover every optional pipeline model. |
| Marker | Current [code license is Apache 2.0](https://github.com/datalab-to/marker/blob/master/LICENSE) | Current weights use a modified AI Pubs Open Rail-M license; the README describes free research/personal use and a startup funding/revenue threshold. Do not summarize its weights as unrestricted Apache-licensed assets. |

Record package versions, model repositories and revisions, artifact hashes, source URLs and notices in an implementation inventory. External vision providers require a record of the configured provider/model and applicable service terms. A mutable hosted model alias cannot guarantee byte-for-byte reproducibility; retain output and any returned model version/fingerprint.

## Extraction preview and reprocessing contract

The following is a proposed application contract:

1. Store the original bytes and create an immutable extraction revision containing the selected processing configuration, engine versions, model/prompt versions and artifact references.
2. Parse asynchronously and emit actual stage/page progress. Preserve partial errors and identify skipped pages. Make cancellation and bounded retry possible.
3. Display the source beside extracted reading order, a table viewer and figure crops. Highlight an element’s page region only when valid geometry exists. Show missing text, suspicious characters, empty tables and generated content distinctly.
4. Let the owner accept the result or reprocess with different settings. The previous ready revision remains usable until the replacement is successfully indexed and activated.
5. Split along document structure. Preserve heading trails, table headers, row groups, units and figure links. Avoid combining unrelated table cells into ordinary prose; any searchable serialization must reference the original structured table.
6. Publish a new index revision atomically. Each chat run records the corpus/index revision it used so a mid-run reprocessing job cannot change the meaning of its evidence.

Each normalized element should reference document and extraction revision, source item ID, element type, text origin, page or structural anchor, optional bounding box with coordinate system, and table cell references when applicable. Each chunk keeps its source element IDs and spans. Missing provenance is explicit. Generated content is never relabeled as verbatim source text.

The processing fingerprint should cover the source digest, normalized options, parser versions, model revisions and prompt version. Include the provider configuration version, not its decrypted secret. Preview, temporary crops, extraction results and replacement indexes must inherit the same chatbot or conversation access scope as the source.

## Quality benchmark and release checks

Build at least twelve reviewable fixtures spanning clean text PDFs, Indonesian and English scans, mixed scanned/native PDFs, multicolumn layouts, complex tables, and diagrams or charts. Include DOCX tables and standalone image uploads. Keep a golden transcription, critical table cells and expected source locations for selected pages.

Compare the same pages across native extraction, layout/OCR, forced OCR and vision. Record cold-start and warm runtime separately, peak memory, processed pages, vision calls, reported or estimated tokens and cost. An engine should earn its default through these results rather than its marketing benchmark.

| Quality dimension | Proposed measurement |
| --- | --- |
| Text fidelity | Character/word error rates on scanned fixtures; missing and duplicated text counts |
| Reading order | Annotated ordering errors and heading/paragraph boundary checks |
| Tables | Exact critical-cell values, header association, row/column spans and structural comparison |
| Figures | Recall of annotated facts and unsupported generated statements, reviewed against the original crop |
| Provenance | Every published chunk resolves to its source revision; valid page/region links where provided |
| RAG effect | Retrieval recall on gold questions plus answer correctness and citation support, using a fixed embedding/chat configuration |
| Reliability | Broken/encrypted file errors, missing OCR data, unavailable model, timeout, cancellation and failed replacement preserving the prior active revision |

For release, require the representative fixtures to show no silent omitted pages, no fabricated provenance, and no unexplained changes to critical table values. Flag uncertain extraction for review. Publish measured limitations and the benchmark configuration; set numeric quality targets after the first baseline run. No quality or speed measurements have been performed during this planning research.
