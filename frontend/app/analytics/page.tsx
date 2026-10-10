"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { ArrowLeft, RefreshCw, Activity, MessageSquare, Mic, Zap, Cpu, Search, CheckCircle, AlertTriangle } from "lucide-react";
import { getAnalytics, getStatus, type Analytics } from "@/lib/api";

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="nova-card p-5 bg-white">
      <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-1">
        {label}
      </div>
      <div className="text-2xl font-black text-sky-600">
        {value}
      </div>
      {sub && <div className="text-[11px] text-slate-400 mt-1">{sub}</div>}
    </div>
  );
}

function BarChart({ data, title }: { data: Record<string, number>; title: string }) {
  const entries = Object.entries(data).sort((a, b) => b[1] - a[1]);
  const max = Math.max(...entries.map((e) => e[1]), 1);

  return (
    <div className="nova-card p-5 bg-white">
      <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 mb-4">{title}</h3>
      <div className="space-y-2.5">
        {entries.map(([label, value]) => (
          <div key={label} className="flex items-center gap-3">
            <span className="text-xs text-slate-600 w-32 truncate">{label}</span>
            <div className="flex-1 h-4 bg-slate-100 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full bg-gradient-to-r from-sky-400 to-blue-600 transition-all"
                style={{ width: `${(value / max) * 100}%` }}
              />
            </div>
            <span className="text-xs font-semibold text-slate-700 w-8 text-right">{value}</span>
          </div>
        ))}
        {entries.length === 0 && (
          <p className="text-slate-400 text-xs py-4 text-center">No telemetry recorded yet</p>
        )}
      </div>
    </div>
  );
}

export default function AnalyticsPage() {
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [status, setStatus] = useState<any>(null);

  useEffect(() => {
    getAnalytics().then(setAnalytics).catch(() => {});
    getStatus().then(setStatus).catch(() => {});
  }, []);

  return (
    <div className="min-h-screen bg-[#f8fafc] text-slate-800">
      <div className="max-w-5xl mx-auto px-6 py-8">
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-sky-600 hover:text-sky-700 mb-6 transition-colors"
        >
          <ArrowLeft size={14} />
          <span>Back to NOVA</span>
        </Link>

        <div className="flex items-center justify-between pb-4 border-b border-slate-200 mb-6">
          <div>
            <h1 className="text-2xl font-extrabold text-slate-900">System Telemetry &amp; Status</h1>
            <p className="text-xs text-slate-500 mt-0.5">
              Runtime health, service availability, and conversation analytics
            </p>
          </div>
          <button
            onClick={() => {
              getAnalytics().then(setAnalytics).catch(() => {});
              getStatus().then(setStatus).catch(() => {});
            }}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white border border-slate-200 text-xs font-semibold text-slate-600 hover:text-sky-600 shadow-xs cursor-pointer"
          >
            <RefreshCw size={13} />
            <span>Refresh</span>
          </button>
        </div>

        {/* Runtime Status Row */}
        {status && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
            <div className="nova-card p-4 bg-white flex items-center justify-between">
              <div>
                <div className="text-[11px] text-slate-400 font-medium">Ollama LLM</div>
                <div className="text-sm font-bold text-slate-800">{status.ollama_available ? "Online" : "Offline"}</div>
              </div>
              <span className={`w-2.5 h-2.5 rounded-full ${status.ollama_available ? "bg-emerald-500 shadow-[0_0_6px_#10b981]" : "bg-red-400"}`} />
            </div>

            <div className="nova-card p-4 bg-white flex items-center justify-between">
              <div>
                <div className="text-[11px] text-slate-400 font-medium">Whisper STT</div>
                <div className="text-sm font-bold text-slate-800">{status.stt_available ? "Ready" : "Offline"}</div>
              </div>
              <span className={`w-2.5 h-2.5 rounded-full ${status.stt_available ? "bg-emerald-500 shadow-[0_0_6px_#10b981]" : "bg-red-400"}`} />
            </div>

            <div className="nova-card p-4 bg-white flex items-center justify-between">
              <div>
                <div className="text-[11px] text-slate-400 font-medium">Native TTS</div>
                <div className="text-sm font-bold text-slate-800">{status.tts_available ? "Ready" : "Offline"}</div>
              </div>
              <span className={`w-2.5 h-2.5 rounded-full ${status.tts_available ? "bg-emerald-500 shadow-[0_0_6px_#10b981]" : "bg-red-400"}`} />
            </div>

            <div className="nova-card p-4 bg-white flex items-center justify-between">
              <div>
                <div className="text-[11px] text-slate-400 font-medium">Vector DB</div>
                <div className="text-sm font-bold text-slate-800">{status.vector_db_ok ? "Operational" : "Offline"}</div>
              </div>
              <span className={`w-2.5 h-2.5 rounded-full ${status.vector_db_ok ? "bg-emerald-500 shadow-[0_0_6px_#10b981]" : "bg-red-400"}`} />
            </div>
          </div>
        )}

        {/* Stat Cards */}
        {analytics && (
          <>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
              <StatCard label="Conversations" value={analytics.total_conversations} />
              <StatCard label="Messages" value={analytics.total_messages} />
              <StatCard label="Voice Queries" value={analytics.voice_requests} />
              <StatCard label="Avg Latency" value={`${Math.round(analytics.avg_response_latency_ms)}ms`} />
              <StatCard label="RAG Searches" value={analytics.rag_searches} />
              <StatCard label="Tool Executions" value={analytics.tool_executions} />
              <StatCard label="Total Errors" value={analytics.total_errors} />
              <StatCard label="Avg LLM Time" value={`${Math.round(analytics.avg_llm_duration_ms)}ms`} />
            </div>

            <div className="grid md:grid-cols-2 gap-6 mb-6">
              <BarChart data={analytics.intent_distribution} title="Intent Distribution" />
              <BarChart data={analytics.tool_usage} title="Tool Usage" />
            </div>

            {/* Performance Breakdown */}
            <div className="nova-card p-5 bg-white">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 mb-4">
                Latency Breakdown
              </h3>
              <div className="grid grid-cols-3 gap-4 text-center">
                <div className="p-3 bg-slate-50 rounded-xl">
                  <div className="text-[11px] text-slate-400 mb-1">Avg STT Duration</div>
                  <div className="text-lg font-bold text-sky-600">{Math.round(analytics.avg_stt_duration_ms)}ms</div>
                </div>
                <div className="p-3 bg-slate-50 rounded-xl">
                  <div className="text-[11px] text-slate-400 mb-1">Avg LLM Duration</div>
                  <div className="text-lg font-bold text-sky-600">{Math.round(analytics.avg_llm_duration_ms)}ms</div>
                </div>
                <div className="p-3 bg-slate-50 rounded-xl">
                  <div className="text-[11px] text-slate-400 mb-1">Avg TTS Duration</div>
                  <div className="text-lg font-bold text-sky-600">{Math.round(analytics.avg_tts_duration_ms)}ms</div>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
