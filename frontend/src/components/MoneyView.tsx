import { Calculator, IndianRupee } from "lucide-react";
import { useState } from "react";
import { pct, rupees, stepText, t } from "../i18n";
import type { Lang, Money, Terms } from "../types";
import { BigButton, Panel, SpeakButton } from "./ui";

type Speaker = { speak: (id: string, texts: string[], lang: Lang) => void; stop: () => void; playing: string | null };

/** Rupees first ("you get / you pay back / extra"), APR second, with the code's steps. */
export function MoneyView({
  lang,
  money,
  moneyError,
  terms,
  onRecalc,
  speaker,
}: {
  lang: Lang;
  money: Money | null;
  moneyError: string | null;
  terms: Terms | null;
  onRecalc: (t: Partial<Terms>) => Promise<void>;
  speaker: Speaker;
}) {
  const [steps, setSteps] = useState(false);
  const [editing, setEditing] = useState(!money && !!moneyError?.startsWith("missing"));

  if (terms?.doc_type === "rental") {
    return (
      <Panel className="space-y-2">
        <h3 className="flex items-center gap-2 text-xl font-bold">
          <IndianRupee className="size-6" /> {t(lang, "moneyTitle")}
        </h3>
        <dl className="grid grid-cols-2 gap-2 text-lg">
          {terms.monthly_rent != null && (
            <>
              <dt>Rent / month</dt>
              <dd className="font-bold">{rupees(terms.monthly_rent)}</dd>
            </>
          )}
          {terms.security_deposit != null && (
            <>
              <dt>Deposit</dt>
              <dd className="font-bold">{rupees(terms.security_deposit)}</dd>
            </>
          )}
        </dl>
      </Panel>
    );
  }

  const spoken = money
    ? [
        `${t(lang, "youGet")} ${rupees(money.cash_in_hand)}.`,
        `${t(lang, "youPay")} ${rupees(money.total_repayment)}.`,
        `${t(lang, "extra")} ${rupees(money.extra_cost)}.`,
      ]
    : [];

  return (
    <Panel className="space-y-4">
      <div className="flex items-center justify-between gap-2">
        <h3 className="flex items-center gap-2 text-xl font-bold">
          <IndianRupee className="size-6" /> {t(lang, "moneyTitle")}
        </h3>
        {money && (
          <SpeakButton
            id="money"
            lang={lang}
            playing={speaker.playing}
            onPlay={() => speaker.speak("money", spoken, lang)}
            onStop={speaker.stop}
          />
        )}
      </div>

      {money ? (
        <>
          <div className="grid grid-cols-3 gap-2 text-center">
            <Stat label={t(lang, "youGet")} value={rupees(money.cash_in_hand)} />
            <Stat label={t(lang, "youPay")} value={rupees(money.total_repayment)} />
            <Stat label={t(lang, "extra")} value={rupees(money.extra_cost)} strong />
          </div>
          <div className="flex flex-wrap items-baseline gap-x-6 gap-y-1 text-lg">
            <span>
              {t(lang, "aprLine")}: <b className="text-2xl">{pct(money.apr_pct)}</b> {t(lang, "perYear")}
            </span>
            {money.stated_annual_pct != null && (
              <span className="text-ink/70">
                {t(lang, "paperSays")}: <b>{pct(money.stated_annual_pct)}</b> {t(lang, "perYear")}
              </span>
            )}
          </div>
          <button onClick={() => setSteps((v) => !v)} className="flex items-center gap-2 font-bold underline underline-offset-4">
            <Calculator className="size-5" /> {t(lang, "showSteps")}
          </button>
          {steps && (
            <ol className="list-decimal space-y-1 rounded-lg bg-paper p-3 pl-8">
              {money.steps.map((s, i) => (
                <li key={i}>{stepText(s, lang)}</li>
              ))}
            </ol>
          )}
          <p className="text-sm text-ink/60">{t(lang, "verifiedByCode")}</p>
        </>
      ) : (
        <p className="rounded-lg bg-warn-soft p-3">{t(lang, "moneyMissing")}</p>
      )}

      <button onClick={() => setEditing((v) => !v)} className="text-sm underline underline-offset-4">
        {t(lang, "fixNumbers")}
      </button>
      {editing && <TermsForm lang={lang} terms={terms} onSubmit={onRecalc} />}
    </Panel>
  );
}

function Stat({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className={`rounded-xl p-3 ${strong ? "bg-bad-soft text-bad" : "bg-paper"}`}>
      <div className="text-sm">{label}</div>
      <div className="text-2xl font-bold">{value}</div>
    </div>
  );
}

const FIELDS: { key: keyof Terms; label: string; kind: "num" | "freq" | "period" | "type" }[] = [
  { key: "principal", label: "Loan amount ₹", kind: "num" },
  { key: "upfront_fees", label: "Fees at start ₹", kind: "num" },
  { key: "installment", label: "Each installment ₹", kind: "num" },
  { key: "num_installments", label: "Number of installments", kind: "num" },
  { key: "frequency", label: "How often", kind: "freq" },
  { key: "stated_rate_pct", label: "Rate on paper %", kind: "num" },
  { key: "stated_rate_period", label: "Rate per", kind: "period" },
  { key: "rate_type", label: "Flat / reducing", kind: "type" },
];

function TermsForm({ lang, terms, onSubmit }: { lang: Lang; terms: Terms | null; onSubmit: (t: Partial<Terms>) => Promise<void> }) {
  const [v, setV] = useState<Record<string, string>>(() =>
    Object.fromEntries(FIELDS.map((f) => [f.key, terms?.[f.key] == null ? "" : String(terms[f.key])])),
  );
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    setBusy(true);
    const out: Record<string, unknown> = {};
    for (const f of FIELDS) {
      const raw = v[f.key];
      out[f.key] = f.kind === "num" ? (raw === "" ? null : Number(raw)) : raw || null;
    }
    try {
      await onSubmit(out as Partial<Terms>);
    } finally {
      setBusy(false);
    }
  };
  const opts = {
    freq: ["daily", "weekly", "fortnightly", "monthly", "quarterly", "yearly"],
    period: ["year", "month", "week", "day"],
    type: ["flat", "reducing", "unknown"],
  };
  return (
    <div className="grid gap-2 sm:grid-cols-2">
      {FIELDS.map((f) => (
        <label key={f.key} className="flex flex-col text-sm">
          {f.label}
          {f.kind === "num" ? (
            <input
              type="number"
              inputMode="decimal"
              value={v[f.key]}
              onChange={(e) => setV({ ...v, [f.key]: e.target.value })}
              className="rounded-md border border-ink/20 px-2 py-1.5 text-lg"
            />
          ) : (
            <select
              value={v[f.key]}
              onChange={(e) => setV({ ...v, [f.key]: e.target.value })}
              className="rounded-md border border-ink/20 px-2 py-1.5 text-lg"
            >
              <option value="">—</option>
              {opts[f.kind].map((o) => (
                <option key={o}>{o}</option>
              ))}
            </select>
          )}
        </label>
      ))}
      <div className="sm:col-span-2">
        <BigButton onClick={submit} disabled={busy}>
          {t(lang, "recalc")}
        </BigButton>
      </div>
    </div>
  );
}
