"use client";

import { useEffect, useRef } from "react";
import { useAppStore } from "@/lib/store";

/**
 * Singleton AudioContext — must be unlocked on first user gesture (iOS).
 * Call ensureAudioContext() in a click/touchend handler before using mic
 * or pushing TTS amplitude.
 */
let _ctx: AudioContext | null = null;

export function ensureAudioContext(): AudioContext {
  if (typeof window === "undefined") {
    throw new Error("AudioContext requested on server");
  }
  if (!_ctx) {
    const Ctor = window.AudioContext ?? (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    _ctx = new Ctor();
  }
  if (_ctx.state === "suspended") {
    _ctx.resume().catch(() => {
      /* iOS will retry on next gesture */
    });
  }
  return _ctx;
}

/**
 * Drive useAppStore.audioLevel from a MediaStream (mic or TTS playback).
 * Returns a stop() function to disconnect when done.
 */
export function startAudioLevelMeter(stream: MediaStream): () => void {
  const ctx = ensureAudioContext();
  const analyser = ctx.createAnalyser();
  analyser.fftSize = 512;
  analyser.smoothingTimeConstant = 0.7;

  const source = ctx.createMediaStreamSource(stream);
  source.connect(analyser);

  const buffer = new Uint8Array(analyser.frequencyBinCount);
  const setLevel = useAppStore.getState().setAudioLevel;

  let raf = 0;
  let stopped = false;

  const tick = () => {
    if (stopped) return;
    analyser.getByteTimeDomainData(buffer);
    let sumSq = 0;
    for (let i = 0; i < buffer.length; i++) {
      const v = (buffer[i] - 128) / 128;
      sumSq += v * v;
    }
    const rms = Math.sqrt(sumSq / buffer.length);
    // RMS for speech is roughly [0.02, 0.25]; map to [0, 1] with a soft ceiling.
    const normalized = Math.min(1, rms * 4.5);
    setLevel(normalized);
    raf = requestAnimationFrame(tick);
  };
  raf = requestAnimationFrame(tick);

  return () => {
    stopped = true;
    cancelAnimationFrame(raf);
    try {
      source.disconnect();
    } catch {
      /* already disconnected */
    }
    setLevel(0);
  };
}

/**
 * Synthetic amplitude for browser speechSynthesis (which can't be analyser-tapped).
 * Returns a stop() function. Real audio analysis lands when we swap to Piper.
 */
export function startSyntheticSpeakingMeter(): () => void {
  const setLevel = useAppStore.getState().setAudioLevel;
  let raf = 0;
  let stopped = false;
  const start = performance.now();

  const tick = () => {
    if (stopped) return;
    const t = (performance.now() - start) / 1000;
    // Two layered sines + light random noise — visually mimics speech cadence
    const base = 0.32 + 0.18 * Math.sin(t * 7.4) + 0.12 * Math.sin(t * 13.1 + 1.2);
    const noise = (Math.random() - 0.5) * 0.08;
    setLevel(Math.max(0, Math.min(1, base + noise)));
    raf = requestAnimationFrame(tick);
  };
  raf = requestAnimationFrame(tick);

  return () => {
    stopped = true;
    cancelAnimationFrame(raf);
    setLevel(0);
  };
}

/**
 * Smoothly decay the audio level to zero on unmount — useful when leaving
 * the Apollo route mid-session.
 */
export function useAudioLevelCleanup() {
  const ref = useRef<(() => void) | null>(null);
  useEffect(() => {
    return () => {
      ref.current?.();
      useAppStore.getState().setAudioLevel(0);
    };
  }, []);
  return ref;
}
