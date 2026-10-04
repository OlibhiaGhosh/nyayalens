import { Activity, FileSignature, Info, LifeBuoy, RotateCcw, Trash2, Type } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import { Capture } from "./components/Capture";
import { ClauseCard } from "./components/ClauseCard";
import { Heatmap } from "./components/Heatmap";
import { MoneyView } from "./components/MoneyView";
import { QAPanel } from "./components/QA";
import { Review } from "./components/Review";
import { Rider } from "./components/Rider";
import { SelfCheck } from "./components/SelfCheck";
import { Summary } from "./components/Summary";
import { BigButton, Panel, VERDICT_STYLE, VerdictIcon } from "./components/ui";
import { LANG_NAMES, t } from "./i18n";
import { useSpeaker } from "./speech";
import type { Lang, Result, SessionView, StreamEvent, Terms, Verdict } from "./types";

type Stage = "capture" | "reading" | "review" | "analyzing" | "results" | "rider" | "selfcheck" | "wiped";

export default function App() {
  const [lang, setLang] = useState<Lang>("bn");
  const [big, setBig] = useState(false);
  const [stage, setStage] = useState<Stage>("capture");
  const [prev, setPrev] = useState<Stage>("capture");
  const [session, setSession] = useState<SessionView | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [progress, setProgress] = useState<string>("");
  const [verdicts, setVerdicts] = useState<Verdict[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const speaker = useSpeaker(session?.session_id);

  useEffect(() => {
    document.documentElement.classList.toggle("big", big);
    document.documentElement.lang = lang;
  }, [big, lang]);

  const onEvent = useCallback(
    (l: Lang) => (e: StreamEvent) => {
      if (e.type === "progress") {
        setProgress(
          e.stage === "analyze"
            ? t(l, "progressAnalyze", { i: e.i, n: e.n })
            : e.stage === "localize"
              ? t(l, "progressLocalize", { i: e.i, n: e.n })
              : e.stage === "terms"
                ? t(l, "progressTerms")
                : t(l, "progressRules"),
        );
      } else if (e.type === "clause") {
        setVerdicts((v) => [...v, e.verdict]);
      } else if (e.type === "partial" || e.type === "done") {
        // Results stream in: money first, then one explained clause at a time.
        setResult(e.result);
        const ready = e.result.cards.filter((c) => !c.pending && c.verdict !== "UNCHECKED");
        const worst = [...ready].sort((a, b) => rank(a.verdict) - rank(b.verdict))[0];
        setSelected((s) => s ?? worst?.clause_id ?? null);
        setStage("results");
        if (e.type === "done") setProgress("");
      } else if (e.type === "error") {
        setError(e.message);
      }
    },
    [],
  );

  const run = async (fn: () => Promise<void>) => {
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const analyze = (s: SessionView, l: Lang = lang) =>
    run(async () => {
      setSession(s);
      setResult(null);
      setSelected(null);
      setVerdicts([]);
      setProgress("");
      setStage("analyzing");
      await api.analyze(s.session_id, l, onEvent(l));
    });

  const onImage = (b: Blob) =>
    run(async () => {
      setStage("reading");
      try {
        const s = await api.scan(b);
        setSession(s);
        setStage("review");
      } catch (e) {
        setStage("capture");
        throw e;
      }
    });

  const onText = (text: string) =>
    run(async () => {
      const s = await api.fromText(text);
      await analyze(s);
    });

  const onSample = (id: string, l: Lang = lang) =>
    run(async () => {
      setStage("reading");
      const s = await api.loadSample(id);
      if (s.image) {
        setSession(s);
        setStage("review");
      } else {
        await analyze(s, l);
      }
    });

  // ?sample=<id>[&lang=en] opens a demo contract directly (handy for rehearsals and screenshots).
  const urlHandled = useRef(false);
  useEffect(() => {
    if (urlHandled.current) return;
    urlHandled.current = true;
    const p = new URLSearchParams(location.search);
    const q = p.get("lang");
    const l: Lang = q === "hi" || q === "en" ? q : "bn";
    setLang(l);
    const id = p.get("sample");
    if (id) onSample(id, l);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const switchLang = (l: Lang) => {
    setLang(l);
    speaker.stop();
    if (session && result && result.lang !== l) {
      run(async () => {
        setProgress("");
        await api.localize(session.session_id, l, onEvent(l));
      });
    }
  };

  const wipe = () =>
    run(async () => {
      speaker.release();
      await api.wipe(session?.session_id);
      setSession(null);
      setResult(null);
      setSelected(null);
      setStage("wiped");
    });

  const recalc = async (terms: Partial<Terms>) => {
    if (!session) return;
    await run(async () => setResult(await api.money(session.session_id, lang, terms)));
  };

  const card = result?.cards.find((c) => c.clause_id === selected) ?? null;
  const jump = (id: number) => {
    setSelected(id);
    document.getElementById("clause-card")?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <div className="min-h-screen">
      <header className="no-print sticky top-0 z-10 border-b border-ink/10 bg-paper/95 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-3 px-4 py-3">
          <div className="mr-auto">
            <h1 className="text-2xl font-black tracking-tight">
              NyayaLens <span className="font-normal text-ink/60">ন্যায়লেন্স</span>
            </h1>
            <p className="text-sm text-ink/70">{t(lang, "appTagline")}</p>
          </div>
          <span className="rounded-full bg-good-soft px-3 py-1 text-sm font-bold text-good">{t(lang, "offlineBadge")}</span>
          <div className="flex overflow-hidden rounded-full border-2 border-ink/20" role="group" aria-label="Language">
            {(Object.keys(LANG_NAMES) as Lang[]).map((l) => (
              <button
                key={l}
                onClick={() => switchLang(l)}
                className={`px-3 py-1 font-bold ${l === lang ? "bg-ink text-white" : "bg-white"}`}
                aria-pressed={l === lang}
              >
                {LANG_NAMES[l]}
              </button>
            ))}
          </div>
          <button
            onClick={() => setBig((v) => !v)}
            aria-pressed={big}
            className={`inline-flex items-center gap-1 rounded-full border-2 px-3 py-1 font-bold ${big ? "border-ink bg-ink text-white" : "border-ink/20 bg-white"}`}
          >
            <Type className="size-4" /> {t(lang, "bigText")}
          </button>
          <button
            onClick={() => {
              setPrev(stage);
              setStage("selfcheck");
            }}
            className="inline-flex items-center gap-1 rounded-full border-2 border-ink/20 bg-white px-3 py-1 font-bold"
          >
            <Activity className="size-4" /> {t(lang, "selfcheck")}
          </button>
          <button
            onClick={wipe}
            className="inline-flex items-center gap-1 rounded-full border-2 border-bad bg-white px-3 py-1 font-bold text-bad"
          >
            <Trash2 className="size-4" /> {t(lang, "wipe")}
          </button>
        </div>
      </header>

      <main className="mx-auto max-w-7xl space-y-5 px-4 py-6">
        <p className="no-print flex items-start gap-2 rounded-xl bg-white p-3 text-ink/80 shadow-sm">
          <Info className="mt-0.5 size-5 shrink-0" /> {t(lang, "notAdvice")}
        </p>

        {error && (
          <p className="no-print rounded-xl bg-bad-soft p-3 font-bold text-bad">
            {t(lang, "error")}: {error}
          </p>
        )}

        {stage === "capture" && <Capture lang={lang} onImage={onImage} onText={onText} onSample={onSample} />}
        {stage === "wiped" && (
          <Panel className="mx-auto max-w-xl space-y-4 text-center">
            <Trash2 className="mx-auto size-12 text-good" />
            <p className="text-xl font-bold">{t(lang, "wiped")}</p>
            <BigButton onClick={() => setStage("capture")}>{t(lang, "startOver")}</BigButton>
          </Panel>
        )}
        {stage === "reading" && <Spinner text={t(lang, "reading")} />}
        {stage === "review" && session && (
          <Review lang={lang} session={session} onConfirm={analyze} onRetake={() => setStage("capture")} />
        )}
        {stage === "analyzing" && (
          <div className="space-y-3">
            <Spinner text={progress || t(lang, "reading")} />
            <div className="flex justify-center gap-2" aria-live="polite">
              {verdicts.map((v, i) => (
                <span key={i} className={`rounded-full p-1 ${VERDICT_STYLE[v].bg}`}>
                  <VerdictIcon v={v} className="size-6" />
                </span>
              ))}
            </div>
          </div>
        )}
        {stage === "selfcheck" && <SelfCheck lang={lang} onBack={() => setStage(prev)} />}
        {stage === "rider" && result && <Rider lang={lang} result={result} onBack={() => setStage("results")} />}

        {stage === "results" && result && session && (
          <>
            {result.engine === "fallback" && (
              <p className="rounded-xl bg-warn-soft p-3 font-bold text-warn">{t(lang, "fallbackEngine")}</p>
            )}
            {progress && (
              <div className="no-print flex items-center gap-3 rounded-xl bg-white p-3 shadow-sm" role="status" aria-live="polite">
                <div className="size-6 shrink-0 animate-spin rounded-full border-4 border-ink/15 border-t-ink" />
                <span className="font-bold">{progress}</span>
              </div>
            )}
            <div className="grid gap-5 lg:grid-cols-2">
              <Summary lang={lang} result={result} speaker={speaker} onJump={jump} />
              <MoneyView
                lang={lang}
                money={result.money}
                moneyError={result.money_error}
                terms={result.terms}
                onRecalc={recalc}
                speaker={speaker}
              />
            </div>

            {result.doc_hits.filter((h) => !h.attached).length > 0 && (
              <Panel className="space-y-2">
                <h3 className="text-xl font-bold">{t(lang, "docWide")}</h3>
                {result.doc_hits
                  .filter((h) => !h.attached)
                  .map((h) => (
                    <p key={h.id} className="flex items-start gap-2">
                      <VerdictIcon v={h.severity} className="mt-1 size-5 shrink-0" />
                      <span>
                        <b>{h.name}.</b> {h.plain}
                      </span>
                    </p>
                  ))}
              </Panel>
            )}

            <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
              <Panel className="lg:sticky lg:top-24">
                <p className="no-print mb-2 text-ink/70">{t(lang, "tapClause")}</p>
                <Heatmap
                  sessionId={session.session_id}
                  size={result.image}
                  cards={result.cards}
                  selected={selected}
                  onSelect={jump}
                  lang={lang}
                />
              </Panel>
              <div id="clause-card" className="scroll-mt-24 space-y-5">
                {card && <ClauseCard key={`${card.clause_id}-${lang}`} card={card} lang={lang} speaker={speaker} />}
                <QAPanel lang={lang} sessionId={session.session_id} cards={result.cards} speaker={speaker} onJump={jump} />
              </div>
            </div>

            <div className="no-print flex flex-wrap gap-3">
              <BigButton onClick={() => setStage("rider")}>
                <FileSignature className="size-5" /> {t(lang, "makeLetter")}
              </BigButton>
              <BigButton variant="secondary" onClick={() => setStage("capture")}>
                <RotateCcw className="size-5" /> {t(lang, "startOver")}
              </BigButton>
            </div>

            <Panel className="space-y-2">
              <h3 className="flex items-center gap-2 text-xl font-bold">
                <LifeBuoy className="size-6" /> {t(lang, "help")}
              </h3>
              <ul className="space-y-1">
                {result.help.map((h) => (
                  <li key={h.id}>
                    <b>{h.name}</b>: {h.contact}
                  </li>
                ))}
              </ul>
              <p className="text-sm text-ink/50">
                {t(lang, "timeTaken")}:{" "}
                {Object.entries(result.timings)
                  .map(([k, v]) => `${k.replace(/_s$/, "")} ${v}s`)
                  .join(" · ")}
              </p>
            </Panel>
            {speaker.error && <p className="text-warn">{t(lang, "noVoice")}</p>}
          </>
        )}
      </main>
    </div>
  );
}

const rank = (v: Verdict) => ({ NOT_OK: 0, CAREFUL: 1, OK: 2, UNCHECKED: 3 })[v];

function Spinner({ text }: { text: string }) {
  return (
    <div className="flex flex-col items-center gap-4 py-12" role="status" aria-live="polite">
      <div className="size-14 animate-spin rounded-full border-8 border-ink/15 border-t-ink" />
      <p className="text-xl font-bold">{text}</p>
    </div>
  );
}
