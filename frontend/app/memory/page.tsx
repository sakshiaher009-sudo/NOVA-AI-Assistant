"use client";
import { useState, useEffect } from "react";
import { getMemories, createMemory, deleteMemory, type MemoryItem } from "@/lib/api";

export default function MemoryPage() {
  const [memories, setMemories] = useState<MemoryItem[]>([]);
  const [newContent, setNewContent] = useState("");

  useEffect(() => { getMemories().then(setMemories).catch(() => {}); }, []);

  const handleCreate = async () => {
    if (!newContent.trim()) return;
    await createMemory(newContent.trim());
    setNewContent("");
    getMemories().then(setMemories).catch(() => {});
  };

  const handleDelete = async (id: string) => {
    await deleteMemory(id);
    setMemories(prev => prev.filter(m => m.id !== id));
  };

  return (
    <div className="min-h-screen bg-surface-900 text-white">
      <div className="max-w-4xl mx-auto px-6 py-8">
        <a href="/" className="text-sm text-nova-400 hover:text-nova-300 mb-2 inline-block">← Back to Chat</a>
        <h1 className="text-2xl font-bold mb-2">🧠 Memory</h1>
        <p className="text-surface-400 text-sm mb-6">Long-term memories stored by NOVA. You can inspect and delete them.</p>

        <div className="bg-surface-800 rounded-xl p-4 border border-surface-600 mb-6 flex gap-3">
          <input type="text" value={newContent} onChange={e => setNewContent(e.target.value)} placeholder="Add a memory..."
            className="flex-1 bg-surface-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-nova-500 placeholder-surface-500"
            onKeyDown={e => { if (e.key === "Enter") handleCreate(); }} />
          <button onClick={handleCreate} disabled={!newContent.trim()}
            className="px-4 py-2 rounded-lg bg-nova-600 hover:bg-nova-500 disabled:bg-surface-700 text-sm transition cursor-pointer">Add</button>
        </div>

        <div className="space-y-2">
          {memories.map(m => (
            <div key={m.id} className="bg-surface-800 rounded-xl p-4 border border-surface-600 flex items-start gap-3 group">
              <span className="text-sm mt-0.5">💭</span>
              <div className="flex-1">
                <p className="text-sm">{m.content}</p>
                <p className="text-[10px] text-surface-500 mt-1">{m.category} · {m.source} · {new Date(m.created_at).toLocaleDateString()}</p>
              </div>
              <button onClick={() => handleDelete(m.id)} className="opacity-0 group-hover:opacity-100 text-red-400 text-xs cursor-pointer transition-opacity">🗑</button>
            </div>
          ))}
          {memories.length === 0 && <p className="text-center text-surface-500 py-12">No memories stored yet</p>}
        </div>
      </div>
    </div>
  );
}
