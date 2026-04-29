"use client";

import { create } from "zustand";

export type ChatTurn = {
  id: string;
  role: "user" | "apollo";
  content: string;
  timestamp: number;
};

export type ApolloState =
  | "idle"
  | "listening"
  | "thinking"
  | "speaking"
  | "error";

interface AppStore {
  // Chat
  chat: ChatTurn[];
  pushTurn: (turn: Omit<ChatTurn, "id" | "timestamp">) => void;
  clearChat: () => void;

  // Orb / voice machine (real wiring lands in Phase 6 — fields here so HUD can already react)
  apolloState: ApolloState;
  setApolloState: (state: ApolloState) => void;
  audioLevel: number; // [0, 1]
  setAudioLevel: (level: number) => void;
}

export const useAppStore = create<AppStore>((set) => ({
  chat: [],
  pushTurn: (turn) =>
    set((s) => ({
      chat: [
        ...s.chat,
        {
          ...turn,
          id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          timestamp: Date.now(),
        },
      ],
    })),
  clearChat: () => set({ chat: [] }),

  apolloState: "idle",
  setApolloState: (state) => set({ apolloState: state }),
  audioLevel: 0,
  setAudioLevel: (level) => set({ audioLevel: Math.max(0, Math.min(1, level)) }),
}));
