"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { ArrowLeft, Plus, StickyNote, Edit3, Trash2, Search } from "lucide-react";
import { getNotes, createNote, updateNote, deleteNote, type Note } from "@/lib/api";

export default function NotesPage() {
  const [notes, setNotes] = useState<Note[]>([]);
  const [newTitle, setNewTitle] = useState("");
  const [newContent, setNewContent] = useState("");
  const [search, setSearch] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);

  useEffect(() => {
    getNotes().then(setNotes).catch(() => {});
  }, []);

  const handleCreate = async () => {
    if (!newTitle.trim()) return;
    await createNote(newTitle.trim(), newContent.trim());
    setNewTitle("");
    setNewContent("");
    getNotes().then(setNotes).catch(() => {});
  };

  const handleDelete = async (id: string) => {
    await deleteNote(id).catch(() => {});
    setNotes((prev) => prev.filter((n) => n.id !== id));
  };

  const handleUpdate = async (id: string, title: string, content: string) => {
    await updateNote(id, { title, content }).catch(() => {});
    setEditingId(null);
    getNotes().then(setNotes).catch(() => {});
  };

  const filteredNotes = notes.filter(
    (n) =>
      n.title.toLowerCase().includes(search.toLowerCase()) ||
      (n.content && n.content.toLowerCase().includes(search.toLowerCase()))
  );

  return (
    <div className="min-h-screen bg-[#f8fafc] text-slate-800">
      <div className="max-w-4xl mx-auto px-6 py-8">
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-sky-600 hover:text-sky-700 mb-6 transition-colors"
        >
          <ArrowLeft size={14} />
          <span>Back to NOVA</span>
        </Link>

        <div className="flex items-center justify-between pb-4 border-b border-slate-200 mb-6">
          <div>
            <h1 className="text-2xl font-extrabold text-slate-900">Notes</h1>
            <p className="text-xs text-slate-500 mt-0.5">
              Keep track of ideas, thoughts, and study points
            </p>
          </div>
          <div className="w-64">
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-white border border-slate-200 text-xs">
              <Search size={14} className="text-slate-400" />
              <input
                type="text"
                placeholder="Search notes..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full bg-transparent outline-none text-slate-700"
              />
            </div>
          </div>
        </div>

        {/* Create Note Card */}
        <div className="nova-card p-5 bg-white mb-6">
          <input
            type="text"
            value={newTitle}
            onChange={(e) => setNewTitle(e.target.value)}
            placeholder="Note title..."
            className="w-full bg-transparent border-b border-slate-200 pb-2 mb-3 text-sm font-semibold text-slate-800 focus:outline-none focus:border-sky-500 placeholder-slate-400"
          />
          <textarea
            value={newContent}
            onChange={(e) => setNewContent(e.target.value)}
            placeholder="Content details or thoughts..."
            rows={2}
            className="w-full bg-transparent text-xs text-slate-600 focus:outline-none placeholder-slate-400 resize-none min-h-[60px]"
          />
          <div className="flex justify-end mt-3 pt-2 border-t border-slate-100">
            <button
              onClick={handleCreate}
              disabled={!newTitle.trim()}
              className="px-4 py-1.5 rounded-lg bg-sky-500 hover:bg-sky-600 disabled:bg-slate-200 text-white text-xs font-semibold shadow-sm transition cursor-pointer"
            >
              Save Note
            </button>
          </div>
        </div>

        {/* Notes Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filteredNotes.map((note) => (
            <div
              key={note.id}
              className="nova-card p-5 bg-white flex flex-col justify-between group hover:border-sky-300 transition-all"
            >
              {editingId === note.id ? (
                <EditNoteForm
                  note={note}
                  onSave={handleUpdate}
                  onCancel={() => setEditingId(null)}
                />
              ) : (
                <>
                  <div>
                    <div className="flex items-start justify-between gap-2">
                      <h3 className="font-bold text-sm text-slate-800 truncate">
                        {note.title}
                      </h3>
                      <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                          onClick={() => setEditingId(note.id)}
                          className="p-1 rounded text-slate-400 hover:text-sky-600 cursor-pointer"
                        >
                          <Edit3 size={13} />
                        </button>
                        <button
                          onClick={() => handleDelete(note.id)}
                          className="p-1 rounded text-slate-400 hover:text-red-500 cursor-pointer"
                        >
                          <Trash2 size={13} />
                        </button>
                      </div>
                    </div>
                    {note.content && (
                      <p className="text-slate-600 text-xs mt-2 whitespace-pre-wrap line-clamp-4 leading-relaxed">
                        {note.content}
                      </p>
                    )}
                  </div>
                  <div className="mt-4 pt-2 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-400">
                    <span>{new Date(note.created_at).toLocaleDateString()}</span>
                    <StickyNote size={12} className="text-sky-400" />
                  </div>
                </>
              )}
            </div>
          ))}
          {filteredNotes.length === 0 && (
            <div className="col-span-2 text-center text-slate-400 py-12 text-xs">
              {search ? "No notes matching search" : "No notes yet. Create your first note above!"}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function EditNoteForm({
  note,
  onSave,
  onCancel,
}: {
  note: Note;
  onSave: (id: string, title: string, content: string) => void;
  onCancel: () => void;
}) {
  const [title, setTitle] = useState(note.title);
  const [content, setContent] = useState(note.content);

  return (
    <div>
      <input
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-1.5 text-xs font-semibold text-slate-800 mb-2 focus:outline-none focus:border-sky-500"
      />
      <textarea
        value={content}
        onChange={(e) => setContent(e.target.value)}
        rows={3}
        className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-1.5 text-xs text-slate-600 mb-2 focus:outline-none focus:border-sky-500 resize-none"
      />
      <div className="flex gap-2 justify-end">
        <button
          onClick={onCancel}
          className="px-3 py-1 rounded text-xs text-slate-500 hover:text-slate-700 cursor-pointer"
        >
          Cancel
        </button>
        <button
          onClick={() => onSave(note.id, title, content)}
          className="px-3 py-1 rounded bg-sky-500 hover:bg-sky-600 text-white text-xs font-semibold cursor-pointer shadow-xs"
        >
          Save
        </button>
      </div>
    </div>
  );
}
