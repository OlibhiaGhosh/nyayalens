import { FileSignature, Info, LifeBuoy, RotateCcw, Trash2, Type, WifiOff } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import { Capture, type CaptureMode } from "./components/Capture";
import { ClauseCard } from "./components/ClauseCard";
import { Heatmap } from "./components/Heatmap";
import { Logo } from "./components/Logo";
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
  const [captureMode, setCaptureMode] = useState<CaptureMode>("choose");
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

  // Landing = the capture screen's three choices (not the camera or text editor inside it).
  const landing = stage === "capture" && captureMode === "choose";
  const card = result?.cards.find((c) => c.clause_id === selected) ?? null;
  const jump = (id: number) => {
    setSelected(id);
    document.getElementById("clause-card")?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <div className="flex min-h-screen flex-col">
      <header
        className={`no-print sticky top-0 z-10 bg-paper/95 backdrop-blur ${landing ? "" : "border-b border-ink/10"}`}
      >
        {/* Strict left / centre / right: equal outer columns keep the languages at the exact page centre.
            Below xl (or with big text) it becomes two rows (logo + tools, then languages), the same on every page. */}
        <nav
          className={`mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-x-4 gap-y-3 px-4 py-3 ${
            big ? "" : "xl:grid xl:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)]"
          }`}
        >
          <button
            onClick={() => setStage("capture")}
            className="flex min-w-0 items-center gap-2.5 justify-self-start rounded-xl text-left"
            aria-label={t(lang, "startOver")}
          >
            <Logo className="size-10 shrink-0" />
            {!landing && <span className="truncate font-display text-2xl font-semibold tracking-tight">NyayLens</span>}
          </button>

          <div
            className={`order-last flex w-full justify-center gap-2 ${big ? "" : "xl:order-none xl:w-auto"}`}
            role="group"
            aria-label="Language"
          >
            {(Object.keys(LANG_NAMES) as Lang[]).map((l) => (
              <button
                key={l}
                onClick={() => switchLang(l)}
                aria-pressed={l === lang}
                className={`min-w-20 whitespace-nowrap rounded-full border-2 px-3 py-1 font-bold transition ${
                  l === lang ? "border-ink bg-ink text-white" : "border-ink/20 bg-white hover:border-ink"
                }`}
              >
                {LANG_NAMES[l]}
              </button>
            ))}
          </div>

          <div className="flex items-center justify-end gap-2 justify-self-end">
            <button
              onClick={() => setBig((v) => !v)}
              aria-pressed={big}
              title={t(lang, "bigText")}
              className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border-2 px-2.5 py-1.5 text-sm font-bold transition sm:px-3 sm:py-1 ${big ? "border-ink bg-ink text-white" : "border-ink/20 bg-white hover:border-ink"}`}
            >
              <Type className="size-4" aria-hidden />
              <span className="sr-only sm:not-sr-only">{t(lang, "bigText")}</span>
            </button>
            <button
              onClick={() => {
                setPrev(stage);
                setStage("selfcheck");
              }}
              title={t(lang, "selfcheck")}
              className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border-2 px-2.5 py-1.5 text-sm font-bold transition sm:px-3 sm:py-1 border-good-soft bg-good-soft text-good hover:border-good"
            >
              <WifiOff className="size-4" aria-hidden />
              <span className="sr-only sm:not-sr-only">{t(lang, "offlineBadge")}</span>
            </button>
            {/* Wiping only makes sense once a paper has been opened. */}
            {!landing && (
              <>
                <span className="mx-1 hidden h-6 w-px bg-ink/15 sm:block" aria-hidden />
                <button
                  onClick={wipe}
                  title={t(lang, "wipe")}
                  className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border-2 px-2.5 py-1.5 text-sm font-bold transition sm:px-3 sm:py-1 border-bad bg-white text-bad hover:bg-bad-soft"
                >
                  <Trash2 className="size-4" aria-hidden />
                  <span className="sr-only sm:not-sr-only">{t(lang, "wipe")}</span>
                </button>
              </>
            )}
          </div>
        </nav>
      </header>

      <main className="mx-auto flex w-full max-w-7xl flex-1 flex-col gap-5 px-4 py-6">

        {error && (
          <p className="no-print rounded-xl bg-bad-soft p-3 font-bold text-bad">
            {t(lang, "error")}: {error}
          </p>
        )}

        {stage === "capture" && <Capture lang={lang} onImage={onImage} onText={onText} onSample={onSample} onModeChange={setCaptureMode} />}
        {stage === "wiped" && (
          <Panel className="space-y-4 py-12 text-center">
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

      <footer className="no-print mx-auto w-full max-w-7xl px-4 pb-6">
        <p className="mx-auto flex max-w-4xl items-start justify-center gap-2 rounded-xl bg-white px-4 py-3 text-sm text-ink/70 shadow-sm">
          <Info className="mt-0.5 size-4 shrink-0" aria-hidden /> {t(lang, "notAdvice")}
        </p>
      </footer>
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
