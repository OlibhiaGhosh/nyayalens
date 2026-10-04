import { api } from "../api";
import { VERDICT_LABEL } from "../i18n";
import type { Card, Lang } from "../types";
import { VERDICT_STYLE, VerdictIcon } from "./ui";

/** Redacted photo with clickable coloured boxes per clause (colour + glyph, never colour alone). */
export function Heatmap({
  sessionId,
  size,
  cards,
  selected,
  onSelect,
  lang,
}: {
  sessionId: string;
  size: { width: number; height: number } | null;
  cards: Card[];
  selected: number | null;
  onSelect: (id: number) => void;
  lang: Lang;
}) {
  if (!size) return <ClauseList cards={cards} selected={selected} onSelect={onSelect} lang={lang} />;
  const r = Math.max(14, size.width * 0.016);
  return (
    <div className="relative">
      <img src={api.imageUrl(sessionId, "redacted")} alt="" className="block w-full rounded-lg" />
      <svg
        viewBox={`0 0 ${size.width} ${size.height}`}
        className="absolute inset-0 size-full"
        preserveAspectRatio="none"
        role="list"
      >
        {cards
          .filter((c) => c.box && c.verdict !== "UNCHECKED")
          .map((c) => {
            const s = VERDICT_STYLE[c.verdict];
            const isSel = c.clause_id === selected;
            const [x, y] = c.box!;
            return (
              <g
                key={c.clause_id}
                role="listitem"
                tabIndex={0}
                aria-label={`${c.label} ${VERDICT_LABEL[c.verdict][lang]}`}
                onClick={() => onSelect(c.clause_id)}
                onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && onSelect(c.clause_id)}
                className="cursor-pointer outline-none"
              >
                {(c.line_boxes.length ? c.line_boxes : [c.box!]).map(([bx, by, bw, bh], i) => (
                  <rect
                    key={i}
                    x={bx - 6}
                    y={by - 4}
                    width={bw + 12}
                    height={bh + 8}
                    fill={s.hex}
                    fillOpacity={isSel ? 0.35 : 0.2}
                    stroke={s.hex}
                    strokeWidth={isSel ? 5 : 0}
                    rx={4}
                  />
                ))}
                <circle cx={Math.max(r + 2, x - r - 8)} cy={y + r} r={r} fill={s.hex} stroke="white" strokeWidth={3} />
                <text
                  x={Math.max(r + 2, x - r - 8)}
                  y={y + r}
                  textAnchor="middle"
                  dominantBaseline="central"
                  fontSize={r * 1.25}
                  fontWeight="bold"
                  fill="white"
                >
                  {s.glyph}
                </text>
              </g>
            );
          })}
      </svg>
    </div>
  );
}

function ClauseList({
  cards,
  selected,
  onSelect,
  lang,
}: {
  cards: Card[];
  selected: number | null;
  onSelect: (id: number) => void;
  lang: Lang;
}) {
  return (
    <ol className="space-y-2">
      {cards.map((c) => {
        const s = VERDICT_STYLE[c.verdict];
        return (
          <li key={c.clause_id}>
            <button
              onClick={() => onSelect(c.clause_id)}
              className={`flex w-full items-start gap-2 rounded-lg border-l-8 p-3 text-left ${s.bg} ${s.border} ${
                c.clause_id === selected ? "ring-4 ring-ink/30" : ""
              }`}
            >
              {c.pending ? (
                <span className="mt-0.5 size-5 shrink-0 animate-spin rounded-full border-4 border-ink/15 border-t-ink" />
              ) : (
                <VerdictIcon v={c.verdict} className="mt-0.5 size-5 shrink-0" />
              )}
              <span className="sr-only">{VERDICT_LABEL[c.verdict][lang]}</span>
              {/* original_text already starts with its own number ("1.", "১।") */}
              <span className="line-clamp-3">{c.original_text}</span>
            </button>
          </li>
        );
      })}
    </ol>
  );
}
