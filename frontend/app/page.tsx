"use client";

import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import {
  Home,
  MessageSquare,
  StickyNote,
  Activity,
  Bell,
  Settings,
  Mic,
  Square,
  Paperclip,
  Send,
  MessageCircle,
  Plus,
  X,
  LogIn,
  User,
  LogOut,
  ChevronDown,
  Zap,
  Brain,
  Shield,
  Menu,
  Search,
  Radio,
  CheckCircle,
  Clock,
  Trash2,
  Edit3,
  Volume2,
  Sparkles,
  RefreshCw,
  Sliders,
  Check,
} from "lucide-react";
import { useAuth } from "@/lib/auth";
import {
  sendMessageStream,
  getConversations,
  getConversation,
  deleteConversation,
  getStatus,
  speakText,
  wakeCheck,
  transcribeAudio,
  getNotes,
  createNote,
  updateNote,
  deleteNote,
  getReminders,
  createReminder,
  updateReminder,
  deleteReminder,
  getAnalytics,
  type Conversation,
  type Message,
  type Note,
  type Reminder,
  type Analytics,
} from "@/lib/api";

// Dynamically import 3D sphere (WebGL needs browser context)
const Nova3DSphere = dynamic(
  () => import("./components/Nova3DSphere"),
  { ssr: false }
);

// ─────────────────────────────────────────────────────────────────────────────
// Types & Constants
// ─────────────────────────────────────────────────────────────────────────────
type ActiveTab = "home" | "chat" | "notes" | "status" | "reminders" | "settings";

type JarvisState =
  | "DORMANT"
  | "LISTENING_WAKE"
  | "WAKE_DETECTED"
  | "LISTENING_CMD"
  | "PROCESSING"
  | "THINKING"
  | "PLANNING"
  | "VERIFYING"
  | "RESPONDING"
  | "SPEAKING"
  | "ERROR";

const LABEL: Record<JarvisState, string> = {
  DORMANT:        "Ready to listen",
  LISTENING_WAKE: "Listening for 'Hey NOVA'",
  WAKE_DETECTED:  "Wake Word Detected",
  LISTENING_CMD:  "Listening...",
  PROCESSING:     "Executing Action...",
  THINKING:       "Thinking...",
  PLANNING:       "Planning...",
  VERIFYING:      "Verifying...",
  RESPONDING:     "Responding...",
  SPEAKING:       "Speaking...",
  ERROR:          "Encountered an Error",
};

const HINT: Record<JarvisState, string> = {
  DORMANT:        "Say \"Hey NOVA\" to activate",
  LISTENING_WAKE: "Say \"Hey NOVA\" or tap the microphone",
  WAKE_DETECTED:  "Yes? How can I help you?",
  LISTENING_CMD:  "Speak your question or instruction...",
  PROCESSING:     "Executing your action...",
  THINKING:       "Analyzing and generating answer...",
  PLANNING:       "Formulating steps...",
  VERIFYING:      "Verifying system state...",
  RESPONDING:     "Streaming response...",
  SPEAKING:       "NOVA is speaking — tap mic to pause",
  ERROR:          "Tap microphone to retry.",
};

function mapToVisualState(jarvisState: string): "dormant" | "listening" | "speaking" | "thinking" | "error" {
  switch (jarvisState) {
    case "LISTENING_WAKE":
    case "WAKE_DETECTED":
    case "LISTENING_CMD":
      return "listening";
    case "SPEAKING":
      return "speaking";
    case "PROCESSING":
    case "THINKING":
    case "PLANNING":
    case "VERIFYING":
    case "RESPONDING":
      return "thinking";
    case "ERROR":
      return "error";
    default:
      return "dormant";
  }
}

