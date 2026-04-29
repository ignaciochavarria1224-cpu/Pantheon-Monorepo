"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  ensureAudioContext,
  startAudioLevelMeter,
  startSyntheticSpeakingMeter,
} from "@/lib/audio-level";
import { useAppStore } from "@/lib/store";

const BASE_URL = process.env.NEXT_PUBLIC_APOLLO_API ?? "http://localhost:8001";

type VoiceResponse = {
  transcription: string;
  response: string;
};

function pickRecordingMime(): string | undefined {
  if (typeof MediaRecorder === "undefined") return undefined;
  const candidates = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/ogg;codecs=opus",
    "audio/mp4",
  ];
  for (const m of candidates) {
    if (MediaRecorder.isTypeSupported(m)) return m;
  }
  return undefined;
}

function speak(text: string, onEnd: () => void) {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) {
    onEnd();
    return;
  }
  // Browser TTS doesn't expose audio for analysis — feed the orb a synthetic level.
  const stopMeter = startSyntheticSpeakingMeter();
  try {
    const utter = new SpeechSynthesisUtterance(text);
    utter.rate = 1.05;
    utter.pitch = 1.0;
    utter.volume = 1.0;

    // Prefer a clear English voice if available
    const voices = window.speechSynthesis.getVoices();
    const preferred =
      voices.find((v) => /Google US English/i.test(v.name)) ??
      voices.find((v) => /Samantha/i.test(v.name)) ??
      voices.find((v) => /English/i.test(v.name)) ??
      null;
    if (preferred) utter.voice = preferred;

    utter.onend = () => {
      stopMeter();
      onEnd();
    };
    utter.onerror = () => {
      stopMeter();
      onEnd();
    };
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utter);
  } catch {
    stopMeter();
    onEnd();
  }
}

export function useVoice() {
  const setApolloState = useAppStore((s) => s.setApolloState);
  const pushTurn = useAppStore((s) => s.pushTurn);

  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const meterStopRef = useRef<(() => void) | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const [isListening, setIsListening] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const stop = useCallback(() => {
    const rec = recorderRef.current;
    if (rec && rec.state !== "inactive") {
      rec.stop();
    }
    meterStopRef.current?.();
    meterStopRef.current = null;
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }, []);

  const start = useCallback(async () => {
    if (isListening || isProcessing) return;
    setError(null);
    try {
      ensureAudioContext();
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const mimeType = pickRecordingMime();
      const rec = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      recorderRef.current = rec;
      chunksRef.current = [];

      rec.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      rec.onstop = async () => {
        const blob = new Blob(chunksRef.current, { type: mimeType ?? "audio/webm" });
        // Stop drawing mic level immediately — we're now in `thinking`
        meterStopRef.current?.();
        meterStopRef.current = null;
        streamRef.current?.getTracks().forEach((t) => t.stop());
        streamRef.current = null;

        if (blob.size < 1500) {
          setApolloState("idle");
          setIsListening(false);
          setIsProcessing(false);
          return;
        }

        setApolloState("thinking");
        setIsProcessing(true);
        try {
          const ext = mimeType?.includes("mp4")
            ? "m4a"
            : mimeType?.includes("ogg")
              ? "ogg"
              : "webm";
          const form = new FormData();
          form.append("audio", blob, `apollo-voice.${ext}`);
          const res = await fetch(`${BASE_URL}/voice`, {
            method: "POST",
            body: form,
          });
          if (!res.ok) {
            const detail = await res.text().catch(() => "");
            throw new Error(`${res.status} ${res.statusText} — ${detail.slice(0, 200)}`);
          }
          const data = (await res.json()) as VoiceResponse;
          if (data.transcription) {
            pushTurn({ role: "user", content: data.transcription });
          }
          if (data.response) {
            pushTurn({ role: "apollo", content: data.response });
            setApolloState("speaking");
            speak(data.response, () => {
              setApolloState("idle");
            });
          } else {
            setApolloState("idle");
          }
        } catch (err) {
          const msg = err instanceof Error ? err.message : String(err);
          setError(msg);
          pushTurn({ role: "apollo", content: `Voice error: ${msg}` });
          setApolloState("error");
          setTimeout(() => setApolloState("idle"), 2400);
        } finally {
          setIsProcessing(false);
          setIsListening(false);
        }
      };

      rec.start();
      setIsListening(true);
      setApolloState("listening");
      meterStopRef.current = startAudioLevelMeter(stream);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
      setApolloState("error");
      setIsListening(false);
      setTimeout(() => setApolloState("idle"), 2400);
    }
  }, [isListening, isProcessing, pushTurn, setApolloState]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stop();
    };
  }, [stop]);

  return { start, stop, isListening, isProcessing, error };
}
