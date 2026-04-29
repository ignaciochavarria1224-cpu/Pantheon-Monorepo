"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useOverview() {
  return useQuery({
    queryKey: ["overview"],
    queryFn: api.overview,
    refetchInterval: 30_000,
  });
}

export function useBlackBookSnapshot() {
  return useQuery({
    queryKey: ["blackbook", "snapshot"],
    queryFn: api.blackbookSnapshot,
    refetchInterval: 30_000,
  });
}

export function useMaridianSnapshot() {
  return useQuery({
    queryKey: ["maridian", "snapshot"],
    queryFn: api.maridianSnapshot,
    refetchInterval: 60_000,
  });
}

export function useMaridianCycleStatus(enabled = false) {
  return useQuery({
    queryKey: ["maridian", "cycle-status"],
    queryFn: api.maridianCycleStatus,
    refetchInterval: enabled ? 5_000 : false,
    enabled,
  });
}

export function useOlympusSnapshot() {
  return useQuery({
    queryKey: ["olympus", "snapshot"],
    queryFn: api.olympusSnapshot,
    refetchInterval: 20_000,
  });
}

export function useChatMutation() {
  return useMutation({
    mutationFn: ({ message, channel = "ui" }: { message: string; channel?: "ui" | "voice" }) =>
      api.chat(message, channel),
  });
}

export function useRunMaridianCycle() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.runMaridianCycleAsync,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["maridian"] });
    },
  });
}
