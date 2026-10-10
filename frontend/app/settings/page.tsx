"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { ArrowLeft, Sliders, Volume2, Sparkles, Server } from "lucide-react";
import { getStatus } from "@/lib/api";

export default function SettingsPage() {
  const [status, setStatus] = useState<any>(null);

  useEffect(() => {
    getStatus().then(setStatus).catch(() => {});
  }, []);

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
          <h1 className="text-2xl font-extrabold text-slate-900">Settings</h1>
          <p className="text-xs text-slate-500 mt-0.5">
            System configuration, active models, and local runtime
          </p>
        </div>

        {/* System Status Table */}
        <div className="nova-card p-6 bg-white mb-6">
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-700 mb-4 flex items-center gap-2">
            <Server size={15} className="text-sky-600" />
            <span>Service Health</span>
          </h2>
          {status ? (
            <div className="space-y-3">
              <StatusRow label="Ollama LLM" available={status.ollama_available} detail={status.ollama_model} />
              <StatusRow label="Speech-to-Text (Faster-Whisper)" available={status.stt_available} />
              <StatusRow label="Text-to-Speech (macOS Engine)" available={status.tts_available} />
              <StatusRow label="Relational Database (SQLite)" available={status.database_ok} />
              <StatusRow label="Vector Knowledge Base (Chroma DB)" available={status.vector_db_ok} />
            </div>
          ) : (
            <p className="text-slate-400 text-xs">Loading runtime status...</p>
          )}
        </div>

        {/* Configuration Guide */}
        <div className="nova-card p-6 bg-white mb-6">
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-700 mb-3 flex items-center gap-2">
            <Sliders size={15} className="text-sky-600" />
            <span>Active Configuration (.env)</span>
          </h2>
          <p className="text-xs text-slate-500 mb-4">
            Configuration parameters loaded from the project root environment file.
          </p>
          <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 font-mono text-xs text-slate-700 space-y-1 overflow-x-auto">
            <p><span className="text-sky-600 font-bold">OLLAMA_MODEL</span>=llama3.2:1b</p>
            <p><span className="text-sky-600 font-bold">STT_MODEL</span>=base</p>
            <p><span className="text-sky-600 font-bold">TTS_ENGINE</span>=macos</p>
            <p><span className="text-sky-600 font-bold">LOG_LEVEL</span>=INFO</p>
          </div>
        </div>

        {/* Quick Setup */}
        <div className="nova-card p-6 bg-white">
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-700 mb-4 flex items-center gap-2">
            <Sparkles size={15} className="text-sky-600" />
            <span>Quick Local Setup</span>
          </h2>
          <div className="space-y-3 text-xs text-slate-600">
            <div className="flex items-start gap-3">
              <span className="font-bold text-sky-600">1.</span>
              <div>
                <p>Install Ollama: <code className="bg-slate-100 px-1.5 py-0.5 rounded font-mono">brew install ollama</code></p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <span className="font-bold text-sky-600">2.</span>
              <div>
                <p>Pull model: <code className="bg-slate-100 px-1.5 py-0.5 rounded font-mono">ollama pull llama3.2:1b</code></p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <span className="font-bold text-sky-600">3.</span>
              <div>
                <p>Start Ollama server: <code className="bg-slate-100 px-1.5 py-0.5 rounded font-mono">ollama serve</code></p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function StatusRow({ label, available, detail }: { label: string; available: boolean; detail?: string }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-slate-100 last:border-0">
      <span className="text-xs font-medium text-slate-700">{label}</span>
      <div className="flex items-center gap-2">
        {detail && <span className="text-[11px] text-slate-400 font-mono">{detail}</span>}
        <div className={`w-2 h-2 rounded-full ${available ? "bg-emerald-500 shadow-[0_0_6px_#10b981]" : "bg-red-400"}`} />
        <span className={`text-xs font-semibold ${available ? "text-emerald-600" : "text-red-500"}`}>
          {available ? "Available" : "Offline"}
        </span>
      </div>
    </div>
  );
}
