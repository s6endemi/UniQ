"use client";

import { motion } from "motion/react";
import { AiOrb } from "@/components/ai-orb";
import { cn } from "@/lib/utils";

export type Message =
  | { id: string; role: "user"; content: string }
  | { id: string; role: "assistant"; content: string; artifactId?: string };

interface ConversationProps {
  messages: Message[];
  pending: boolean;
  onArtifactClick?: (artifactId: string) => void;
}

export function Conversation({ messages, pending, onArtifactClick }: ConversationProps) {
  return (
    <div className="flex flex-col gap-6 p-6">
      {messages.length === 0 && !pending && <EmptyState />}
      {messages.map((m) => (
        <MessageBubble key={m.id} message={m} onArtifactClick={onArtifactClick} />
      ))}
      {pending && <ThinkingIndicator />}
    </div>
  );
}

function EmptyState() {
  const prompts = [
    "How does BMI change over time for Mounjaro vs Wegovy patients?",
    "Which side effects are most common across GLP-1 medications?",
    "Export FHIR for the patient with the largest BMI drop.",
    "Show medication adherence patterns by brand.",
  ];
  return (
    <div className="flex flex-col items-center gap-8 py-12 text-center">
      <AiOrb size={120} />
      <div className="space-y-2">
        <h2 className="font-display text-2xl font-semibold tracking-tight text-text-0">
          Ask your unified data.
        </h2>
        <p className="max-w-md text-sm text-text-2">
          The analyst reads the discovered schema, generates a read-only query,
          and returns the answer with a visual artifact you can download.
        </p>
      </div>
      <div className="flex flex-col gap-2">
        {prompts.map((p) => (
          <button
            key={p}
            className="rounded-full border border-ink-700 bg-ink-900/60 px-4 py-2 text-sm text-text-2 transition-colors hover:border-glacial/40 hover:text-text-0"
          >
            {p}
          </button>
        ))}
      </div>
    </div>
  );
}

function MessageBubble({
  message,
  onArtifactClick,
}: {
  message: Message;
  onArtifactClick?: (artifactId: string) => void;
}) {
  const isUser = message.role === "user";
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className={cn("flex gap-3", isUser ? "justify-end" : "justify-start")}
    >
      {!isUser && (
        <div className="mt-1 grid h-7 w-7 shrink-0 place-items-center rounded-full border border-glacial/30 bg-glacial/10">
          <span className="h-1.5 w-1.5 rounded-full bg-glacial" />
        </div>
      )}
      <div
        className={cn(
          "max-w-[75%] rounded-2xl px-4 py-3 text-sm leading-relaxed",
          isUser
            ? "bg-glacial/15 text-text-0"
            : "border border-ink-700 bg-ink-900/60 text-text-1",
        )}
      >
        <div className="whitespace-pre-wrap">{message.content}</div>
        {message.role === "assistant" && message.artifactId && (
          <button
            onClick={() => onArtifactClick?.(message.artifactId!)}
            className="mt-3 inline-flex items-center gap-2 rounded-md border border-glacial/30 bg-glacial/10 px-2.5 py-1 font-mono text-[11px] uppercase tracking-wider text-glacial hover:border-glacial/60"
          >
            view artifact →
          </button>
        )}
      </div>
    </motion.div>
  );
}

function ThinkingIndicator() {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="flex gap-3"
    >
      <div className="mt-1 grid h-7 w-7 shrink-0 place-items-center rounded-full border border-glacial/30 bg-glacial/10">
        <motion.span
          className="h-1.5 w-1.5 rounded-full bg-glacial"
          animate={{ scale: [1, 1.6, 1], opacity: [0.6, 1, 0.6] }}
          transition={{ duration: 1.2, repeat: Infinity, ease: "easeInOut" }}
        />
      </div>
      <div className="max-w-[75%] rounded-2xl border border-ink-700 bg-ink-900/60 px-4 py-3">
        <div className="flex items-center gap-1">
          {[0, 150, 300].map((delay) => (
            <motion.span
              key={delay}
              className="h-1.5 w-1.5 rounded-full bg-text-2"
              animate={{ y: [0, -4, 0] }}
              transition={{
                duration: 0.8,
                repeat: Infinity,
                delay: delay / 1000,
                ease: "easeInOut",
              }}
            />
          ))}
          <span className="ml-2 font-mono text-[10px] uppercase tracking-wider text-text-3">
            analyst is reasoning…
          </span>
        </div>
      </div>
    </motion.div>
  );
}
