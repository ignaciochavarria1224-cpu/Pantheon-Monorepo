"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Send, Trash2, Mic } from "lucide-react";

import { Orb } from "@/components/orb/Orb";
import { WireframeRing } from "@/components/hud/Wireframe";
import { GlowPanel } from "@/components/hud/GlowPanel";
import { useAppStore } from "@/lib/store";
import { useChatMutation } from "@/lib/hooks";
import { api } from "@/lib/api";
import { fmtRelative } from "@/lib/format";

export default function ApolloPage() {
  const chat = useAppStore((s) => s.chat);
  const pushTurn = useAppStore((s) => s.pushTurn);
  const clearChat = useAppStore((s) => s.clearChat);
  const apolloState = useAppStore((s) => s.apolloState);
  const setApolloState = useAppStore((s) => s.setApolloState);

  const [input, setInput] = useState("");
  const chatMutation = useChatMutation();

  const sending = chatMutation.isPending;

  async function handleSend(e?: React.FormEvent) {
    e?.preventDefault();
    const message = input.trim();
    if (!message || sending) return;
    pushTurn({ role: "user", content: message });
    setInput("");
    setApolloState("thinking");
    try {
      const reply = await chatMutation.mutateAsync({ message });
      pushTurn({ role: "apollo", content: reply.response });
      setApolloState("speaking");
      // brief "speaking" flicker; real TTS-driven amplitude lands in Phase 6
      setTimeout(() => setApolloState("idle"), 1200);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      pushTurn({ role: "apollo", content: `Error: ${msg}` });
      setApolloState("error");
      setTimeout(() => setApolloState("idle"), 2400);
    }
  }

  async function handleClear() {
    clearChat();
    try {
      await api.resetChat();
    } catch {
      /* harmless if backend rejects */
    }
  }

  return (
    <div className="mx-auto grid w-full max-w-7xl gap-6 lg:grid-cols-[1.15fr_1fr]">
      {/* Orb stage */}
      <section className="flex flex-col items-center justify-start gap-6">
        <div className="relative flex h-[460px] w-full items-center justify-center md:h-[540px]">
          <WireframeRing
            size={520}
            ticks={36}
            color="rgba(0, 229, 255, 0.32)"
            rotate="slow"
            className="absolute inset-0 m-auto"
          />
          <WireframeRing
            size={400}
            ticks={18}
            dashed
            color="rgba(255, 179, 71, 0.32)"
            rotate="slower"
            className="absolute inset-0 m-auto"
          />
          <Orb className="relative z-10" />
        </div>

        <motion.div
          key={apolloState}
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-center gap-3 font-mono text-[11px] uppercase tracking-widestmax text-cyan/70"
        >
          <span className="inline-block h-1.5 w-1.5 rounded-full bg-cyan shadow-glow-cyan" />
          STATUS · {apolloState}
        </motion.div>
      </section>

      {/* Chat panel */}
      <section className="flex flex-col gap-4">
        <GlowPanel
          eyebrow="Channel · UI"
          title="Apollo"
          action={
            <button
              type="button"
              onClick={handleClear}
              aria-label="Clear chat"
              className="rounded border border-cyan/20 p-1.5 text-white/55 transition hover:border-cyan/60 hover:text-cyan"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          }
          className="flex flex-1 flex-col"
        >
          <div className="flex h-[420px] flex-col gap-3 overflow-y-auto pr-2 md:h-[460px]">
            <AnimatePresence initial={false}>
              {chat.length === 0 && (
                <motion.div
                  key="empty"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="m-auto max-w-sm text-center font-mono text-[12px] tracking-wider text-white/40"
                >
                  Apollo is listening on Ollama / llama3.2.
                  <br />
                  Ask anything. Say &quot;run my journal cycle&quot; or &quot;what&apos;s my balance&quot;.
                </motion.div>
              )}
              {chat.map((turn) => (
                <motion.div
                  key={turn.id}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  className={`flex flex-col gap-1 ${
                    turn.role === "user" ? "items-end" : "items-start"
                  }`}
                >
                  <div className="font-mono text-[10px] uppercase tracking-widestmax text-white/35">
                    {turn.role === "user" ? "you" : "apollo"} · {fmtRelative(new Date(turn.timestamp).toISOString())}
                  </div>
                  <div
                    className={`max-w-[85%] whitespace-pre-wrap rounded border px-3 py-2 font-mono text-[13px] leading-relaxed ${
                      turn.role === "user"
                        ? "border-gold/30 bg-gold/5 text-gold"
                        : "border-cyan/25 bg-cyan/5 text-white/85"
                    }`}
                  >
                    {turn.content}
                  </div>
                </motion.div>
              ))}
              {sending && (
                <motion.div
                  key="thinking"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="self-start font-mono text-[11px] tracking-wider text-cyan/70"
                >
                  apollo · thinking ◌◌◌
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </GlowPanel>

        <form
          onSubmit={handleSend}
          className="flex items-center gap-2 rounded border border-cyan/25 bg-ink/70 p-2 backdrop-blur"
        >
          <button
            type="button"
            disabled
            title="Voice input lands in Phase 6"
            className="flex h-9 w-9 items-center justify-center rounded border border-cyan/15 text-white/30"
            aria-label="Push to talk (coming Phase 6)"
          >
            <Mic className="h-4 w-4" />
          </button>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask Apollo…"
            className="flex-1 bg-transparent px-2 py-2 font-mono text-[13px] text-white placeholder:text-white/35 focus:outline-none"
            disabled={sending}
          />
          <button
            type="submit"
            disabled={!input.trim() || sending}
            className="flex h-9 items-center gap-2 rounded border border-cyan/40 px-3 font-mono text-[12px] uppercase tracking-wider text-cyan transition hover:border-glow-cyan-strong hover:text-glow-cyan disabled:opacity-40"
          >
            <Send className="h-3.5 w-3.5" />
            send
          </button>
        </form>
      </section>
    </div>
  );
}
