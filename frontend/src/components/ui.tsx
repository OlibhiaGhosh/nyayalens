import { AlertTriangle, CheckCircle2, CircleDashed, OctagonX, Square, Volume2 } from "lucide-react";
import type { ReactNode } from "react";
import { t, VERDICT_LABEL } from "../i18n";
import type { Lang, Verdict } from "../types";

// Colour is never the only signal: every verdict also has its own icon and label.
export const VERDICT_STYLE: Record<Verdict, { fg: string; bg: string; border: string; hex: string; glyph: string }> = {
  NOT_OK: { fg: "text-bad", bg: "bg-bad-soft", border: "border-bad", hex: "#d92d20", glyph: "✕" },
  CAREFUL: { fg: "text-warn", bg: "bg-warn-soft", border: "border-warn", hex: "#f79009", glyph: "!" },
  OK: { fg: "text-good", bg: "bg-good-soft", border: "border-good", hex: "#17b26a", glyph: "✓" },
  UNCHECKED: { fg: "text-slate-500", bg: "bg-slate-100", border: "border-slate-300", hex: "#98a2b3", glyph: "" },
};

export function VerdictIcon({ v, className = "size-5" }: { v: Verdict; className?: string }) {
  const Icon = { NOT_OK: OctagonX, CAREFUL: AlertTriangle, OK: CheckCircle2, UNCHECKED: CircleDashed }[v];
  return <Icon className={`${className} ${VERDICT_STYLE[v].fg}`} aria-hidden />;
}

export function VerdictBadge({ v, lang }: { v: Verdict; lang: Lang }) {
  const s = VERDICT_STYLE[v];
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 font-bold ${s.bg} ${s.fg} ${s.border}`}>
      <VerdictIcon v={v} />
      {VERDICT_LABEL[v][lang]}
    </span>
  );
}

export function SpeakButton({
  id,
  playing,
  onPlay,
  onStop,
  lang,
  label,
  small,
}: {
  id: string;
  playing: string | null;
  onPlay: () => void;
  onStop: () => void;
  lang: Lang;
  label?: string;
  small?: boolean;
}) {
  const active = playing === id;
  return (
    <button
      type="button"
      onClick={active ? onStop : onPlay}
      className={`no-print inline-flex shrink-0 items-center gap-1.5 rounded-full border-2 font-bold transition ${
        active ? "border-ink bg-ink text-white" : "border-ink/20 bg-white hover:border-ink"
      } ${small ? "px-2.5 py-1 text-sm" : "px-4 py-2"}`}
      aria-label={active ? t(lang, "stop") : label ?? t(lang, "listen")}
    >
      {active ? <Square className="size-4" /> : <Volume2 className="size-5" />}
      {!small && (active ? t(lang, "stop") : label ?? t(lang, "listen"))}
    </button>
  );
}

export function Panel({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`rounded-2xl border border-ink/10 bg-white p-5 shadow-sm ${className}`}>{children}</section>;
}

export function BigButton({
  children,
  onClick,
  disabled,
  variant = "primary",
  type = "button",
}: {
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  variant?: "primary" | "secondary";
  type?: "button" | "submit";
}) {
  const cls =
    variant === "primary"
      ? "bg-ink text-white hover:bg-ink/90"
      : "border-2 border-ink/20 bg-white text-ink hover:border-ink";
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex items-center justify-center gap-2 rounded-xl px-5 py-3 text-lg font-bold transition disabled:opacity-40 ${cls}`}
    >
      {children}
    </button>
  );
}
