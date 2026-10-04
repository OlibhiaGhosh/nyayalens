import { AlertTriangle, Eye, EyeOff, RotateCcw, ShieldCheck } from "lucide-react";
import { useMemo, useState } from "react";
import { api } from "../api";
import { t, type Key } from "../i18n";
import type { Lang, SessionView } from "../types";
import { BigButton, Panel } from "./ui";

/** Stage 3 result + "Is this what your paper says?" correction screen. */
export function Review({
  lang,
  session,
  onConfirm,
  onRetake,
}: {
  lang: Lang;
  session: SessionView;
  onConfirm: (s: SessionView) => void;
  onRetake: () => void;
}) {
  const [showOriginal, setShowOriginal] = useState(false);
  const [ignoreQuality, setIgnoreQuality] = useState(false);
  const [lines, setLines] = useState(() => session.lines.map((l) => l.text));
  const [busy, setBusy] = useState(false);
  const edited = useMemo(() => lines.some((l, i) => l !== session.lines[i]?.text), [lines, session.lines]);
  const lowCount = session.lines.filter((l) => l.low_conf).length;
  const q = session.quality;

  const confirm = async () => {
    setBusy(true);
    try {
      // Keep emptied lines as "." so line count, and therefore heatmap boxes, stay aligned.
      const s = edited ? await api.correctText(session.session_id, lines.map((l) => l.trim() || ".").join("\n")) : session;
      onConfirm(s);
    } finally {
      setBusy(false);
    }
  };

  if (q?.retake && !ignoreQuality) {
    return (
      <Panel className="space-y-4">
        <h2 className="flex items-center gap-2 text-2xl font-bold text-warn">
          <AlertTriangle className="size-7" /> {t(lang, "retakeTitle")}
        </h2>
        <ul className="list-disc space-y-1 pl-6 text-lg">
          {q.issues.map((i) => (
            <li key={i}>{t(lang, i as Key)}</li>
          ))}
        </ul>
        <div className="flex flex-wrap gap-3">
          <BigButton onClick={onRetake}>
            <RotateCcw className="size-5" /> {t(lang, "retake")}
          </BigButton>
          <BigButton variant="secondary" onClick={() => setIgnoreQuality(true)}>
            {t(lang, "continueAnyway")}
          </BigButton>
        </div>
      </Panel>
    );
  }

  const piiEntries = Object.entries(session.pii_counts);
  return (
    <div className="grid gap-5 lg:grid-cols-2">
      {session.image && (
        <Panel className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            {piiEntries.length > 0 ? (
              <p className="flex items-center gap-2 font-bold text-good">
                <ShieldCheck className="size-6" />
                {t(lang, "hiddenInfo")}:{" "}
                {piiEntries.map(([k, n]) => `${n} ${t(lang, k as Key)}`).join(", ")}
              </p>
            ) : (
              <span />
            )}
            <button
              onClick={() => setShowOriginal((v) => !v)}
              className="inline-flex items-center gap-1.5 rounded-full border-2 border-ink/20 px-3 py-1 text-sm font-bold hover:border-ink"
            >
              {showOriginal ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
              {showOriginal ? t(lang, "showHidden") : t(lang, "showOriginal")}
            </button>
          </div>
          <img
            src={api.imageUrl(session.session_id, showOriginal ? "original" : "redacted")}
            alt=""
            className="w-full rounded-lg border border-ink/10"
          />
        </Panel>
      )}
      <Panel className={`space-y-3 ${session.image ? "" : "lg:col-span-2"}`}>
        <h2 className="text-2xl font-bold">{t(lang, "checkTitle")}</h2>
        <p className="text-ink/70">{t(lang, "checkHelp")}</p>
        {lowCount > 0 && (
          <p className="flex items-center gap-2 rounded-lg bg-warn-soft p-2 font-bold text-warn">
            <AlertTriangle className="size-5" /> {t(lang, "lowConfWarn")}
          </p>
        )}
        <div className="max-h-[60vh] space-y-1 overflow-y-auto pr-1">
          {lines.map((text, i) => (
            <textarea
              key={i}
              value={text}
              rows={Math.max(1, Math.ceil(text.length / 55))}
              onChange={(e) => setLines((ls) => ls.map((l, j) => (j === i ? e.target.value.replace(/\n/g, " ") : l)))}
              className={`block w-full resize-none rounded-md border px-2 py-1 ${
                session.lines[i]?.low_conf ? "border-warn bg-warn-soft" : "border-ink/10"
              }`}
            />
          ))}
        </div>
        <BigButton onClick={confirm} disabled={busy}>
          {t(lang, "checkMyPaper")}
        </BigButton>
      </Panel>
    </div>
  );
}
