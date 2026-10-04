import { CheckCircle2, CircleX, RefreshCw, WifiOff } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";
import type { Lang } from "../types";
import { BigButton, Panel } from "./ui";

/** Offline self-check: every dependency is local and the network is off. */
export function SelfCheck({ onBack }: { lang: Lang; onBack: () => void }) {
  const [data, setData] = useState<Record<string, any> | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const load = (probe = false) =>
    api
      .selfcheck(probe)
      .then(setData)
      .catch((e) => setErr(String(e)));
  useEffect(() => {
    load();
  }, []);

  const o = data?.ollama;
  const ts = data?.tesseract;
  const tts = data?.tts;
  const rows: [string, boolean, string][] = data
    ? [
        ["Ollama running", !!o?.running, o?.error ?? "127.0.0.1:11434"],
        [`Model ${o?.model}`, !!o?.model_present, (o?.installed ?? []).join(", ")],
        ["Tesseract OCR", !!ts?.available, ts?.version ?? ts?.error ?? ""],
        ["OCR languages (ben, hin, eng)", !!ts?.available && !(ts?.missing ?? []).length, ts?.missing?.length ? `missing: ${ts.missing.join(", ")}` : (ts?.langs ?? []).join(", ")],
        ["Piper TTS library", !!tts?.piper_installed, ""],
        ...Object.entries(tts?.voices ?? {}).map(
          ([lang, v]: [string, any]) => [`Voice ${lang}: ${v.name}`, !!v.present, ""] as [string, boolean, string],
        ),
        ["HF_HUB_OFFLINE=1", data.offline_env?.HF_HUB_OFFLINE === "1", ""],
        ["Fonts & icons bundled (no CDN)", true, "Noto Sans Bengali / Devanagari from npm"],
        ["Page origin", location.hostname === "127.0.0.1" || location.hostname === "localhost", location.origin],
      ]
    : [];

  return (
    <Panel className="space-y-4">
      <h2 className="text-2xl font-bold">Offline self-check</h2>
      {err && <p className="text-bad">{err}</p>}
      <ul className="grid gap-x-10 lg:grid-cols-2">
        {rows.map(([name, ok, detail]) => (
          <li key={name} className="flex items-start gap-3 border-b border-ink/10 py-2">
            {ok ? <CheckCircle2 className="size-6 shrink-0 text-good" /> : <CircleX className="size-6 shrink-0 text-bad" />}
            <div>
              <div className="font-bold">{name}</div>
              {detail && <div className="text-sm break-all text-ink/60">{detail}</div>}
            </div>
          </li>
        ))}
        {data?.internet && (
          <li className="flex items-center gap-3 py-2">
            {data.internet === "unreachable" ? (
              <CheckCircle2 className="size-6 text-good" />
            ) : (
              <CircleX className="size-6 text-warn" />
            )}
            <b>Internet: {data.internet}</b>
          </li>
        )}
      </ul>
      <div className="flex flex-wrap gap-3">
        <BigButton variant="secondary" onClick={() => load(true)}>
          <WifiOff className="size-5" /> Check internet is off
        </BigButton>
        <BigButton variant="secondary" onClick={() => load()}>
          <RefreshCw className="size-5" /> Refresh
        </BigButton>
        <BigButton onClick={onBack}>Back</BigButton>
      </div>
    </Panel>
  );
}
