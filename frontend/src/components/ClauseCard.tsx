import { AlertTriangle, BookOpen, Brain, ExternalLink, Scale, ShieldAlert } from "lucide-react";
import { useState } from "react";
import { t } from "../i18n";
import type { Card, Lang } from "../types";
import { Panel, SpeakButton, VerdictBadge, VERDICT_STYLE } from "./ui";

type Speaker = { speak: (id: string, texts: string[], lang: Lang) => void; stop: () => void; playing: string | null };

export function ClauseCard({ card, lang, speaker }: { card: Card; lang: Lang; speaker: Speaker }) {
  const [compare, setCompare] = useState(false);
  const s = VERDICT_STYLE[card.verdict];
  const id = `card-${card.clause_id}`;
  const readAloud = [card.plain_explanation, card.why_it_matters, ...(card.questions_to_ask ?? []), card.ask_to_change]
    .filter(Boolean) as string[];

  return (
    <Panel className={`space-y-4 border-l-8 ${s.border}`}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="text-xl font-bold">
            {t(lang, "clause")} {card.label || card.clause_id}
          </span>
          <VerdictBadge v={card.verdict} lang={lang} />
        </div>
        {readAloud.length > 0 && (
          <SpeakButton
            id={id}
            lang={lang}
            playing={speaker.playing}
            onPlay={() => speaker.speak(id, readAloud, lang)}
            onStop={speaker.stop}
          />
        )}
      </div>

      {card.low_conf && (
        <p className="flex items-center gap-2 rounded-lg bg-warn-soft p-2 text-warn">
          <AlertTriangle className="size-5 shrink-0" /> {t(lang, "lowConfCard")}
        </p>
      )}

      {card.pending ? (
        <p className="flex items-center gap-3 text-ink/70" role="status">
          <span className="size-5 animate-spin rounded-full border-4 border-ink/15 border-t-ink" />
          {t(lang, "checkingPart")}
        </p>
      ) : card.verdict === "UNCHECKED" ? (
        <>
          <p className="text-ink/70">{t(lang, "notChecked")}</p>
          <blockquote className="rounded-lg bg-paper p-3 text-ink/80">{card.original_text}</blockquote>
        </>
      ) : (
        <>
          <Section icon={<BookOpen className="size-5" />} title={t(lang, "whatItSays")}>
            {card.plain_explanation}
          </Section>
          {card.why_it_matters && (
            <Section icon={<ShieldAlert className="size-5" />} title={t(lang, "whyItMatters")}>
              {card.why_it_matters}
            </Section>
          )}
          {!!card.questions_to_ask?.length && (
            <div>
              <h4 className="mb-2 font-bold">{t(lang, "questionsToAsk")}</h4>
              <ul className="space-y-2">
                {card.questions_to_ask.map((q, i) => (
                  <li key={i} className="flex items-center gap-2 rounded-lg bg-paper p-2">
                    <SpeakButton
                      small
                      id={`${id}-q${i}`}
                      lang={lang}
                      playing={speaker.playing}
                      onPlay={() => speaker.speak(`${id}-q${i}`, [q], lang)}
                      onStop={speaker.stop}
                    />
                    <span className="text-lg">{q}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {card.ask_to_change && (
            <p className="rounded-lg border-2 border-dashed border-ink/20 p-3">
              <b>{t(lang, "askToChange")}: </b>
              {card.ask_to_change}
            </p>
          )}
          {card.verdict_source === "raised_by_rules" && (
            <p className="text-sm text-ink/60">{t(lang, "raisedByRules")}</p>
          )}

          <div>
            <button onClick={() => setCompare((v) => !v)} className="font-bold underline underline-offset-4">
              {t(lang, "compare")}
            </button>
            {compare && (
              <div className="mt-3 grid gap-3 md:grid-cols-2">
                <div className={`rounded-lg p-3 ${s.bg}`}>
                  <h5 className="mb-1 text-sm font-bold uppercase">{t(lang, "onPaper")}</h5>
                  <p>{card.original_text}</p>
                </div>
                <div className="rounded-lg bg-good-soft p-3">
                  <h5 className="mb-1 text-sm font-bold uppercase">{t(lang, "fairer")}</h5>
                  <p>{card.fair_rewrite_en || card.riders_en?.[0] || "—"}</p>
                </div>
              </div>
            )}
          </div>

          {card.statutes.length > 0 && (
            <div className="space-y-2">
              <h4 className="flex items-center gap-2 font-bold">
                <Scale className="size-5" /> {t(lang, "lawRefs")}
              </h4>
              {card.statutes.map((st) => (
                <details key={st.id} className="rounded-lg bg-paper p-2">
                  <summary className="cursor-pointer font-semibold">
                    {st.name}{" "}
                    <span className={`text-xs ${st.last_verified ? "text-good" : "text-warn"}`}>
                      ({st.last_verified ? `${t(lang, "verifiedOn")} ${st.last_verified}` : t(lang, "unverified")})
                    </span>
                  </summary>
                  <p className="mt-1">{st.plain_summary}</p>
                  <p className="mt-1 flex items-center gap-1 text-sm text-ink/60">
                    <ExternalLink className="size-3.5" /> {st.source_hint || st.source_url}
                  </p>
                </details>
              ))}
            </div>
          )}

          {card.thinking && (
            <details className="rounded-lg border border-dashed border-ink/30 p-2 text-sm">
              <summary className="flex cursor-pointer items-center gap-2 font-semibold">
                <Brain className="size-4" /> {t(lang, "reasoning")}
              </summary>
              <pre className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap font-sans text-ink/70">{card.thinking}</pre>
            </details>
          )}
        </>
      )}
    </Panel>
  );
}

function Section({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode }) {
  return (
    <div>
      <h4 className="mb-1 flex items-center gap-2 font-bold">
        {icon} {title}
      </h4>
      <p className="text-lg leading-relaxed">{children}</p>
    </div>
  );
}
