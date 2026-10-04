import { MessageCircleQuestion } from "lucide-react";
import { t } from "../i18n";
import type { Lang, Result } from "../types";
import { Panel, SpeakButton } from "./ui";

type Speaker = { speak: (id: string, texts: string[], lang: Lang) => void; stop: () => void; playing: string | null };

export function Summary({
  lang,
  result,
  speaker,
  onJump,
}: {
  lang: Lang;
  result: Result;
  speaker: Speaker;
  onJump: (id: number) => void;
}) {
  if (!result.summary.length) return null;
  return (
    <Panel className="space-y-3 border-2 border-ink">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="flex items-center gap-2 text-xl font-bold">
          <MessageCircleQuestion className="size-7" /> {t(lang, "threeThings")}
        </h3>
        <SpeakButton
          id="summary"
          lang={lang}
          label={t(lang, "playAll")}
          playing={speaker.playing}
          onPlay={() => speaker.speak("summary", result.summary.map((s, i) => `${i + 1}. ${s.question}`), lang)}
          onStop={speaker.stop}
        />
      </div>
      <ol className="space-y-2">
        {result.summary.map((s, i) => (
          <li key={i} className="flex items-center gap-3 rounded-xl bg-paper p-3">
            <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-ink text-lg font-bold text-white">
              {i + 1}
            </span>
            <span className="flex-1 text-lg">{s.question}</span>
            <SpeakButton
              small
              id={`summary-${i}`}
              lang={lang}
              playing={speaker.playing}
              onPlay={() => speaker.speak(`summary-${i}`, [s.question], lang)}
              onStop={speaker.stop}
            />
            {s.clause_id != null && (
              <button onClick={() => onJump(s.clause_id!)} className="no-print text-sm underline">
                {t(lang, "clause")} →
              </button>
            )}
          </li>
        ))}
      </ol>
    </Panel>
  );
}
