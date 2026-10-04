import { ArrowLeft, Copy, Printer } from "lucide-react";
import { useMemo, useState } from "react";
import { t } from "../i18n";
import type { Lang, Result } from "../types";
import { BigButton } from "./ui";

/**
 * Counter-rider letter. The formal English text comes from the curated rule list
 * (not generated), one item per flagged clause; the local-language section
 * explains what each item asks for. Print-to-PDF uses the browser, which shapes
 * Bengali conjuncts correctly with the bundled Noto fonts.
 */
export function Rider({ lang, result, onBack }: { lang: Lang; result: Result; onBack: () => void }) {
  const [copied, setCopied] = useState(false);

  const items = useMemo(() => {
    const out: { ref: string; text: string; ask?: string }[] = [];
    const seen = new Set<string>();
    for (const c of result.cards) {
      if (c.verdict !== "NOT_OK" && c.verdict !== "CAREFUL") continue;
      for (const r of c.riders_en ?? []) {
        if (seen.has(r)) continue;
        seen.add(r);
        out.push({ ref: `Clause ${c.label || c.clause_id}`, text: r, ask: c.ask_to_change });
      }
    }
    for (const h of result.doc_hits) {
      if (!seen.has(h.rider_en)) {
        seen.add(h.rider_en);
        out.push({ ref: "General", text: h.rider_en, ask: h.ask_to_change });
      }
    }
    return out;
  }, [result]);

  const today = new Date().toLocaleDateString("en-IN");
  const english = [
    "RIDER TO THE AGREEMENT",
    "",
    `Date: ${today}`,
    "Between: ______________________ (Lender / Landlord)",
    "And: ______________________ (Borrower / Tenant)",
    "",
    "Notwithstanding anything to the contrary in the Agreement, the parties agree as follows:",
    "",
    ...items.map((it, i) => `${i + 1}. (${it.ref}) ${it.text}`),
    "",
    "This rider forms part of the Agreement and prevails over any inconsistent term.",
    "",
    "Signature (Lender / Landlord): ____________        Signature (Borrower / Tenant): ____________",
  ].join("\n");

  const copy = async () => {
    await navigator.clipboard.writeText(english);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-4">
      <div className="no-print flex flex-wrap gap-3">
        <BigButton variant="secondary" onClick={onBack}>
          <ArrowLeft className="size-5" /> {t(lang, "back")}
        </BigButton>
        <BigButton variant="secondary" onClick={copy}>
          <Copy className="size-5" /> {copied ? t(lang, "copied") : t(lang, "copy")}
        </BigButton>
        <BigButton onClick={() => window.print()}>
          <Printer className="size-5" /> {t(lang, "print")}
        </BigButton>
      </div>

      <article className="print-page mx-auto max-w-3xl space-y-4 rounded-2xl border border-ink/10 bg-white p-10 font-serif shadow-sm">
        <h1 className="text-center text-2xl font-bold tracking-wide">RIDER TO THE AGREEMENT</h1>
        <p>Date: {today}</p>
        <p>Between: ______________________ (Lender / Landlord)</p>
        <p>And: ______________________ (Borrower / Tenant)</p>
        <p>Notwithstanding anything to the contrary in the Agreement, the parties agree as follows:</p>
        <ol className="list-decimal space-y-3 pl-6">
          {items.map((it, i) => (
            <li key={i}>
              <b>({it.ref})</b> {it.text}
            </li>
          ))}
        </ol>
        <p>This rider forms part of the Agreement and prevails over any inconsistent term.</p>
        <div className="grid grid-cols-2 gap-8 pt-10">
          <p className="border-t border-ink pt-1">Lender / Landlord</p>
          <p className="border-t border-ink pt-1">Borrower / Tenant</p>
        </div>

        {lang !== "en" && (
          <section className="mt-8 border-t-2 border-dashed border-ink/30 pt-4 font-sans">
            <h2 className="mb-2 text-xl font-bold">{t(lang, "letterExplain")}</h2>
            <ol className="list-decimal space-y-2 pl-6 text-lg">
              {items.map((it, i) => (
                <li key={i}>{it.ask}</li>
              ))}
            </ol>
          </section>
        )}
        <p className="pt-6 font-sans text-sm text-ink/60">{t(lang, "notAdvice")}</p>
      </article>
    </div>
  );
}
