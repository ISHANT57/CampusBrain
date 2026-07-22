import { useRef, useState, type DragEvent, type KeyboardEvent } from "react";
import { CheckCircle2, Loader2, UploadCloud, XCircle } from "lucide-react";

import { api } from "../api/client";
import { Badge } from "../components/chat/ui/primitives";
import { cn } from "../components/chat/lib/utils";

type Status = "uploading" | "pending" | "processing" | "processed" | "failed";
type Item = { name: string; status: Status; error?: string };

const TERMINAL = ["processed", "failed"];

// Literal Tailwind classes, not built from a template string — Tailwind's
// scanner needs to see the exact class name in source to generate it.
const STATUS_META: Record<Status, { label: string; icon: typeof CheckCircle2; badge: string; icon_color: string; spin?: boolean }> = {
  uploading: { label: "Uploading", icon: Loader2, badge: "warning", icon_color: "text-warning", spin: true },
  pending: { label: "Pending", icon: Loader2, badge: "warning", icon_color: "text-warning", spin: true },
  processing: { label: "Processing", icon: Loader2, badge: "warning", icon_color: "text-warning", spin: true },
  processed: { label: "Processed", icon: CheckCircle2, badge: "success", icon_color: "text-success" },
  failed: { label: "Failed", icon: XCircle, badge: "error", icon_color: "text-error" },
};

export default function Upload() {
  const [items, setItems] = useState<Item[]>([]);
  const [dragActive, setDragActive] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const update = (name: string, patch: Partial<Item>) =>
    setItems((list) => list.map((i) => (i.name === name ? { ...i, ...patch } : i)));

  // Poll until the background worker finishes extracting/chunking/embedding.
  const pollUntilDone = (name: string, id: number) => {
    const timer = setInterval(async () => {
      try {
        const doc = await api.getDocument(id);
        update(name, { status: doc.status });
        if (TERMINAL.includes(doc.status)) clearInterval(timer);
      } catch {
        clearInterval(timer);
      }
    }, 2000);
  };

  const handleFiles = async (files: FileList) => {
    for (const file of Array.from(files)) {
      setItems((list) => [...list, { name: file.name, status: "uploading" }]);
      try {
        const doc = await api.uploadDocument(file);
        update(file.name, { status: doc.status });
        pollUntilDone(file.name, doc.id);
      } catch (err) {
        update(file.name, { status: "failed", error: (err as Error).message });
      }
    }
  };

  const openPicker = () => inputRef.current?.click();
  const onDropzoneKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      openPicker();
    }
  };
  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragActive(false);
    if (e.dataTransfer.files.length) handleFiles(e.dataTransfer.files);
  };

  return (
    <div className="mx-auto max-w-[760px] px-6 py-10">
      <div className="mb-6">
        <p className="eyebrow">Knowledge base</p>
        <h1 className="mt-1.5 text-[22px] font-medium tracking-[-0.01em] text-ink">Upload documents</h1>
        <p className="mt-1.5 max-w-[540px] text-[13.5px] leading-[1.55] text-muted">
          PDF, Word (.doc/.docx), PowerPoint (.ppt/.pptx), Excel (.xls/.xlsx), CSV, Markdown, TXT,
          JSON, HTML or XML. Max 100 MB per file.
        </p>
      </div>

      <div
        onClick={openPicker}
        onKeyDown={onDropzoneKeyDown}
        onDragOver={(e) => {
          e.preventDefault();
          setDragActive(true);
        }}
        onDragLeave={() => setDragActive(false)}
        onDrop={onDrop}
        role="button"
        tabIndex={0}
        aria-label="Upload documents — drop files here or press Enter to choose"
        className={cn(
          "flex cursor-pointer flex-col items-center gap-3 rounded-[var(--radius-panel)] border-2 border-dashed px-6 py-14 text-center transition-colors duration-150",
          dragActive
            ? "border-accent bg-accent-soft"
            : "border-border bg-sunken hover:border-border-strong hover:bg-surface",
        )}
      >
        <span className="flex size-11 items-center justify-center rounded-full bg-surface text-accent shadow-[var(--shadow-card)]">
          <UploadCloud className="size-5" />
        </span>
        <p className="text-[14px] font-medium text-ink">
          {dragActive ? "Drop to upload" : "Drop files here, or click to choose"}
        </p>
        <p className="text-[12.5px] text-faint">Multiple files supported</p>
        <input
          ref={inputRef}
          type="file"
          multiple
          hidden
          tabIndex={-1}
          accept=".pdf,.txt,.md,.csv,.xlsx,.xls,.docx,.doc,.pptx,.ppt,.json,.html,.xml"
          onChange={(e) => e.target.files && handleFiles(e.target.files)}
        />
      </div>

      {items.length > 0 && (
        <ul className="mt-6 flex flex-col gap-2">
          {items.map((i) => {
            const meta = STATUS_META[i.status];
            return (
              <li key={i.name} className="rounded-[var(--radius-card)] border border-border bg-surface px-4 py-3">
                <div className="flex items-center gap-3">
                  <meta.icon
                    className={cn("size-4 shrink-0", meta.icon_color, meta.spin && "animate-spin")}
                    aria-hidden="true"
                  />
                  <span className="min-w-0 flex-1 truncate text-[13.5px] text-ink">{i.name}</span>
                  <Badge variant={meta.badge as "success" | "warning" | "error"}>{meta.label}</Badge>
                </div>
                {i.error && <p className="mt-2 pl-7 text-[12.5px] leading-[1.5] text-error">{i.error}</p>}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
