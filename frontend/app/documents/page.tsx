"use client";
import { useState, useEffect, useRef } from "react";
import { getDocuments, uploadDocument, deleteDocument, reindexDocument, type Document } from "@/lib/api";

export default function DocumentsPage() {
  const [docs, setDocs] = useState<Document[]>([]);
  const [uploading, setUploading] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => { getDocuments().then(setDocs).catch(() => {}); }, []);

  const handleUpload = async (files: FileList | null) => {
    if (!files) return;
    setUploading(true);
    for (const file of Array.from(files)) {
      try {
        await uploadDocument(file);
      } catch (err: any) {
        alert(`Failed to upload ${file.name}: ${err.message}`);
      }
    }
    setUploading(false);
    getDocuments().then(setDocs).catch(() => {});
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this document?")) return;
    await deleteDocument(id).catch(() => {});
    setDocs(prev => prev.filter(d => d.id !== id));
  };

  const handleReindex = async (id: string) => {
    await reindexDocument(id).catch(() => {});
    getDocuments().then(setDocs).catch(() => {});
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="min-h-screen bg-surface-900 text-white">
      <div className="max-w-4xl mx-auto px-6 py-8">
        <div className="flex items-center justify-between mb-8">
          <div>
            <a href="/" className="text-sm text-nova-400 hover:text-nova-300 mb-2 inline-block">← Back to Chat</a>
            <h1 className="text-2xl font-bold">📄 Documents</h1>
            <p className="text-surface-400 text-sm mt-1">Upload documents for RAG search</p>
          </div>
        </div>

        {/* Upload Zone */}
        <div className={`border-2 border-dashed rounded-2xl p-10 text-center mb-8 transition-all cursor-pointer ${dragActive ? "border-nova-500 bg-nova-500/5" : "border-surface-600 hover:border-surface-500"}`}
          onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
          onDragLeave={() => setDragActive(false)}
          onDrop={(e) => { e.preventDefault(); setDragActive(false); handleUpload(e.dataTransfer.files); }}
          onClick={() => fileRef.current?.click()}>
          <input ref={fileRef} type="file" accept=".pdf,.txt,.md,.docx" multiple onChange={(e) => handleUpload(e.target.files)} className="hidden" />
          <p className="text-3xl mb-3">{uploading ? "⏳" : "📁"}</p>
          <p className="text-surface-300 text-sm">{uploading ? "Uploading..." : "Drop files here or click to upload"}</p>
          <p className="text-surface-500 text-xs mt-2">Supports PDF, TXT, Markdown, DOCX (max 25MB)</p>
        </div>

        {/* Document List */}
        <div className="space-y-3">
          {docs.map(doc => (
            <div key={doc.id} className="bg-surface-800 rounded-xl p-4 border border-surface-600 flex items-center gap-4">
              <div className="w-10 h-10 rounded-lg bg-surface-700 flex items-center justify-center text-lg">
                {doc.file_extension === "pdf" ? "📕" : doc.file_extension === "docx" ? "📘" : "📄"}
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-medium text-sm truncate">{doc.original_filename}</p>
                <p className="text-surface-500 text-xs">{formatSize(doc.file_size_bytes)} · {doc.chunk_count} chunks · {doc.status}</p>
              </div>
              <div className="flex gap-2">
                <button onClick={() => handleReindex(doc.id)} className="px-3 py-1.5 rounded-lg bg-surface-700 text-xs hover:bg-surface-600 transition cursor-pointer" title="Re-index">🔄</button>
                <button onClick={() => handleDelete(doc.id)} className="px-3 py-1.5 rounded-lg bg-red-500/10 text-red-400 text-xs hover:bg-red-500/20 transition cursor-pointer" title="Delete">🗑</button>
              </div>
            </div>
          ))}
          {docs.length === 0 && <p className="text-center text-surface-500 py-12">No documents uploaded yet</p>}
        </div>
      </div>
    </div>
  );
}
