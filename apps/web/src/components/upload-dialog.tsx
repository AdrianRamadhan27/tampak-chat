"use client";

import { useState } from "react";
import { Boxes, FileText, ScanLine, Sparkles, UploadCloud } from "lucide-react";
import { api, errorMessage, post } from "@/lib/api";
import type { Bot, ProcessingOptions, Session } from "@/lib/types";
import { Badge, Button, Dialog, ErrorBanner } from "./ui";

export const DEFAULT_PROCESSING: ProcessingOptions = {
  method: "auto",
  table_mode: "accurate",
  page_start: 1,
  page_end: null,
  processing_budget_usd: 0.25,
  languages: ["eng"],
  force_ocr: false,
  enrich_figures: false,
  chunk_size: 1400,
  chunk_overlap: 160,
  remote_consent: false,
};
export type Uploaded = {
  source_id: string;
  revision_id: string;
  status: string;
};

export function UploadDialog({
  open,
  onClose,
  bot,
  session,
  conversationId,
  reprocess,
  onUploaded,
}: {
  open: boolean;
  onClose: () => void;
  bot: Bot;
  session: Session;
  conversationId?: string;
  reprocess?: { revision_id: string; name: string };
  onUploaded: (result: Uploaded) => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [options, setOptions] = useState<ProcessingOptions>(DEFAULT_PROCESSING);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [dragging, setDragging] = useState(false);
  const name = reprocess?.name ?? file?.name ?? "";
  const suffix = name.split(".").at(-1)?.toLowerCase();
  const visualFile = ["pdf", "png", "jpg", "jpeg", "webp"].includes(
    suffix ?? "",
  );
  const officeText = ["docx", "txt", "md", "csv", "xlsx"].includes(
    suffix ?? "",
  );
  const vision =
    session.capabilities.vision?.available &&
    session.capabilities.vision?.vision;
  function selectFile(value: File | undefined) {
    if (!value) return;
    setError("");
    if (value.size > 10 * 1024 * 1024) {
      setError("Upload a file up to 10 MB.");
      return;
    }
    setFile(value);
    if (
      !["pdf", "png", "jpg", "jpeg", "webp"].includes(
        value.name.split(".").at(-1)?.toLowerCase() ?? "",
      )
    )
      setOptions((previous) => ({ ...previous, method: "native" }));
  }
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      let result: Uploaded;
      if (reprocess && !file)
        result = await post<Uploaded>(
          `/revisions/${reprocess.revision_id}/reprocess`,
          options,
        );
      else {
        if (!file) throw new Error("Choose a file to upload.");
        const data = new FormData();
        data.set("file", file);
        data.set("options", JSON.stringify(options));
        if (conversationId) data.set("conversation_id", conversationId);
        result = await api<Uploaded>(
          reprocess
            ? `/revisions/${reprocess.revision_id}/replace`
            : `/bots/${bot.id}/sources`,
          {
            method: "POST",
            body: data,
          },
        );
      }
      onUploaded(result);
      onClose();
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }
  const methods = [
    {
      id: "auto",
      icon: Boxes,
      label: "Automatic",
      detail:
        "Docling layout + OCR for PDFs and images; structured native parsing for Office, text and datasets.",
      disabled: false,
    },
    {
      id: "native",
      icon: FileText,
      label: "Native extraction",
      detail:
        "Fast, local parsing. Text, digital PDFs, Office files and datasets.",
      disabled: false,
    },
    {
      id: "layout",
      icon: Boxes,
      label: "Layout + OCR",
      detail:
        "Docling reads layout, restores tables and recognizes scanned regions.",
      disabled: officeText,
    },
    {
      id: "ocr",
      icon: ScanLine,
      label: "Force OCR",
      detail:
        "Re-read every PDF page with Tesseract. Useful for broken text layers.",
      disabled: officeText,
    },
    {
      id: "vision",
      icon: Sparkles,
      label: "Full-page vision",
      detail: vision
        ? "A vision model interprets page images, charts and complex layouts."
        : "Configure a public vision model in Admin to enable this method.",
      disabled: !vision || officeText,
    },
  ] as const;
  return (
    <Dialog
      open={open}
      onOpenChange={(value) => {
        if (!value && !busy) onClose();
      }}
      title={
        reprocess
          ? "Reprocess this source"
          : conversationId
            ? "Attach to this conversation"
            : "Add knowledge"
      }
      description={
        reprocess
          ? "A new revision is reviewed before replacing the active version."
          : `Choose how Tampak-Chat reads a source for ${bot.name}.`
      }
      className="upload-dialog"
    >
      <form onSubmit={submit} className="dialog-body">
        {error && <ErrorBanner message={error} />}
        <label
          className={`file-drop ${dragging ? "drag-over" : ""}`}
          onDragOver={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(event) => {
            event.preventDefault();
            setDragging(false);
            selectFile(event.dataTransfer.files[0]);
          }}
        >
          <input
            type="file"
            accept=".pdf,.docx,.txt,.md,.csv,.xlsx,.png,.jpg,.jpeg,.webp"
            onChange={(event) => selectFile(event.target.files?.[0])}
          />
          <UploadCloud size={30} />
          <strong>
            {file
              ? file.name
              : reprocess
                ? "Optional: choose a replacement file"
                : "Drop a file here, or browse"}
          </strong>
          <span>
            {file
              ? `${(file.size / 1024).toFixed(0)} KB · ${file.type || "document"}`
              : "PDF, DOCX, text, CSV, XLSX and images · up to 10 MB"}
          </span>
        </label>

        {reprocess && (
          <p className="muted small">
            Keep {reprocess.name} and change processing settings, or choose an
            updated file in the same format.
          </p>
        )}
        <div className="section-heading">
          <h3>How should we read it?</h3>
          <Badge>Per document</Badge>
        </div>
        <div
          className="method-grid"
          role="radiogroup"
          aria-label="Document processing method"
        >
          {methods.map((method) => (
            <label
              key={method.id}
              className={`method-option ${options.method === method.id ? "selected" : ""} ${method.disabled ? "disabled" : ""}`}
            >
              <input
                type="radio"
                name="method"
                value={method.id}
                checked={options.method === method.id}
                disabled={method.disabled}
                onChange={() => setOptions({ ...options, method: method.id })}
              />
              <method.icon size={20} />
              <div>
                <strong>{method.label}</strong>
                <p>{method.detail}</p>
              </div>
            </label>
          ))}
        </div>
        <label className="checkbox-row">
          <input
            type="checkbox"
            checked={options.enrich_figures}
            disabled={!vision || (!visualFile && suffix !== "docx")}
            onChange={(event) =>
              setOptions({ ...options, enrich_figures: event.target.checked })
            }
          />
          <span>
            <strong>Describe figures with vision</strong>
            <small>
              Keep the local extraction and add grounded descriptions of images
              and charts. Up to 10 figures.
            </small>
          </span>
        </label>
        <details className="advanced-options">
          <summary>Page range, OCR, tables & chunking</summary>
          <div className="advanced-grid">
            <label>
              First physical page
              <input
                type="number"
                min={1}
                max={50}
                disabled={!visualFile}
                value={options.page_start}
                onChange={(event) =>
                  setOptions({
                    ...options,
                    page_start: Number(event.target.value),
                  })
                }
              />
            </label>
            <label>
              Last physical page
              <input
                type="number"
                min={options.page_start}
                max={50}
                disabled={!visualFile}
                value={options.page_end ?? ""}
                placeholder="All remaining"
                onChange={(event) =>
                  setOptions({
                    ...options,
                    page_end: event.target.value
                      ? Number(event.target.value)
                      : null,
                  })
                }
              />
            </label>
            <label>
              Table reconstruction
              <select
                disabled={!["auto", "layout", "ocr"].includes(options.method)}
                value={options.table_mode}
                onChange={(event) =>
                  setOptions({
                    ...options,
                    table_mode:
                      event.target.value === "fast" ? "fast" : "accurate",
                  })
                }
              >
                <option value="accurate">TableFormer · accurate</option>
                <option value="fast">TableFormer · fast</option>
              </select>
            </label>
            <label>
              Remote processing budget · USD
              <input
                type="number"
                min={0}
                max={10}
                step="0.01"
                value={options.processing_budget_usd}
                onChange={(event) =>
                  setOptions({
                    ...options,
                    processing_budget_usd: Number(event.target.value),
                  })
                }
              />
            </label>
            <p className="muted small">
              Installed OCR engine: Tesseract · English and Bahasa Indonesia.
              Page numbers refer to the original file.
            </p>

            <fieldset>
              <legend>OCR languages</legend>
              {(["eng", "ind"] as const).map((language) => (
                <label className="checkbox-row" key={language}>
                  <input
                    type="checkbox"
                    checked={options.languages.includes(language)}
                    onChange={(event) =>
                      setOptions({
                        ...options,
                        languages: event.target.checked
                          ? [...options.languages, language]
                          : options.languages.filter(
                                (item) => item !== language,
                              ).length
                            ? options.languages.filter(
                                (item) => item !== language,
                              )
                            : ["eng"],
                      })
                    }
                  />
                  {language === "eng" ? "English" : "Bahasa Indonesia"}
                </label>
              ))}
            </fieldset>
            <label>
              Chunk size (characters)
              <input
                type="number"
                min={500}
                max={3000}
                step={100}
                value={options.chunk_size}
                onChange={(event) =>
                  setOptions({
                    ...options,
                    chunk_size: Number(event.target.value),
                  })
                }
              />
            </label>
            <label>
              Chunk overlap
              <input
                type="number"
                min={0}
                max={300}
                step={20}
                value={options.chunk_overlap}
                onChange={(event) =>
                  setOptions({
                    ...options,
                    chunk_overlap: Number(event.target.value),
                  })
                }
              />
            </label>
          </div>
        </details>
        <div className="privacy-note">
          <strong>Know where your file goes</strong>
          <p>
            Native and OCR extraction run locally. Vector indexing sends
            approved text to Qwen3 Embedding 8B through OpenRouter. Vision sends
            selected page or figure images to the configured vision provider.
          </p>
          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={options.remote_consent}
              onChange={(event) =>
                setOptions({ ...options, remote_consent: event.target.checked })
              }
            />
            <span>
              This source contains no confidential or personal data. Allow
              remote embedding
              {options.method === "vision" || options.enrich_figures
                ? " and vision processing"
                : ""}
              .
            </span>
          </label>
        </div>
        <div className="upload-sequence">
          <span>1. Extract</span>
          <span>→</span>
          <span>2. Review</span>
          <span>→</span>
          <span>3. Index</span>
          <span>→</span>
          <span>4. Ready for chat</span>
        </div>
        <div className="dialog-footer">
          <p>Originals and source locations are preserved.</p>
          <Button
            type="button"
            variant="ghost"
            onClick={onClose}
            disabled={busy}
          >
            Cancel
          </Button>
          <Button
            variant="primary"
            type="submit"
            busy={busy}
            disabled={
              (!reprocess && !file) ||
              ((options.method === "vision" || options.enrich_figures) &&
                !options.remote_consent)
            }
          >
            {reprocess ? "Create new revision" : "Upload & extract"}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
