import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import { SPEECH_LANG } from "./i18n";
import type { Lang } from "./types";

/**
 * Read-aloud. Prefers the backend's offline Piper voice; falls back to the
 * browser's speech synthesis if it has a voice for the language.
 */
export function useSpeaker(sessionId?: string) {
  const [playing, setPlaying] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const audio = useRef<HTMLAudioElement | null>(null);
  const urls = useRef<string[]>([]);
  const queue = useRef<{ texts: string[]; lang: Lang; id: string } | null>(null);

  const stop = useCallback(() => {
    queue.current = null;
    audio.current?.pause();
    window.speechSynthesis?.cancel();
    setPlaying(null);
  }, []);

  const playOne = useCallback(
    async (text: string, lang: Lang): Promise<void> => {
      const blob = await api.tts(text, lang, sessionId).catch(() => null);
      if (blob) {
        const url = URL.createObjectURL(blob);
        urls.current.push(url);
        await new Promise<void>((resolve) => {
          const a = new Audio(url);
          audio.current = a;
          a.onended = a.onerror = a.onpause = () => resolve();
          a.play().catch(() => resolve());
        });
        return;
      }
      const synth = window.speechSynthesis;
      const voice = synth?.getVoices().find((v) => v.lang.toLowerCase().startsWith(lang));
      if (!synth || !voice) throw new Error("no-voice");
      await new Promise<void>((resolve) => {
        const u = new SpeechSynthesisUtterance(text);
        u.lang = SPEECH_LANG[lang];
        u.voice = voice;
        u.rate = 0.9;
        u.onend = u.onerror = () => resolve();
        synth.speak(u);
      });
    },
    [sessionId],
  );

  const speak = useCallback(
    async (id: string, texts: string[], lang: Lang) => {
      stop();
      setError(null);
      const q = { texts: texts.filter(Boolean), lang, id };
      queue.current = q;
      setPlaying(id);
      try {
        for (const text of q.texts) {
          if (queue.current !== q) return;
          await playOne(text, lang);
        }
      } catch {
        setError("no-voice");
      } finally {
        if (queue.current === q) {
          queue.current = null;
          setPlaying(null);
        }
      }
    },
    [playOne, stop],
  );

  const release = useCallback(() => {
    stop();
    urls.current.forEach((u) => URL.revokeObjectURL(u));
    urls.current = [];
  }, [stop]);

  useEffect(() => release, [release]);

  return { speak, stop, playing, error, release };
}
