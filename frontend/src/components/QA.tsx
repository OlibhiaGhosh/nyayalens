import { Loader2, Mic, Send, Square } from "lucide-react";
import { useState } from "react";
import { api } from "../api";
import { t } from "../i18n";
import type { Card, Lang } from "../types";
import { useRecorder } from "../voice";
import { Panel, SpeakButton } from "./ui";

type Speaker = { speak: (id: string, texts: string[], lang: Lang) => void; stop: () => void; playing: string | null };
type QA = { q: string; answer: string; found: boolean; clause_ids: number[]; lang: Lang; voice: boolean };
type Busy = null | "hearing" | "answering";

/** Grounded follow-up: every answer cites a clause or says "not in this document".
 *  Questions can be typed or spoken; a spoken question is answered in the language it was asked in. */
export function QAPanel({
  lang,
  sessionId,
  cards,
  speaker,
  onJump,
}: {
  lang: Lang;
  sessionId: string;
  cards: Card[];
  speaker: Speaker;
  onJump: (id: number) => void;
}) {
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState<Busy>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [history, setHistory] = useState<QA[]>([]);
  const label = (id: number) => cards.find((c) => c.clause_id === id)?.label || String(id);

  const ask = async (question: string, qLang: Lang, voice: boolean) => {
    question = question.trim();
    if (!question) return;
    setBusy("answering");
    try {
      const r = await api.ask(sessionId, qLang, question);
      setHistory((h) => [{ q: question, ...r, lang: qLang, voice }, ...h]);
      setQ("");
      // Someone who asked out loud most likely wants to hear the answer.
      if (voice) speaker.speak(`qa-${history.length}`, [r.answer], qLang);
    } finally {
      setBusy(null);
    }
  };

  const rec = useRecorder(async (wav) => {
    setBusy("hearing");
    try {
      const r = await api.transcribe(sessionId, lang, wav);
      if (!r.text.trim()) {
        setNotice(t(lang, "notHeard"));
        setBusy(null);
        return;
      }
      setQ(r.text);
      await ask(r.text, r.lang, true);
    } catch (e) {
      setNotice(String(e).includes("503") || String(e).includes("Gemma") ? t(lang, "voiceNeedsGemma") : t(lang, "notHeard"));
      setBusy(null);
    }
  });

  const startVoice = () => {
    setNotice(null);
    speaker.stop();
    rec.start();
  };

  const status = rec.recording
    ? t(lang, "listening", { s: rec.seconds })
    : busy
      ? t(lang, busy)
      : rec.error === "denied" || rec.error === "unsupported"
        ? t(lang, "micDenied")
        : notice;

  return (
    <Panel className="space-y-3">
      <h3 className="text-xl font-bold">{t(lang, "askTitle")}</h3>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          ask(q, lang, false);
        }}
        className="flex flex-wrap gap-2"
      >
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={t(lang, "askPlaceholder")}
          className="min-w-0 flex-1 basis-56 rounded-xl border-2 border-ink/20 px-3 py-2 text-lg"
          maxLength={500}
          disabled={rec.recording}
        />
        <button
          type="button"
          onClick={rec.recording ? rec.stop : startVoice}
          disabled={!!busy}
          aria-label={rec.recording ? t(lang, "stopRecording") : t(lang, "speakQuestion")}
          className={`inline-flex items-center gap-2 rounded-xl border-2 px-4 py-2 font-bold disabled:opacity-40 ${
            rec.recording ? "animate-pulse border-bad bg-bad text-white" : "border-ink bg-white text-ink"
          }`}
        >
          {rec.recording ? <Square className="size-5" /> : <Mic className="size-5" />}
          {rec.recording ? t(lang, "stopRecording") : t(lang, "speakQuestion")}
        </button>
        <button
          type="submit"
          disabled={!!busy || rec.recording}
          className="inline-flex items-center gap-2 rounded-xl bg-ink px-4 py-2 font-bold text-white disabled:opacity-40"
        >
          <Send className="size-5" /> {t(lang, "ask")}
        </button>
      </form>
      {status && (
        <p className="flex items-center gap-2 text-ink/70" role="status" aria-live="polite">
          {busy && <Loader2 className="size-4 animate-spin" />}
          {status}
        </p>
      )}
      {history.map((h, i) => {
        const id = `qa-${history.length - 1 - i}`;
        return (
          <div key={id} className="space-y-1 rounded-xl bg-paper p-3">
            <p className="flex items-center gap-1.5 font-bold">
              {h.voice && <Mic className="size-4 shrink-0 text-ink/50" aria-label={t(lang, "speakQuestion")} />}
              {h.q}
            </p>
            <div className="flex items-start gap-2">
              <p className={`flex-1 text-lg ${h.found ? "" : "text-ink/60"}`}>{h.answer}</p>
              <SpeakButton
                small
                id={id}
                lang={lang}
                playing={speaker.playing}
                onPlay={() => speaker.speak(id, [h.answer], h.lang)}
                onStop={speaker.stop}
              />
            </div>
            {h.clause_ids.length > 0 && (
              <p className="text-sm">
                {t(lang, "fromPart")}:{" "}
                {h.clause_ids.map((cid) => (
                  <button key={cid} onClick={() => onJump(cid)} className="mr-2 font-bold underline">
                    {label(cid)}
                  </button>
                ))}
              </p>
            )}
          </div>
        );
      })}
    </Panel>
  );
}
