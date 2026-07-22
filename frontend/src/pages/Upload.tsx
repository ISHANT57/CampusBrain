import { useRef, useState } from "react";

import { api } from "../api/client";

type Item = { name: string; status: string; error?: string };

const TERMINAL = ["processed", "failed"];

export default function Upload() {
  const [items, setItems] = useState<Item[]>([]);
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

  return (
    <div className="page">
      <h2>Upload documents</h2>
      <p className="muted">
        PDF, Word (.doc/.docx), PowerPoint (.ppt/.pptx), Excel (.xls/.xlsx), CSV, Markdown, TXT,
        JSON, HTML or XML. Max 100 MB.
      </p>

      <div
        className="dropzone"
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          if (e.dataTransfer.files) handleFiles(e.dataTransfer.files);
        }}
      >
        Drop files here, or click to choose
        <input
          ref={inputRef}
          type="file"
          multiple
          hidden
          // Mirrors backend/app/core/upload_policy.py's SUPPORTED_TYPES keys —
          // a browser-level hint only, not real validation (the backend
          // re-checks the actual file bytes regardless; this list is a
          // second source of truth to keep in sync manually, not shared code,
          // since the frontend can't import a Python module).
          accept=".pdf,.txt,.md,.csv,.xlsx,.xls,.docx,.doc,.pptx,.ppt,.json,.html,.xml"
          onChange={(e) => e.target.files && handleFiles(e.target.files)}
        />
      </div>

      {items.length > 0 && (
        <table className="uploads">
          <tbody>
            {items.map((i) => (
              <tr key={i.name}>
                <td>{i.name}</td>
                <td className={`status ${i.status}`}>{i.status}</td>
                <td className="error">{i.error ?? ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
