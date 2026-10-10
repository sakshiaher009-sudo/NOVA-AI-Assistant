"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { ArrowLeft, Clock, Trash2, Check, Bell } from "lucide-react";
import { getReminders, createReminder, updateReminder, deleteReminder, type Reminder } from "@/lib/api";

export default function RemindersPage() {
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [newTitle, setNewTitle] = useState("");
  const [newDate, setNewDate] = useState("");

  useEffect(() => {
    getReminders().then(setReminders).catch(() => {});
  }, []);

  const handleCreate = async () => {
    if (!newTitle.trim()) return;
    await createReminder(newTitle.trim(), newDate || undefined);
    setNewTitle("");
    setNewDate("");
    getReminders().then(setReminders).catch(() => {});
  };

  const handleToggle = async (rem: Reminder) => {
    const nextStatus = rem.status === "completed" ? "pending" : "completed";
    await updateReminder(rem.id, { status: nextStatus });
    getReminders().then(setReminders).catch(() => {});
  };

  const handleDelete = async (id: string) => {
    await deleteReminder(id);
    setReminders((prev) => prev.filter((r) => r.id !== id));
  };

  const pending = reminders.filter((r) => r.status === "pending");
  const completed = reminders.filter((r) => r.status === "completed");

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

        <div className="pb-4 border-b border-slate-200 mb-6">
          <h1 className="text-2xl font-extrabold text-slate-900">Reminders</h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Keep track of scheduled alerts, to-dos, and tasks
          </p>
        </div>

        {/* Create Reminder Card */}
        <div className="nova-card p-5 bg-white mb-6">
          <h3 className="text-xs font-bold uppercase tracking-wider text-sky-700 mb-3">
            Add Reminder
          </h3>
          <div className="flex flex-col sm:flex-row gap-3">
            <input
              type="text"
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              placeholder="What to remember..."
              className="flex-1 px-3 py-2 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-800 outline-none focus:border-sky-500 transition-colors"
            />
            <input
              type="datetime-local"
              value={newDate}
              onChange={(e) => setNewDate(e.target.value)}
              className="px-3 py-2 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-600 outline-none focus:border-sky-500 transition-colors"
            />
            <button
              onClick={handleCreate}
              disabled={!newTitle.trim()}
              className="px-5 py-2 rounded-xl bg-sky-500 hover:bg-sky-600 disabled:bg-slate-200 text-white text-xs font-semibold shadow-sm transition-all cursor-pointer whitespace-nowrap"
            >
              Add
            </button>
          </div>
        </div>

        {/* Pending Reminders */}
        {pending.length > 0 && (
          <div className="mb-8">
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-3">
              Pending ({pending.length})
            </h2>
            <div className="space-y-2">
              {pending.map((rem) => (
                <div
                  key={rem.id}
                  className="nova-card p-3.5 bg-white flex items-center justify-between group hover:border-sky-300 transition-all"
                >
                  <div className="flex items-center gap-3">
                    <button
                      onClick={() => handleToggle(rem)}
                      className="w-5 h-5 rounded-full border-2 border-slate-300 hover:border-sky-500 flex items-center justify-center transition-colors cursor-pointer"
                    />
                    <div>
                      <p className="text-xs font-bold text-slate-800">{rem.title}</p>
                      {rem.scheduled_at && (
                        <p className="text-[10px] text-slate-400 mt-0.5 flex items-center gap-1">
                          <Clock size={11} />
                          <span>{new Date(rem.scheduled_at).toLocaleString()}</span>
                        </p>
                      )}
                    </div>
                  </div>
                  <button
                    onClick={() => handleDelete(rem.id)}
                    className="opacity-0 group-hover:opacity-100 p-1 text-slate-400 hover:text-red-500 cursor-pointer rounded transition-opacity"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Completed Reminders */}
        {completed.length > 0 && (
          <div>
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3">
              Completed ({completed.length})
            </h2>
            <div className="space-y-2 opacity-60">
              {completed.map((rem) => (
                <div
                  key={rem.id}
                  className="nova-card p-3 bg-white flex items-center justify-between group"
                >
                  <div className="flex items-center gap-3">
                    <button
                      onClick={() => handleToggle(rem)}
                      className="w-5 h-5 rounded-full bg-emerald-500 text-white flex items-center justify-center text-[10px] cursor-pointer"
                    >
                      <Check size={12} />
                    </button>
                    <p className="text-xs text-slate-500 line-through">{rem.title}</p>
                  </div>
                  <button
                    onClick={() => handleDelete(rem.id)}
                    className="opacity-0 group-hover:opacity-100 p-1 text-slate-400 hover:text-red-500 cursor-pointer rounded transition-opacity"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {reminders.length === 0 && (
          <div className="text-center py-12 text-slate-400 text-xs">
            No reminders scheduled yet
          </div>
        )}
      </div>
    </div>
  );
}