function formatTime(isoString?: string): string {
  if (!isoString) {
    return new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  }
  try {
    const d = new Date(isoString);
    return isNaN(d.getTime())
      ? new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })
      : d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  } catch {
    return new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Audio Waveform Component
// ─────────────────────────────────────────────────────────────────────────────
function Waveform({
  active,
  amplitude,
}: {
  active: boolean;
  amplitude: number;
}) {
  const bars = [10, 16, 24, 14, 30, 20, 12, 26, 18, 11, 22, 14, 8];

  return (
    <div
      className={`flex items-center gap-[3px] h-8 my-2 ${
        active ? "nova-waveform-active" : ""
      }`}
      aria-hidden="true"
    >
      {bars.map((defaultHeight, i) => {
        const dynamicHeight = active
          ? Math.max(8, Math.min(32, defaultHeight * (1 + amplitude * 1.6)))
          : defaultHeight * 0.55;
        return (
          <div
            key={i}
            className="nova-waveform-bar"
            style={{
              height: `${dynamicHeight}px`,
              opacity: active ? 0.95 : 0.4,
            }}
          />
        );
      })}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Profile / Sign In Menu Component
// ─────────────────────────────────────────────────────────────────────────────
function ProfileMenu() {
  const { user, isLoading, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  if (isLoading) {
    return (
      <div className="w-8 h-8 rounded-full bg-slate-100 animate-pulse border border-slate-200" />
    );
  }

  if (!user) {
    return (
      <Link
        href="/login"
        className="flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-white hover:bg-sky-50/80 border border-slate-200 hover:border-sky-300 transition-all text-xs font-semibold text-slate-700 shadow-sm"
      >
        <User size={14} className="text-sky-600" />
        <span>Sign In</span>
      </Link>
    );
  }

  const initial = (user.name || "User").charAt(0).toUpperCase();

  return (
    <div ref={menuRef} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 px-2.5 py-1 rounded-full bg-white hover:bg-sky-50/60 border border-slate-200/80 transition-all text-xs font-medium text-slate-700 cursor-pointer shadow-sm"
      >
        <div className="w-7 h-7 rounded-full bg-gradient-to-tr from-blue-600 to-sky-400 text-white font-bold text-xs flex items-center justify-center shadow-sm">
          {initial}
        </div>
        <span className="hidden sm:inline font-semibold">{user.name}</span>
        <ChevronDown size={12} className="text-slate-400" />
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 w-52 nova-glass-card rounded-2xl py-1.5 z-50 animate-fadeIn">
          <div className="px-3.5 py-2.5 border-b border-slate-100">
            <p className="text-xs font-bold text-slate-900">{user.name}</p>
            <p className="text-[11px] text-slate-400 truncate">{user.email}</p>
          </div>
          <button
            onClick={async () => {
              await logout();
              setOpen(false);
            }}
            className="w-full px-3.5 py-2.5 text-xs text-left text-slate-600 hover:text-red-600 hover:bg-red-50/50 flex items-center gap-2 transition-colors cursor-pointer"
          >
            <LogOut size={13} />
            <span>Sign out</span>
          </button>
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Sidebar Component
// ─────────────────────────────────────────────────────────────────────────────
function Sidebar({
  activeTab,
  onTabChange,
  conversations,
  activeId,
  onSelect,
  onNew,
  onDelete,
  mobileOpen,
  onMobileClose,
}: {
  activeTab: ActiveTab;
  onTabChange: (tab: ActiveTab) => void;
  conversations: Conversation[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  mobileOpen: boolean;
  onMobileClose: () => void;
}) {
  const [searchQuery, setSearchQuery] = useState("");

  const filteredConversations = useMemo(() => {
    if (!searchQuery.trim()) return conversations;
    const q = searchQuery.toLowerCase();
    return conversations.filter(
      (c) => (c.title || "").toLowerCase().includes(q)
    );
  }, [conversations, searchQuery]);

  return (
    <>
      {/* Mobile overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 bg-slate-900/20 backdrop-blur-xs z-30 md:hidden"
          onClick={onMobileClose}
        />
      )}

      <aside
        className={`nova-sidebar w-68 sm:w-72 flex flex-col h-screen shrink-0 select-none z-40
        fixed md:relative md:translate-x-0 transition-transform duration-300
        ${mobileOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"}`}
      >
        {/* Top Branding & New Conversation */}
        <div className="p-5 border-b border-slate-100">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              {/* Preserved NOVA Logo */}
              <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-blue-600 via-sky-500 to-sky-400 flex items-center justify-center text-white font-extrabold text-base shadow-[0_4px_14px_rgba(2,132,199,0.3)]">
                N
              </div>
              <div>
                <div className="text-base font-extrabold tracking-wider text-slate-900">
                  NOVA
                </div>
                <div className="text-[9px] font-semibold text-slate-400 tracking-widest uppercase">
                  VOICE AI ASSISTANT
                </div>
              </div>
            </div>
            <button
              onClick={onMobileClose}
              className="md:hidden p-1.5 text-slate-400 hover:text-slate-600 cursor-pointer rounded-lg hover:bg-slate-100"
            >
              <X size={18} />
            </button>
          </div>

          {/* + New Conversation Button */}
          <button
            onClick={() => {
              onNew();
              onMobileClose();
            }}
            className="w-full py-2.5 px-4 rounded-xl bg-gradient-to-r from-blue-600 via-sky-500 to-sky-400 hover:from-blue-700 hover:to-sky-500 text-white text-xs font-semibold flex items-center justify-center gap-2 transition-all cursor-pointer shadow-[0_4px_14px_rgba(2,132,199,0.25)] active:scale-[0.98]"
          >
            <Plus size={15} />
            <span>New Conversation</span>
          </button>
        </div>

        {/* Semantic Navigation */}
        <div className="px-3 pt-3 pb-2 space-y-1">
          <button
            onClick={() => { onTabChange("home"); onMobileClose(); }}
            className={`nova-nav-item ${activeTab === "home" ? "nova-nav-active" : ""}`}
          >
            <Home size={17} />
            <span>Home</span>
          </button>

          <button
            onClick={() => { onTabChange("chat"); onMobileClose(); }}
            className={`nova-nav-item ${activeTab === "chat" ? "nova-nav-active" : ""}`}
          >
            <MessageSquare size={17} />
            <span>Chat</span>
          </button>

          <button
            onClick={() => { onTabChange("notes"); onMobileClose(); }}
            className={`nova-nav-item ${activeTab === "notes" ? "nova-nav-active" : ""}`}
          >
            <StickyNote size={17} />
            <span>Notes</span>
          </button>

          <button
            onClick={() => { onTabChange("status"); onMobileClose(); }}
            className={`nova-nav-item ${activeTab === "status" ? "nova-nav-active" : ""}`}
          >
            <Activity size={17} />
            <span>Status</span>
          </button>

          <button
            onClick={() => { onTabChange("reminders"); onMobileClose(); }}
            className={`nova-nav-item ${activeTab === "reminders" ? "nova-nav-active" : ""}`}
          >
            <Bell size={17} />
            <span>Reminders</span>
          </button>

          <button
            onClick={() => { onTabChange("settings"); onMobileClose(); }}
            className={`nova-nav-item ${activeTab === "settings" ? "nova-nav-active" : ""}`}
          >
            <Settings size={17} />
            <span>Settings</span>
          </button>
        </div>

        {/* ALL CONVERSATIONS with Search */}
        <div className="flex-1 flex flex-col min-h-0 pt-3 border-t border-slate-100">
          <div className="px-4 mb-2 flex items-center justify-between">
            <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">
              ALL CONVERSATIONS
            </span>
            <span className="text-[10px] text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded-full font-medium">
              {filteredConversations.length}
            </span>
          </div>

          {/* Quick Search */}
          <div className="px-3 mb-2">
            <div className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-slate-50 border border-slate-200/80 focus-within:border-sky-400 focus-within:bg-white transition-all">
              <Search size={13} className="text-slate-400 shrink-0" />
              <input
                type="text"
                placeholder="Search conversations..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full text-xs text-slate-700 bg-transparent outline-none placeholder-slate-400"
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery("")}
                  className="text-slate-400 hover:text-slate-600 cursor-pointer"
                >
                  <X size={12} />
                </button>
              )}
            </div>
          </div>

          {/* Scrollable conversation list */}
          <div className="flex-1 overflow-y-auto px-3 space-y-1">
            {filteredConversations.map((c) => {
              const isSelected = activeId === c.id;
              return (
                <div
                  key={c.id}
                  onClick={() => {
                    onSelect(c.id);
                    onMobileClose();
                  }}
                  className={`group flex items-center justify-between px-3 py-2 rounded-xl text-xs cursor-pointer transition-all ${
                    isSelected
                      ? "bg-sky-50 text-sky-700 font-semibold shadow-xs"
                      : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                  }`}
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <MessageCircle
                      size={14}
                      className={isSelected ? "text-sky-600 shrink-0" : "text-slate-400 group-hover:text-slate-600 shrink-0"}
                    />
                    <div className="truncate">
                      <div className="truncate text-xs">{c.title || "Conversation"}</div>
                      {c.message_count !== undefined && (
                        <div className="text-[10px] text-slate-400 font-normal">
                          {c.message_count} {c.message_count === 1 ? "message" : "messages"}
                        </div>
                      )}
                    </div>
                  </div>

                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onDelete(c.id);
                    }}
                    title="Delete conversation"
                    className="opacity-0 group-hover:opacity-100 p-1 text-slate-400 hover:text-red-500 hover:bg-red-50 transition-all rounded-md cursor-pointer shrink-0"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              );
            })}

            {filteredConversations.length === 0 && (
              <div className="text-center py-8 px-4 text-slate-400 text-xs">
                {searchQuery ? "No matching conversations" : "No conversations yet"}
              </div>
            )}
          </div>
        </div>

        {/* Minimal Footer */}
        <div className="p-3 border-t border-slate-100 text-center">
          <Link
            href="/login"
            className="text-[11px] text-slate-400 hover:text-sky-600 transition-colors"
          >
            Switch Account or Sign In
          </Link>
        </div>
      </aside>
    </>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Chat Message Component
// ─────────────────────────────────────────────────────────────────────────────
function ChatMessageBubble({ msg }: { msg: Message }) {
  const isUser = msg.role === "user";
  const time = formatTime(msg.created_at);

  if (isUser) {
    return (
      <div className="flex items-start justify-end gap-3 mb-6 animate-fadeIn">
        <div className="flex flex-col items-end max-w-[80%] sm:max-w-[70%]">
          <div className="chat-bubble-user px-5 py-3.5 text-sm leading-relaxed whitespace-pre-wrap">
            {msg.content}
          </div>
          <div className="text-[11px] text-slate-400 mt-1 mr-1">{time}</div>
        </div>
        <div className="w-8 h-8 rounded-full bg-slate-200 text-slate-600 flex items-center justify-center shrink-0 shadow-xs">
          <User size={15} />
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-start justify-start gap-3 mb-6 animate-fadeIn">
      <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-blue-600 to-sky-400 text-white font-bold text-xs flex items-center justify-center shrink-0 shadow-[0_2px_8px_rgba(2,132,199,0.3)]">
        N
      </div>
      <div className="flex flex-col items-start max-w-[80%] sm:max-w-[75%]">
        <div className="chat-bubble-assistant px-5 py-3.5 text-sm leading-relaxed text-slate-800 whitespace-pre-wrap">
          {msg.content}

          {msg.tool_name && (
            <div className="mt-3 pt-2.5 border-t border-slate-100 flex items-center gap-2 text-xs text-emerald-600 font-semibold">
              <CheckCircle size={14} />
              <span>Done! Action completed ({msg.tool_name}).</span>
            </div>
          )}
        </div>
        <div className="text-[11px] text-slate-400 mt-1 ml-1">{time}</div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Floating Input Dock Component (Section 15)
// ─────────────────────────────────────────────────────────────────────────────
function InputDock({
  input,
  setInput,
  onSend,
  onOrbClick,
  isRecording,
  isBusy,
}: {
  input: string;
  setInput: (v: string) => void;
  onSend: () => void;
  onOrbClick: () => void;
  isRecording: boolean;
  isBusy: boolean;
}) {
  return (
    <div className="composer-dock w-full max-w-3xl flex items-center gap-2.5 px-3 py-2">
      {/* Microphone button */}
      <button
        type="button"
        onClick={onOrbClick}
        title={isRecording ? "Stop listening" : "Tap to speak"}
        className={`w-10 h-10 rounded-full flex items-center justify-center text-white shrink-0 transition-all cursor-pointer shadow-sm active:scale-95 ${
          isRecording
            ? "bg-red-500 shadow-[0_0_16px_rgba(239,68,68,0.5)] animate-pulse"
            : "bg-sky-500 hover:bg-sky-600 shadow-[0_4px_12px_rgba(14,165,233,0.3)]"
        }`}
      >
        {isRecording ? <Square size={16} /> : <Mic size={18} />}
      </button>

      {/* Text Input */}
      <input
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            onSend();
          }
        }}
        placeholder='Type a message or say "Hey NOVA"...'
        disabled={isBusy}
        className="flex-1 py-2 text-sm text-slate-800 placeholder-slate-400 bg-transparent outline-none"
      />

      {/* Voice Waveform Button */}
      <button
        type="button"
        onClick={onOrbClick}
        title="Voice assistant mode"
        className={`p-2 rounded-full transition-all cursor-pointer ${
          isRecording
            ? "text-red-500 bg-red-50"
            : "text-slate-400 hover:text-sky-600 hover:bg-sky-50"
        }`}
      >
        <Volume2 size={18} />
      </button>

      {/* Send Button */}
      <button
        type="button"
        onClick={onSend}
        disabled={!input.trim() || isBusy}
        title="Send message"
        className={`w-10 h-10 rounded-full flex items-center justify-center text-white shrink-0 transition-all cursor-pointer shadow-sm ${
          input.trim() && !isBusy
            ? "bg-gradient-to-tr from-blue-600 to-sky-500 hover:from-blue-700 hover:to-sky-600 shadow-[0_4px_14px_rgba(2,132,199,0.3)] active:scale-95 cursor-pointer"
            : "bg-slate-200 text-slate-400 cursor-not-allowed shadow-none"
        }`}
      >
        <Send size={16} />
      </button>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Application Page
// ─────────────────────────────────────────────────────────────────────────────
export default function HomePage() {
  // ── Views ──────────────────────────────────────────────────────────────────
  const [activeTab, setActiveTab] = useState<ActiveTab>("home");
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

  // ── UI state ───────────────────────────────────────────────────────────────
  const [jarvisState, setJarvisState] = useState<JarvisState>("DORMANT");
  const [wakeMode, setWakeMode] = useState(false);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [transcript, setTranscript] = useState("");
  const [input, setInput] = useState("");
  const [amplitude, setAmplitude] = useState(0);
  const [ollamaOk, setOllamaOk] = useState<boolean | null>(null);
  const [micDenied, setMicDenied] = useState(false);
  const [errorText, setErrorText] = useState("");

  // ── Notes view state ───────────────────────────────────────────────────────
  const [notes, setNotes] = useState<Note[]>([]);
  const [noteTitle, setNoteTitle] = useState("");
  const [noteContent, setNoteContent] = useState("");
  const [noteSearch, setNoteSearch] = useState("");
  const [editingNoteId, setEditingNoteId] = useState<string | null>(null);

  // ── Reminders view state ───────────────────────────────────────────────────
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [remTitle, setRemTitle] = useState("");
  const [remDate, setRemDate] = useState("");

  // ── Status view state ──────────────────────────────────────────────────────
  const [systemStatus, setSystemStatus] = useState<any>(null);
  const [analytics, setAnalytics] = useState<Analytics | null>(null);

  // ── Refs ───────────────────────────────────────────────────────────────────
  const stateRef = useRef<JarvisState>("DORMANT");
  const wakeModeRef = useRef(false);
  const activeConvRef = useRef<string | null>(null);
  const wakeStreamRef = useRef<MediaStream | null>(null);
  const wakeProcessing = useRef(false);
  const cmdRecorderRef = useRef<MediaRecorder | null>(null);
  const cmdChunksRef = useRef<Blob[]>([]);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioUrlRef = useRef<string | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const ampFrameRef = useRef<number | null>(null);
  const silenceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const cmdMaxTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const audioQueueRef = useRef<{ promise: Promise<Blob> }[]>([]);
  const isPlayingRef = useRef(false);
  const streamDoneRef = useRef(false);

  // ── State Synchronizer ─────────────────────────────────────────────────────
  const go = useCallback((s: JarvisState) => {
    stateRef.current = s;
    setJarvisState(s);
  }, []);

  useEffect(() => {
    activeConvRef.current = activeConvId;
  }, [activeConvId]);

  useEffect(() => {
    wakeModeRef.current = wakeMode;
  }, [wakeMode]);

  useEffect(() => {
    if (activeTab === "chat") {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, activeTab]);

  // ── Initial load ───────────────────────────────────────────────────────────
  useEffect(() => {
    getConversations().then(setConversations).catch(() => {});
    getStatus()
      .then((s) => {
        setSystemStatus(s);
        setOllamaOk(s.ollama_available);
      })
      .catch(() => {
        setOllamaOk(false);
      });
  }, []);

  // Load secondary views data when switching tabs
  useEffect(() => {
    if (activeTab === "notes") {
      getNotes().then(setNotes).catch(() => {});
    } else if (activeTab === "reminders") {
      getReminders().then(setReminders).catch(() => {});
    } else if (activeTab === "status") {
      getStatus().then(setSystemStatus).catch(() => {});
      getAnalytics().then(setAnalytics).catch(() => {});
    }
  }, [activeTab]);

  // ── Amplitude Visualizer ───────────────────────────────────────────────────
  const startAmplitude = useCallback((stream: MediaStream) => {
    try {
      const ctx = new AudioContext();
      const src = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      src.connect(analyser);
      analyserRef.current = analyser;
      const buf = new Uint8Array(analyser.frequencyBinCount);
      const tick = () => {
        if (!analyserRef.current) return;
        analyserRef.current.getByteFrequencyData(buf);
        const rms =
          Math.sqrt(buf.reduce((s, v) => s + v * v, 0) / buf.length) / 128;
        setAmplitude(rms);
        ampFrameRef.current = requestAnimationFrame(tick);
      };
      ampFrameRef.current = requestAnimationFrame(tick);
    } catch {}
  }, []);

  const stopAmplitude = useCallback(() => {
    if (ampFrameRef.current) {
      cancelAnimationFrame(ampFrameRef.current);
      ampFrameRef.current = null;
    }
    analyserRef.current = null;
    setAmplitude(0);
  }, []);

  // ── Audio Playback / TTS Queue ─────────────────────────────────────────────
  const stopAudio = useCallback(() => {
    audioQueueRef.current = [];
    isPlayingRef.current = false;
    streamDoneRef.current = true;
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.src = "";
      audioRef.current = null;
    }
    if (audioUrlRef.current) {
      URL.revokeObjectURL(audioUrlRef.current);
      audioUrlRef.current = null;
    }
  }, []);

  const playAudio = useCallback(
    (blob: Blob, onEnd: () => void) => {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current.src = "";
      }
      if (audioUrlRef.current) {
        URL.revokeObjectURL(audioUrlRef.current);
      }
      const url = URL.createObjectURL(blob);
      audioUrlRef.current = url;
      const audio = new Audio(url);
      audioRef.current = audio;
      go("SPEAKING");
      audio.onended = () => {
        if (audioUrlRef.current) {
          URL.revokeObjectURL(audioUrlRef.current);
          audioUrlRef.current = null;
        }
        audioRef.current = null;
        onEnd();
      };
      audio.onerror = () => {
        if (audioUrlRef.current) {
          URL.revokeObjectURL(audioUrlRef.current);
          audioUrlRef.current = null;
        }
        audioRef.current = null;
        onEnd();
      };
      audio.play().catch(() => onEnd());
    },
    [go]
  );

  const playNextInQueue = useCallback(() => {
    if (isPlayingRef.current) return;
    const item = audioQueueRef.current.shift();
    if (!item) {
      if (streamDoneRef.current) {
        if (wakeModeRef.current) {
          go("LISTENING_WAKE");
          runWakeWordLoop();
        } else {
          go("DORMANT");
        }
      }
      return;
    }
    isPlayingRef.current = true;
    item.promise
      .then((blob) => {
        playAudio(blob, () => {
          isPlayingRef.current = false;
          playNextInQueue();
        });
      })
      .catch(() => {
        isPlayingRef.current = false;
        playNextInQueue();
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [go, playAudio]);

  const addMessage = useCallback((msg: Message) => {
    setMessages((prev) => [...prev, msg]);
  }, []);

  // ── Voice Command Processing ───────────────────────────────────────────────
  const processCommand = useCallback(
    async (blob: Blob) => {
      go("PROCESSING");
      stopAmplitude();
      setTranscript("");
      stopAudio();
      streamDoneRef.current = false;
      isPlayingRef.current = false;
      audioQueueRef.current = [];

      try {
        const stt = await transcribeAudio(blob);
        const txt = (stt.text || "").trim();
        setTranscript(txt);

        if (!txt) {
          go(wakeModeRef.current ? "LISTENING_WAKE" : "DORMANT");
          if (wakeModeRef.current) runWakeWordLoop();
          return;
        }

        const userMsgId = Date.now().toString();
        addMessage({
          id: userMsgId,
          role: "user",
          content: txt,
          is_voice: true,
          created_at: new Date().toISOString(),
        });

        const assistantMsgId = (Date.now() + 1).toString();
        addMessage({
          id: assistantMsgId,
          role: "assistant",
          content: "",
          is_voice: true,
          created_at: new Date().toISOString(),
        });

        go("THINKING");

        let sentenceBuffer = "";
        const enqueueSentence = (s: string) => {
          const clean = s.trim();
          if (!clean || clean.length < 2) return;
          const promise = speakText(clean);
          audioQueueRef.current.push({ promise });
          playNextInQueue();
        };

        await sendMessageStream(txt, activeConvRef.current || undefined, (event) => {
          if (event.type === "init") {
            if (event.conversation_id && !activeConvRef.current) {
              setActiveConvId(event.conversation_id);
              activeConvRef.current = event.conversation_id;
              getConversations().then(setConversations).catch(() => {});
            }
          } else if (event.type === "state") {
            if (event.agent_state === "planning") go("PLANNING");
            else if (event.agent_state === "executing") go("PROCESSING");
            else if (event.agent_state === "verifying") go("VERIFYING");
            else if (event.agent_state === "responding") go("RESPONDING");
            else if (event.agent_state === "thinking") go("THINKING");
          } else if (event.type === "token" && event.token) {
            const token = event.token;
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId ? { ...m, content: m.content + token } : m
              )
            );

            sentenceBuffer += token;
            const match = sentenceBuffer.match(/^(.*?[.!?])(\s+[\s\S]*)$/);
            if (match) {
              const sentence = match[1];
              sentenceBuffer = match[2];
              enqueueSentence(sentence);
            }
          } else if (event.type === "done") {
            if (event.conversation_id && !activeConvRef.current) {
              setActiveConvId(event.conversation_id);
              activeConvRef.current = event.conversation_id;
              getConversations().then(setConversations).catch(() => {});
            }
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId
                  ? {
                      ...m,
                      content: event.response || m.content,
                      latency_ms: event.latency_ms ?? m.latency_ms,
                      tool_name: event.tool_name ?? m.tool_name,
                      intent: event.intent ?? m.intent,
                    }
                  : m
              )
            );
          }
        });

        if (sentenceBuffer.trim()) {
          enqueueSentence(sentenceBuffer);
          sentenceBuffer = "";
        }

        streamDoneRef.current = true;
        if (audioQueueRef.current.length === 0 && !isPlayingRef.current) {
          if (wakeModeRef.current) {
            go("LISTENING_WAKE");
            runWakeWordLoop();
          } else {
            go("DORMANT");
          }
        }
      } catch (err: any) {
        setErrorText(err.message || "Error");
        go("ERROR");
        setTimeout(() => {
          go(wakeModeRef.current ? "LISTENING_WAKE" : "DORMANT");
          if (wakeModeRef.current) runWakeWordLoop();
        }, 3000);
      }
      // eslint-disable-next-line react-hooks/exhaustive-deps
    },
    [addMessage, go, playAudio, playNextInQueue, stopAmplitude, stopAudio]
  );

  // ── Recording Command ──────────────────────────────────────────────────────
  const startCommandRecording = useCallback(async () => {
    go("LISTENING_CMD");
    setTranscript("Listening...");

    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      setMicDenied(false);
    } catch {
      setMicDenied(true);
      go("ERROR");
      setErrorText("Microphone permission denied");
      setTimeout(
        () => go(wakeModeRef.current ? "LISTENING_WAKE" : "DORMANT"),
        2500
      );
      return;
    }

    startAmplitude(stream);
    cmdChunksRef.current = [];
    const recorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
    cmdRecorderRef.current = recorder;
    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) cmdChunksRef.current.push(e.data);
    };

    recorder.onstop = () => {
      stream.getTracks().forEach((t) => t.stop());
      clearTimeout(silenceTimerRef.current!);
      clearTimeout(cmdMaxTimerRef.current!);
      stopAmplitude();

      if (stateRef.current !== "LISTENING_CMD") return;
      const blob = new Blob(cmdChunksRef.current, { type: "audio/webm" });
      processCommand(blob);
    };

    recorder.start();

    const silenceCheck = () => {
      if (stateRef.current !== "LISTENING_CMD") return;
      if (analyserRef.current) {
        const buf = new Uint8Array(analyserRef.current.frequencyBinCount);
        analyserRef.current.getByteFrequencyData(buf);
        const rms =
          Math.sqrt(buf.reduce((s, v) => s + v * v, 0) / buf.length) / 128;
        if (rms < 0.04) {
          if (!silenceTimerRef.current) {
            silenceTimerRef.current = setTimeout(() => {
              silenceTimerRef.current = null;
              if (recorder.state === "recording") recorder.stop();
            }, 1500);
          }
        } else {
          clearTimeout(silenceTimerRef.current!);
          silenceTimerRef.current = null;
        }
      }
      setTimeout(silenceCheck, 200);
    };
    setTimeout(silenceCheck, 500);

    cmdMaxTimerRef.current = setTimeout(() => {
      if (recorder.state === "recording") recorder.stop();
    }, 8000);
  }, [go, processCommand, startAmplitude, stopAmplitude]);

  // ── Wake Word Loop ─────────────────────────────────────────────────────────
  const runWakeWordLoop = useCallback(async () => {
    if (stateRef.current !== "LISTENING_WAKE") return;
    if (!wakeStreamRef.current || !wakeStreamRef.current.active) return;

    const chunks: Blob[] = [];
    let recorder: MediaRecorder;
    try {
      recorder = new MediaRecorder(wakeStreamRef.current, {
        mimeType: "audio/webm",
      });
    } catch {
      return;
    }
    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunks.push(e.data);
    };

    recorder.onstop = async () => {
      if (stateRef.current !== "LISTENING_WAKE") return;
      const blob = new Blob(chunks, { type: "audio/webm" });

      if (blob.size > 3000 && !wakeProcessing.current) {
        wakeProcessing.current = true;
        const result = await wakeCheck(blob);
        wakeProcessing.current = false;

        if (result.detected && stateRef.current === "LISTENING_WAKE") {
          go("WAKE_DETECTED");
          setTranscript("Yes?");
          setTimeout(() => {
            if (stateRef.current === "WAKE_DETECTED") startCommandRecording();
          }, 600);
          return;
        }
      }

      if (stateRef.current === "LISTENING_WAKE") runWakeWordLoop();
    };

    recorder.start();
    setTimeout(() => {
      if (recorder.state === "recording") recorder.stop();
    }, 1500);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [go, startCommandRecording]);

  const enableWakeMode = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      setMicDenied(false);
      wakeStreamRef.current = stream;
      setWakeMode(true);
      wakeModeRef.current = true;
      go("LISTENING_WAKE");
      runWakeWordLoop();
    } catch {
      setMicDenied(true);
      setErrorText("Microphone permission denied");
      go("ERROR");
      setTimeout(() => go("DORMANT"), 2500);
    }
  }, [go, runWakeWordLoop]);

  const disableWakeMode = useCallback(() => {
    wakeStreamRef.current?.getTracks().forEach((t) => t.stop());
    wakeStreamRef.current = null;
    wakeProcessing.current = false;
    setWakeMode(false);
    wakeModeRef.current = false;
    stopAudio();
    stopAmplitude();
    if (cmdRecorderRef.current?.state === "recording") {
      cmdRecorderRef.current.stop();
    }
    go("DORMANT");
    setTranscript("");
  }, [go, stopAmplitude, stopAudio]);

  const handleOrbClick = useCallback(() => {
    const s = stateRef.current;
    if (s === "DORMANT") {
      startCommandRecording();
    } else if (s === "LISTENING_CMD") {
      if (cmdRecorderRef.current?.state === "recording") {
        cmdRecorderRef.current.stop();
      }
    } else if (s === "SPEAKING") {
      stopAudio();
      startCommandRecording();
    } else if (s === "ERROR") {
      go(wakeModeRef.current ? "LISTENING_WAKE" : "DORMANT");
      if (wakeModeRef.current) runWakeWordLoop();
    }
  }, [go, runWakeWordLoop, startCommandRecording, stopAudio]);

  // ── Text Chat Send ─────────────────────────────────────────────────────────
  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (
      !text ||
      ["PROCESSING", "THINKING", "PLANNING", "VERIFYING", "RESPONDING"].includes(
        stateRef.current
      )
    )
      return;
    setInput("");
    if (activeTab === "home") {
      setActiveTab("chat");
    }

    const userMsgId = Date.now().toString();
    addMessage({
      id: userMsgId,
      role: "user",
      content: text,
      is_voice: false,
      created_at: new Date().toISOString(),
    });
    go("THINKING");

    const assistantMsgId = (Date.now() + 1).toString();
    addMessage({
      id: assistantMsgId,
      role: "assistant",
      content: "",
      is_voice: false,
      created_at: new Date().toISOString(),
    });

    try {
      await sendMessageStream(text, activeConvRef.current || undefined, (event) => {
        if (event.type === "init") {
          if (event.conversation_id && !activeConvRef.current) {
            setActiveConvId(event.conversation_id);
            activeConvRef.current = event.conversation_id;
            getConversations().then(setConversations).catch(() => {});
          }
        } else if (event.type === "state") {
          if (event.agent_state === "planning") go("PLANNING");
          else if (event.agent_state === "executing") go("PROCESSING");
          else if (event.agent_state === "verifying") go("VERIFYING");
          else if (event.agent_state === "responding") go("RESPONDING");
          else if (event.agent_state === "thinking") go("THINKING");
        } else if (event.type === "token" && event.token) {
          const token = event.token;
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMsgId ? { ...m, content: m.content + token } : m
            )
          );
        } else if (event.type === "done") {
          if (event.conversation_id && !activeConvRef.current) {
            setActiveConvId(event.conversation_id);
            activeConvRef.current = event.conversation_id;
            getConversations().then(setConversations).catch(() => {});
          }
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMsgId
                ? {
                    ...m,
                    content: event.response || m.content,
                    latency_ms: event.latency_ms ?? m.latency_ms,
                    tool_name: event.tool_name ?? m.tool_name,
                    intent: event.intent ?? m.intent,
                  }
                : m
            )
          );
        }
      });
    } catch (err: any) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantMsgId ? { ...m, content: `⚠️ ${err.message}` } : m
        )
      );
    } finally {
      go(wakeModeRef.current ? "LISTENING_WAKE" : "DORMANT");
    }
  }, [activeTab, addMessage, go, input]);

  const loadConv = useCallback(async (id: string) => {
    try {
      const d = await getConversation(id);
      setActiveConvId(id);
      setMessages(d.messages);
      setActiveTab("chat");
    } catch {}
  }, []);

  useEffect(() => () => {
    disableWakeMode();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Notes Handlers ─────────────────────────────────────────────────────────
  const handleSaveNote = async () => {
    if (!noteTitle.trim()) return;
    if (editingNoteId) {
      await updateNote(editingNoteId, { title: noteTitle.trim(), content: noteContent.trim() }).catch(() => {});
      setEditingNoteId(null);
    } else {
      await createNote(noteTitle.trim(), noteContent.trim()).catch(() => {});
    }
    setNoteTitle("");
    setNoteContent("");
    getNotes().then(setNotes).catch(() => {});
  };

  const handleDeleteNote = async (id: string) => {
    await deleteNote(id).catch(() => {});
    setNotes((prev) => prev.filter((n) => n.id !== id));
  };

  // ── Reminders Handlers ─────────────────────────────────────────────────────
  const handleCreateReminder = async () => {
    if (!remTitle.trim()) return;
    await createReminder(remTitle.trim(), remDate || undefined).catch(() => {});
    setRemTitle("");
    setRemDate("");
    getReminders().then(setReminders).catch(() => {});
  };

  const handleToggleReminder = async (rem: Reminder) => {
    const nextStatus = rem.status === "completed" ? "pending" : "completed";
    await updateReminder(rem.id, { status: nextStatus }).catch(() => {});
    getReminders().then(setReminders).catch(() => {});
  };

  const handleDeleteReminder = async (id: string) => {
    await deleteReminder(id).catch(() => {});
    setReminders((prev) => prev.filter((r) => r.id !== id));
  };

  const isBusy = ["PROCESSING", "THINKING", "SPEAKING", "PLANNING", "VERIFYING", "RESPONDING"].includes(jarvisState);
  const isRecording = jarvisState === "LISTENING_CMD";

  // Filtered notes for Notes tab
  const filteredNotes = useMemo(() => {
    if (!noteSearch.trim()) return notes;
    const q = noteSearch.toLowerCase();
    return notes.filter(
      (n) => n.title.toLowerCase().includes(q) || (n.content && n.content.toLowerCase().includes(q))
    );
  }, [notes, noteSearch]);

  const pendingReminders = reminders.filter((r) => r.status === "pending");
  const completedReminders = reminders.filter((r) => r.status === "completed");

  return (
    <div className="flex h-screen bg-[#f8fafc] text-slate-800 overflow-hidden select-none">
      {/* ── 5. LEFT SIDEBAR ─────────────────────────────────────────────────── */}
      <Sidebar
        activeTab={activeTab}
        onTabChange={setActiveTab}
        conversations={conversations}
        activeId={activeConvId}
        onSelect={loadConv}
        onNew={() => {
          setActiveConvId(null);
          setMessages([]);
          setTranscript("");
          setActiveTab("chat");
        }}
        onDelete={async (id) => {
          try {
            await deleteConversation(id);
            setConversations((p) => p.filter((c) => c.id !== id));
            if (activeConvId === id) {
              setActiveConvId(null);
              setMessages([]);
            }
          } catch {}
        }}
        mobileOpen={mobileSidebarOpen}
        onMobileClose={() => setMobileSidebarOpen(false)}
      />

      {/* ── MAIN CONTENT AREA ───────────────────────────────────────────────── */}
      <main className="flex-1 flex flex-col h-screen overflow-hidden relative">
        {/* ── 8. TOP HEADER ─────────────────────────────────────────────────── */}
        <header className="nova-header px-4 sm:px-8 py-3.5 flex items-center justify-between shrink-0 z-20">
          <div className="flex items-center gap-3">
            {/* Mobile Hamburger */}
            <button
              onClick={() => setMobileSidebarOpen(true)}
              className="md:hidden p-1.5 text-slate-500 hover:text-slate-800 cursor-pointer rounded-lg hover:bg-slate-100"
            >
              <Menu size={20} />
            </button>

            <div>
              <div className="flex items-center gap-2">
                <span className="text-lg font-black tracking-[0.2em] text-slate-900 uppercase">
                  NOVA
                </span>
                <span className="hidden sm:inline text-[10px] text-sky-600 bg-sky-50 font-semibold px-2 py-0.5 rounded-full border border-sky-100">
                  {activeTab.toUpperCase()}
                </span>
              </div>
              <span className="block text-[9px] font-semibold text-slate-400 tracking-widest uppercase">
                VOICE AI ASSISTANT
              </span>
            </div>
          </div>

          {/* Right Status Controls */}
          <div className="flex items-center gap-2 sm:gap-3">
            {/* LLM Status Chip */}
            <div className="nova-status-chip">
              <span
                className={`w-2 h-2 rounded-full ${
                  ollamaOk
                    ? "bg-emerald-500 shadow-[0_0_6px_#10b981]"
                    : "bg-red-400 shadow-[0_0_6px_#f87171]"
                }`}
              />
              <span className="hidden sm:inline font-semibold">
                LLM {ollamaOk ? "Online" : "Offline"}
              </span>
            </div>

            {/* Mic Status Chip */}
            <div className="nova-status-chip">
              <span className="w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_6px_#10b981]" />
              <span className="hidden sm:inline font-semibold">Mic Ready</span>
            </div>

            {/* Wake Word Toggle */}
            <button
              type="button"
              onClick={() => (wakeMode ? disableWakeMode() : enableWakeMode())}
              className={`nova-status-chip font-semibold cursor-pointer transition-all ${
                wakeMode
                  ? "bg-sky-50/90 border-sky-300 text-sky-700 shadow-[0_0_12px_rgba(2,132,199,0.2)]"
                  : "hover:bg-slate-100/70"
              }`}
            >
              <span
                className={`w-2 h-2 rounded-full ${
                  wakeMode
                    ? "bg-sky-500 shadow-[0_0_6px_#0ea5e9]"
                    : "border border-slate-400"
                }`}
              />
              <span className="hidden sm:inline">
                Wake Word {wakeMode ? "ON" : "OFF"}
              </span>
            </button>

            {/* Profile / Sign In */}
            <ProfileMenu />
          </div>
        </header>

        {/* ── 9. VIEW 1: HOME PAGE ─────────────────────────────────────────── */}
        {activeTab === "home" && (
          <div className="flex-1 flex flex-col items-center justify-between px-4 sm:px-8 py-6 overflow-y-auto nova-home-bg relative">
            {/* Branding Hero */}
            <div className="text-center pt-2 select-none z-10">
              <h1 className="text-4xl sm:text-5xl font-light tracking-[0.45em] text-slate-900 uppercase pl-3">
                N O V A
              </h1>
              <p className="text-[11px] font-medium tracking-[0.4em] text-slate-400 uppercase mt-2">
                A SMARTER YOU TOMORROW
              </p>
            </div>

            {/* 10, 11, 12, 13. NOVA Core & Voice Area */}
            <div className="flex flex-col items-center justify-center my-auto py-2 z-10 w-full max-w-md">
              {/* 3D Nova Core */}
              <Nova3DSphere
                state={mapToVisualState(jarvisState)}
                amplitude={amplitude}
                onClick={handleOrbClick}
              />

              {/* Dynamic Waveform */}
              <Waveform active={isRecording || jarvisState === "SPEAKING"} amplitude={amplitude} />

              {/* Status Headline & Hint */}
              <h2 className="text-lg font-bold text-slate-900 mt-1">
                {LABEL[jarvisState]}
              </h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Say <span className="text-sky-600 font-bold">&quot;Hey NOVA&quot;</span> to activate or press the mic
              </p>

              {/* Live Transcript Pill */}
              {transcript && (
                <div className="mt-3 px-4 py-1.5 rounded-full bg-white/95 backdrop-blur-md border border-sky-200 shadow-sm text-xs font-semibold text-sky-700 animate-fadeIn">
                  &quot;{transcript}&quot;
                </div>
              )}

              {/* Error Badge */}
              {jarvisState === "ERROR" && errorText && (
                <div className="mt-3 px-4 py-1.5 rounded-full bg-red-50 border border-red-200 text-xs font-semibold text-red-600 animate-fadeIn">
                  ⚠ {errorText}
                </div>
              )}

              {/* Mic Denied Badge */}
              {micDenied && (
                <div className="mt-3 px-4 py-1.5 rounded-full bg-red-50 border border-red-200 text-xs font-semibold text-red-600 animate-fadeIn">
                  Microphone access blocked — allow mic permissions in browser
                </div>
              )}
            </div>

            {/* 14. Exactly 4 Feature Cards */}
            <div className="w-full max-w-4xl grid grid-cols-2 md:grid-cols-4 gap-3 sm:gap-4 my-3 z-10">
              {/* Card 1: Speak Naturally */}
              <div
                onClick={handleOrbClick}
                className="nova-card p-4 flex flex-col items-center text-center cursor-pointer group"
              >
                <div className="w-10 h-10 rounded-full bg-sky-50 text-sky-600 flex items-center justify-center mb-2.5 group-hover:scale-110 transition-transform">
                  <Mic size={19} />
                </div>
                <div className="text-xs font-bold text-slate-900">
                  Speak Naturally
                </div>
                <div className="text-[11px] text-slate-400 mt-0.5">
                  Just say what you need
                </div>
              </div>

              {/* Card 2: Fast & Smart */}
              <div
                onClick={() => {
                  setActiveTab("chat");
                  setInput("What can you do?");
                }}
                className="nova-card p-4 flex flex-col items-center text-center cursor-pointer group"
              >
                <div className="w-10 h-10 rounded-full bg-sky-50 text-sky-600 flex items-center justify-center mb-2.5 group-hover:scale-110 transition-transform">
                  <Zap size={19} />
                </div>
                <div className="text-xs font-bold text-slate-900">
                  Fast &amp; Smart
                </div>
                <div className="text-[11px] text-slate-400 mt-0.5">
                  Get instant answers
                </div>
              </div>

              {/* Card 3: AI Powered */}
              <div
                onClick={() => {
                  setActiveTab("chat");
                  setInput("Explain how you work.");
                }}
                className="nova-card p-4 flex flex-col items-center text-center cursor-pointer group"
              >
                <div className="w-10 h-10 rounded-full bg-sky-50 text-sky-600 flex items-center justify-center mb-2.5 group-hover:scale-110 transition-transform">
                  <Brain size={19} />
                </div>
                <div className="text-xs font-bold text-slate-900">
                  AI Powered
                </div>
                <div className="text-[11px] text-slate-400 mt-0.5">
                  Think · Assist · Act
                </div>
              </div>

              {/* Card 4: Your Privacy */}
              <div
                onClick={() => {
                  setActiveTab("chat");
                  setInput("How does local on-device privacy work?");
                }}
                className="nova-card p-4 flex flex-col items-center text-center cursor-pointer group"
              >
                <div className="w-10 h-10 rounded-full bg-sky-50 text-sky-600 flex items-center justify-center mb-2.5 group-hover:scale-110 transition-transform">
                  <Shield size={19} />
                </div>
                <div className="text-xs font-bold text-slate-900">
                  Your Privacy
                </div>
                <div className="text-[11px] text-slate-400 mt-0.5">
                  Stays with you
                </div>
              </div>
            </div>

            {/* 15. Bottom Input Dock */}
            <div className="w-full flex justify-center pb-2 z-10">
              <InputDock
                input={input}
                setInput={setInput}
                onSend={handleSend}
                onOrbClick={handleOrbClick}
                isRecording={isRecording}
                isBusy={isBusy}
              />
            </div>
          </div>
        )}

        {/* ── 16. VIEW 2: CHAT PAGE ─────────────────────────────────────────── */}
        {activeTab === "chat" && (
          <div className="flex-1 flex flex-col h-full overflow-hidden bg-white">
            {/* Chat Title Header */}
            <div className="px-6 sm:px-12 pt-5 pb-3 border-b border-slate-100 shrink-0">
              <h1 className="text-xl font-extrabold text-slate-900">Chat</h1>
              <p className="text-xs text-slate-500 mt-0.5">
                Your conversations with NOVA
              </p>
            </div>

            {/* Conversation Feed */}
            <div className="flex-1 overflow-y-auto px-4 sm:px-12 py-6 select-text">
              {messages.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full text-center px-4">
                  <div className="w-14 h-14 rounded-2xl bg-sky-50 text-sky-600 flex items-center justify-center mb-3 shadow-xs">
                    <MessageCircle size={26} />
                  </div>
                  <h3 className="text-base font-bold text-slate-800">
                    Start a conversation
                  </h3>
                  <p className="text-xs text-slate-400 mt-1 max-w-sm">
                    Ask questions, control apps, or speak naturally. Say &quot;Hey NOVA&quot; or type your message below.
                  </p>

                  {/* Suggestion Chips */}
                  <div className="flex flex-wrap gap-2 justify-center mt-6 max-w-md">
                    {[
                      "Open GitHub",
                      "What is 25 × 18?",
                      "What time is it?",
                      "Search Python tutorial",
                      "Tell me a fun fact",
                    ].map((prompt) => (
                      <button
                        key={prompt}
                        onClick={() => setInput(prompt)}
                        className="px-3.5 py-1.5 rounded-full bg-slate-50 hover:bg-sky-50 hover:text-sky-600 hover:border-sky-200 border border-slate-200 text-xs font-medium text-slate-600 transition-all cursor-pointer shadow-xs"
                      >
                        {prompt}
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                messages.map((m) => <ChatMessageBubble key={m.id} msg={m} />)
              )}

              {/* Streaming / Typing indicator */}
              {isBusy && (
                <div className="flex items-center gap-1.5 px-4 py-3 bg-slate-50 rounded-2xl w-20 mb-4 text-sky-600 border border-slate-100 animate-fadeIn">
                  <div className="w-2 h-2 rounded-full bg-sky-500 animate-bounce" />
                  <div
                    className="w-2 h-2 rounded-full bg-sky-500 animate-bounce"
                    style={{ animationDelay: "0.15s" }}
                  />
                  <div
                    className="w-2 h-2 rounded-full bg-sky-500 animate-bounce"
                    style={{ animationDelay: "0.3s" }}
                  />
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* Bottom Composer Dock */}
            <div className="p-4 sm:px-12 sm:pb-6 bg-white shrink-0 border-t border-slate-100 flex justify-center">
              <InputDock
                input={input}
                setInput={setInput}
                onSend={handleSend}
                onOrbClick={handleOrbClick}
                isRecording={isRecording}
                isBusy={isBusy}
              />
            </div>
          </div>
        )}

        {/* ── 17. VIEW 3: NOTES PAGE ────────────────────────────────────────── */}
        {activeTab === "notes" && (
          <div className="flex-1 flex flex-col h-full overflow-y-auto px-6 sm:px-12 py-6 bg-[#f8fafc]">
            <div className="max-w-4xl w-full mx-auto space-y-6">
              <div className="flex items-center justify-between pb-2 border-b border-slate-200/80">
                <div>
                  <h1 className="text-2xl font-extrabold text-slate-900">Notes</h1>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Capture and organize your thoughts with NOVA
                  </p>
                </div>
                <div className="w-64">
                  <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-white border border-slate-200 text-xs">
                    <Search size={14} className="text-slate-400" />
                    <input
                      type="text"
                      placeholder="Search notes..."
                      value={noteSearch}
                      onChange={(e) => setNoteSearch(e.target.value)}
                      className="w-full bg-transparent outline-none text-slate-700"
                    />
                  </div>
                </div>
              </div>

              {/* Create / Edit Note Card */}
              <div className="nova-card p-5 bg-white">
                <h3 className="text-xs font-bold uppercase tracking-wider text-sky-700 mb-3">
                  {editingNoteId ? "Edit Note" : "Create New Note"}
                </h3>
                <input
                  type="text"
                  placeholder="Note title..."
                  value={noteTitle}
                  onChange={(e) => setNoteTitle(e.target.value)}
                  className="w-full text-sm font-semibold text-slate-800 bg-transparent border-b border-slate-200 pb-2 mb-3 outline-none focus:border-sky-500 transition-colors"
                />
                <textarea
                  placeholder="Note details, thoughts, or ideas..."
                  value={noteContent}
                  onChange={(e) => setNoteContent(e.target.value)}
                  rows={3}
                  className="w-full text-xs text-slate-600 bg-transparent outline-none resize-none placeholder-slate-400"
                />
                <div className="flex items-center justify-end gap-2 mt-3 pt-2 border-t border-slate-100">
                  {editingNoteId && (
                    <button
                      onClick={() => {
                        setEditingNoteId(null);
                        setNoteTitle("");
                        setNoteContent("");
                      }}
                      className="px-3 py-1.5 text-xs text-slate-500 hover:text-slate-700 cursor-pointer"
                    >
                      Cancel
                    </button>
                  )}
                  <button
                    onClick={handleSaveNote}
                    disabled={!noteTitle.trim()}
                    className="px-4 py-1.5 rounded-lg bg-sky-500 hover:bg-sky-600 disabled:bg-slate-200 text-white text-xs font-semibold shadow-sm transition-all cursor-pointer"
                  >
                    {editingNoteId ? "Update Note" : "Save Note"}
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
                    <div>
                      <div className="flex items-start justify-between gap-2">
                        <h4 className="text-sm font-bold text-slate-800 line-clamp-1">
                          {note.title}
                        </h4>
                        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                          <button
                            onClick={() => {
                              setEditingNoteId(note.id);
                              setNoteTitle(note.title);
                              setNoteContent(note.content || "");
                            }}
                            className="p-1 text-slate-400 hover:text-sky-600 cursor-pointer rounded"
                          >
                            <Edit3 size={13} />
                          </button>
                          <button
                            onClick={() => handleDeleteNote(note.id)}
                            className="p-1 text-slate-400 hover:text-red-500 cursor-pointer rounded"
                          >
                            <Trash2 size={13} />
                          </button>
                        </div>
                      </div>
                      <p className="text-xs text-slate-600 mt-2 whitespace-pre-wrap line-clamp-4 leading-relaxed">
                        {note.content || "No additional content"}
                      </p>
                    </div>

                    <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-400">
                      <span>{new Date(note.created_at).toLocaleDateString()}</span>
                      <StickyNote size={12} className="text-sky-400" />
                    </div>
                  </div>
                ))}
              </div>

              {filteredNotes.length === 0 && (
                <div className="text-center py-12 text-slate-400 text-xs">
                  {noteSearch ? "No notes found matching your search" : "No notes saved yet. Create your first note above!"}
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── 18. VIEW 4: STATUS PAGE ───────────────────────────────────────── */}
        {activeTab === "status" && (
          <div className="flex-1 flex flex-col h-full overflow-y-auto px-6 sm:px-12 py-6 bg-[#f8fafc]">
            <div className="max-w-4xl w-full mx-auto space-y-6">
              <div className="flex items-center justify-between pb-2 border-b border-slate-200/80">
                <div>
                  <h1 className="text-2xl font-extrabold text-slate-900">System Status</h1>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Real-time operational health and runtime services
                  </p>
                </div>
                <button
                  onClick={() => {
                    getStatus().then(setSystemStatus).catch(() => {});
                    getAnalytics().then(setAnalytics).catch(() => {});
                  }}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white border border-slate-200 text-xs font-semibold text-slate-600 hover:text-sky-600 shadow-xs cursor-pointer"
                >
                  <RefreshCw size={13} />
                  <span>Refresh</span>
                </button>
              </div>

              {/* Service Cards */}
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
                {/* Ollama LLM */}
                <div className="nova-card p-4 bg-white">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-bold text-slate-700">Ollama LLM</span>
                    <span
                      className={`w-2.5 h-2.5 rounded-full ${
                        systemStatus?.ollama_available ? "bg-emerald-500 shadow-[0_0_6px_#10b981]" : "bg-red-400"
                      }`}
                    />
                  </div>
                  <div className="text-base font-extrabold text-slate-900">
                    {systemStatus?.ollama_available ? "Online" : "Offline"}
                  </div>
                  <div className="text-[11px] text-slate-400 font-mono mt-1 truncate">
                    Model: {systemStatus?.ollama_model || "llama3.2:1b"}
                  </div>
                </div>

                {/* Speech to Text */}
                <div className="nova-card p-4 bg-white">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-bold text-slate-700">Speech-to-Text (STT)</span>
                    <span
                      className={`w-2.5 h-2.5 rounded-full ${
                        systemStatus?.stt_available ? "bg-emerald-500 shadow-[0_0_6px_#10b981]" : "bg-red-400"
                      }`}
                    />
                  </div>
                  <div className="text-base font-extrabold text-slate-900">
                    {systemStatus?.stt_available ? "Ready" : "Unavailable"}
                  </div>
                  <div className="text-[11px] text-slate-400 mt-1">
                    Faster-Whisper / Local Model
                  </div>
                </div>

                {/* Text to Speech */}
                <div className="nova-card p-4 bg-white">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-bold text-slate-700">Text-to-Speech (TTS)</span>
                    <span
                      className={`w-2.5 h-2.5 rounded-full ${
                        systemStatus?.tts_available ? "bg-emerald-500 shadow-[0_0_6px_#10b981]" : "bg-red-400"
                      }`}
                    />
                  </div>
                  <div className="text-base font-extrabold text-slate-900">
                    {systemStatus?.tts_available ? "Ready" : "Unavailable"}
                  </div>
                  <div className="text-[11px] text-slate-400 mt-1">
                    Native macOS / Audio Engine
                  </div>
                </div>

                {/* Database */}
                <div className="nova-card p-4 bg-white">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-bold text-slate-700">SQLite Database</span>
                    <span
                      className={`w-2.5 h-2.5 rounded-full ${
                        systemStatus?.database_ok ? "bg-emerald-500 shadow-[0_0_6px_#10b981]" : "bg-red-400"
                      }`}
                    />
                  </div>
                  <div className="text-base font-extrabold text-slate-900">
                    {systemStatus?.database_ok ? "Operational" : "Error"}
                  </div>
                  <div className="text-[11px] text-slate-400 mt-1">
                    Local persistent storage
                  </div>
                </div>

                {/* Vector Database */}
                <div className="nova-card p-4 bg-white">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-bold text-slate-700">Vector Knowledge DB</span>
                    <span
                      className={`w-2.5 h-2.5 rounded-full ${
                        systemStatus?.vector_db_ok ? "bg-emerald-500 shadow-[0_0_6px_#10b981]" : "bg-red-400"
                      }`}
                    />
                  </div>
                  <div className="text-base font-extrabold text-slate-900">
                    {systemStatus?.vector_db_ok ? "Operational" : "Unavailable"}
                  </div>
                  <div className="text-[11px] text-slate-400 mt-1">
                    Chroma Vector Engine
                  </div>
                </div>

                {/* Wake Word Detection */}
                <div className="nova-card p-4 bg-white">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-bold text-slate-700">Wake Word Engine</span>
                    <span
                      className={`w-2.5 h-2.5 rounded-full ${
                        wakeMode ? "bg-sky-500 shadow-[0_0_6px_#0ea5e9]" : "bg-slate-300"
                      }`}
                    />
                  </div>
                  <div className="text-base font-extrabold text-slate-900">
                    {wakeMode ? "Active" : "Standby"}
                  </div>
                  <div className="text-[11px] text-slate-400 mt-1">
                    Phrase: &quot;Hey NOVA&quot;
                  </div>
                </div>
              </div>

              {/* Analytics metrics if available */}
              {analytics && (
                <div className="nova-card p-5 bg-white space-y-4">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">
                    Performance &amp; Activity
                  </h3>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-center">
                    <div className="p-3 bg-slate-50 rounded-xl">
                      <div className="text-xl font-black text-sky-600">
                        {analytics.total_conversations}
                      </div>
                      <div className="text-[11px] text-slate-500 font-medium">Conversations</div>
                    </div>
                    <div className="p-3 bg-slate-50 rounded-xl">
                      <div className="text-xl font-black text-sky-600">
                        {analytics.total_messages}
                      </div>
                      <div className="text-[11px] text-slate-500 font-medium">Messages</div>
                    </div>
                    <div className="p-3 bg-slate-50 rounded-xl">
                      <div className="text-xl font-black text-sky-600">
                        {analytics.voice_requests}
                      </div>
                      <div className="text-[11px] text-slate-500 font-medium">Voice Queries</div>
                    </div>
                    <div className="p-3 bg-slate-50 rounded-xl">
                      <div className="text-xl font-black text-sky-600">
                        {Math.round(analytics.avg_response_latency_ms)}ms
                      </div>
                      <div className="text-[11px] text-slate-500 font-medium">Avg Latency</div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── 19. VIEW 5: REMINDERS PAGE ────────────────────────────────────── */}
        {activeTab === "reminders" && (
          <div className="flex-1 flex flex-col h-full overflow-y-auto px-6 sm:px-12 py-6 bg-[#f8fafc]">
            <div className="max-w-4xl w-full mx-auto space-y-6">
              <div className="pb-2 border-b border-slate-200/80">
                <h1 className="text-2xl font-extrabold text-slate-900">Reminders</h1>
                <p className="text-xs text-slate-500 mt-0.5">
                  Scheduled alerts and task checklist
                </p>
              </div>

              {/* Add Reminder Card */}
              <div className="nova-card p-5 bg-white">
                <h3 className="text-xs font-bold uppercase tracking-wider text-sky-700 mb-3">
                  Add Reminder
                </h3>
                <div className="flex flex-col sm:flex-row gap-3">
                  <input
                    type="text"
                    placeholder="Reminder title or task..."
                    value={remTitle}
                    onChange={(e) => setRemTitle(e.target.value)}
                    className="flex-1 px-3 py-2 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-800 outline-none focus:border-sky-500 transition-colors"
                  />
                  <input
                    type="datetime-local"
                    value={remDate}
                    onChange={(e) => setRemDate(e.target.value)}
                    className="px-3 py-2 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-600 outline-none focus:border-sky-500 transition-colors"
                  />
                  <button
                    onClick={handleCreateReminder}
                    disabled={!remTitle.trim()}
                    className="px-5 py-2 rounded-xl bg-sky-500 hover:bg-sky-600 disabled:bg-slate-200 text-white text-xs font-semibold shadow-sm transition-all cursor-pointer shrink-0"
                  >
                    Add
                  </button>
                </div>
              </div>

              {/* Pending Reminders */}
              <div>
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-3">
                  Pending ({pendingReminders.length})
                </h3>
                <div className="space-y-2">
                  {pendingReminders.map((rem) => (
                    <div
                      key={rem.id}
                      className="nova-card p-3.5 bg-white flex items-center justify-between group hover:border-sky-300 transition-all"
                    >
                      <div className="flex items-center gap-3">
                        <button
                          onClick={() => handleToggleReminder(rem)}
                          className="w-5 h-5 rounded-full border-2 border-slate-300 hover:border-sky-500 flex items-center justify-center transition-colors cursor-pointer"
                        />
                        <div>
                          <div className="text-xs font-bold text-slate-800">{rem.title}</div>
                          {rem.scheduled_at && (
                            <div className="text-[10px] text-slate-400 mt-0.5 flex items-center gap-1">
                              <Clock size={11} />
                              <span>{new Date(rem.scheduled_at).toLocaleString()}</span>
                            </div>
                          )}
                        </div>
                      </div>

                      <button
                        onClick={() => handleDeleteReminder(rem.id)}
                        className="opacity-0 group-hover:opacity-100 p-1 text-slate-400 hover:text-red-500 cursor-pointer rounded"
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>
                  ))}

                  {pendingReminders.length === 0 && (
                    <div className="text-center py-6 text-slate-400 text-xs bg-white rounded-xl border border-slate-100">
                      No pending reminders
                    </div>
                  )}
                </div>
              </div>

              {/* Completed Reminders */}
              {completedReminders.length > 0 && (
                <div>
                  <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3">
                    Completed ({completedReminders.length})
                  </h3>
                  <div className="space-y-2 opacity-60">
                    {completedReminders.map((rem) => (
                      <div
                        key={rem.id}
                        className="nova-card p-3 bg-white flex items-center justify-between group"
                      >
                        <div className="flex items-center gap-3">
                          <button
                            onClick={() => handleToggleReminder(rem)}
                            className="w-5 h-5 rounded-full bg-emerald-500 text-white flex items-center justify-center text-[10px] cursor-pointer"
                          >
                            <Check size={12} />
                          </button>
                          <span className="text-xs text-slate-500 line-through">{rem.title}</span>
                        </div>
                        <button
                          onClick={() => handleDeleteReminder(rem.id)}
                          className="opacity-0 group-hover:opacity-100 p-1 text-slate-400 hover:text-red-500 cursor-pointer rounded"
                        >
                          <Trash2 size={13} />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── 20. VIEW 6: SETTINGS PAGE ─────────────────────────────────────── */}
        {activeTab === "settings" && (
          <div className="flex-1 flex flex-col h-full overflow-y-auto px-6 sm:px-12 py-6 bg-[#f8fafc]">
            <div className="max-w-4xl w-full mx-auto space-y-6">
              <div className="pb-2 border-b border-slate-200/80">
                <h1 className="text-2xl font-extrabold text-slate-900">Settings</h1>
                <p className="text-xs text-slate-500 mt-0.5">
                  Application preferences and runtime environment
                </p>
              </div>

              {/* Voice & Wake Word */}
              <div className="nova-card p-6 bg-white space-y-4">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-2">
                  <Volume2 size={15} className="text-sky-600" />
                  <span>Voice &amp; Audio</span>
                </h3>

                <div className="flex items-center justify-between py-2 border-b border-slate-100">
                  <div>
                    <div className="text-xs font-semibold text-slate-800">Wake Word Listening</div>
                    <div className="text-[11px] text-slate-400">Continually listen for &quot;Hey NOVA&quot;</div>
                  </div>
                  <button
                    onClick={() => (wakeMode ? disableWakeMode() : enableWakeMode())}
                    className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-all cursor-pointer ${
                      wakeMode
                        ? "bg-sky-500 text-white shadow-sm"
                        : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                    }`}
                  >
                    {wakeMode ? "Active" : "Disabled"}
                  </button>
                </div>

                <div className="flex items-center justify-between py-2">
                  <div>
                    <div className="text-xs font-semibold text-slate-800">Voice Synthesis Engine</div>
                    <div className="text-[11px] text-slate-400">Native macOS Speech / Local STT &amp; TTS</div>
                  </div>
                  <span className="text-xs font-mono text-sky-600 bg-sky-50 px-2 py-1 rounded">
                    macOS Native
                  </span>
                </div>
              </div>

              {/* Configuration Guide */}
              <div className="nova-card p-6 bg-white space-y-3">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-2">
                  <Sliders size={15} className="text-sky-600" />
                  <span>Environment Configuration (.env)</span>
                </h3>
                <p className="text-xs text-slate-500">
                  Current backend parameters loaded from the project root environment.
                </p>
                <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 font-mono text-xs text-slate-700 space-y-1">
                  <div><span className="text-sky-600 font-bold">OLLAMA_MODEL</span>=llama3.2:1b</div>
                  <div><span className="text-sky-600 font-bold">STT_MODEL</span>=base</div>
                  <div><span className="text-sky-600 font-bold">TTS_ENGINE</span>=macos</div>
                  <div><span className="text-sky-600 font-bold">LOG_LEVEL</span>=INFO</div>
                </div>
              </div>

              {/* Quick Setup for Ollama */}
              <div className="nova-card p-6 bg-white space-y-3">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-2">
                  <Sparkles size={15} className="text-sky-600" />
                  <span>Quick Setup &amp; Verification</span>
                </h3>
                <div className="space-y-2 text-xs text-slate-600">
                  <div className="flex items-start gap-2">
                    <span className="font-bold text-sky-600">1.</span>
                    <span>Install Ollama: <code className="bg-slate-100 px-1 py-0.5 rounded font-mono">brew install ollama</code></span>
                  </div>
                  <div className="flex items-start gap-2">
                    <span className="font-bold text-sky-600">2.</span>
                    <span>Pull default model: <code className="bg-slate-100 px-1 py-0.5 rounded font-mono">ollama pull llama3.2:1b</code></span>
                  </div>
                  <div className="flex items-start gap-2">
                    <span className="font-bold text-sky-600">3.</span>
                    <span>Start local server: <code className="bg-slate-100 px-1 py-0.5 rounded font-mono">ollama serve</code></span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
