import {
  ArrowRight,
  Camera,
  ChevronDown,
  FileText,
  ImageUp,
  X,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { LANG_NAMES, t } from "../i18n";
import type { Lang } from "../types";
import { BigButton, Panel } from "./ui";

export type CaptureMode = "choose" | "camera" | "text";

const ACRONYMS = new Set(["mfi", "nbfc", "emi"]);

/** "04_vehicle_loan_en" -> "Vehicle loan" (the language is shown separately). */
function sampleTitle(id: string, lang: string) {
  const words = id
    .replace(/^\d+_/, "")
    .replace(new RegExp(`_${lang}$`), "")
    .split("_");
  const title = words
    .map((w) => (ACRONYMS.has(w) ? w.toUpperCase() : w))
    .join(" ");
  return title.charAt(0).toUpperCase() + title.slice(1);
}

export function Capture({
  lang,
  onImage,
  onText,
  onSample,
  onModeChange,
}: {
  lang: Lang;
  onImage: (b: Blob) => void;
  onText: (s: string) => void;
  onSample: (id: string) => void;
  onModeChange?: (m: CaptureMode) => void;
}) {
  const [mode, setMode] = useState<CaptureMode>("choose");
  useEffect(() => onModeChange?.(mode), [mode, onModeChange]);
  const [text, setText] = useState("");
  const [samples, setSamples] = useState<
    { id: string; lang: string; photo: boolean }[]
  >([]);
  const fileRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    api
      .samples()
      .then(setSamples)
      .catch(() => setSamples([]));
  }, []);

  if (mode === "camera")
    return (
      <Webcam
        lang={lang}
        onCapture={onImage}
        onCancel={() => setMode("choose")}
      />
    );
  if (mode === "text")
    return (
      <Panel className="space-y-3">
        <h2 className="flex items-center gap-2 text-2xl font-bold">
          <FileText className="size-7" /> {t(lang, "pasteText")}
        </h2>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={16}
          autoFocus
          className="w-full rounded-xl border border-ink/20 p-3 font-mono text-base"
          placeholder={"1. ...\n2. ..."}
        />
        <div className="flex flex-wrap gap-3">
          <BigButton
            onClick={() => onText(text)}
            disabled={text.trim().length < 20}
          >
            {t(lang, "checkMyPaper")}
          </BigButton>
          <BigButton variant="secondary" onClick={() => setMode("choose")}>
            {t(lang, "cancel")}
          </BigButton>
        </div>
      </Panel>
    );

  return (
    <div className="my-auto space-y-10 py-6 md:py-10">
      <div className="space-y-4 text-center">
        <h1 className="font-display text-6xl leading-tight font-semibold tracking-tight md:text-7xl lg:text-8xl">
          NyayLens
        </h1>
        <p className="mx-auto max-w-2xl text-lg text-ink/70 md:text-xl">
          {t(lang, "appTagline")}
        </p>
      </div>

      <div className="grid gap-5 md:grid-cols-3 lg:gap-8">
        <ActionCard
          primary
          icon={Camera}
          title={t(lang, "takePhoto")}
          hint={t(lang, "takePhotoHint")}
          onClick={() => setMode("camera")}
        />
        <ActionCard
          icon={ImageUp}
          title={t(lang, "uploadPhoto")}
          hint={t(lang, "uploadPhotoHint")}
          onClick={() => fileRef.current?.click()}
        />
        <ActionCard
          icon={FileText}
          title={t(lang, "pasteText")}
          hint={t(lang, "pasteTextHint")}
          onClick={() => setMode("text")}
        />
        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) onImage(f);
            e.target.value = "";
          }}
        />
      </div>

      {samples.length > 0 && (
        <details className="group text-center text-sm">
          <summary className="inline-flex cursor-pointer list-none items-center gap-1 rounded-full px-3 py-1 text-ink/60 hover:text-ink [&::-webkit-details-marker]:hidden">
            {t(lang, "samplesTitle")}
            <ChevronDown
              className="size-4 transition group-open:rotate-180"
              aria-hidden
            />
          </summary>
          <div className="mt-3 flex flex-wrap justify-center gap-2">
            {samples.map((s) => (
              <button
                key={s.id}
                onClick={() => onSample(s.id)}
                className="rounded-full border border-ink/15 bg-white px-3 py-1 hover:border-ink"
              >
                {sampleTitle(s.id, s.lang)} ·{" "}
                {LANG_NAMES[s.lang as Lang] ?? s.lang}
              </button>
            ))}
          </div>
        </details>
      )}
    </div>
  );
}

function ActionCard({
  icon: Icon,
  title,
  hint,
  onClick,
  primary,
}: {
  icon: typeof Camera;
  title: string;
  hint: string;
  onClick: () => void;
  primary?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      className={`group flex items-center gap-4 rounded-3xl border-2 p-5 text-left shadow-sm transition hover:-translate-y-0.5 hover:shadow-md md:min-h-72 md:flex-col md:justify-start md:gap-5 md:p-8 md:pt-12 md:text-center ${
        primary
          ? "border-ink bg-ink text-white"
          : "border-ink/15 bg-white hover:border-ink"
      }`}
    >
      <span
        className={`flex size-12 shrink-0 items-center justify-center rounded-2xl md:size-20 ${primary ? "bg-white/15" : "bg-paper"}`}
      >
        <Icon className="size-7 md:size-10" aria-hidden />
      </span>
      <span className="space-y-1.5">
        <span className="flex items-center gap-2 text-xl font-bold md:justify-center md:text-2xl">
          {title}
          <ArrowRight
            className="size-5 shrink-0 transition group-hover:translate-x-1"
            aria-hidden
          />
        </span>
        <span
          className={`block md:mx-auto md:max-w-64 ${primary ? "text-white/80" : "text-ink/70"}`}
        >
          {hint}
        </span>
      </span>
    </button>
  );
}

function Webcam({
  lang,
  onCapture,
  onCancel,
}: {
  lang: Lang;
  onCapture: (b: Blob) => void;
  onCancel: () => void;
}) {
  const video = useRef<HTMLVideoElement>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let stream: MediaStream | null = null;
    navigator.mediaDevices
      ?.getUserMedia({
        video: {
          facingMode: "environment",
          width: { ideal: 2560 },
          height: { ideal: 1440 },
        },
      })
      .then((s) => {
        stream = s;
        if (video.current) video.current.srcObject = s;
      })
      .catch((e) => setErr(String(e)));
    return () => stream?.getTracks().forEach((tr) => tr.stop());
  }, []);

  const snap = () => {
    const v = video.current;
    if (!v || !v.videoWidth) return;
    const c = document.createElement("canvas");
    c.width = v.videoWidth;
    c.height = v.videoHeight;
    c.getContext("2d")!.drawImage(v, 0, 0);
    c.toBlob((b) => b && onCapture(b), "image/jpeg", 0.95);
  };

  return (
    <Panel className="space-y-3">
      {err ? (
        <p className="text-bad">{err}</p>
      ) : (
        <video
          ref={video}
          autoPlay
          playsInline
          muted
          className="mx-auto max-h-[65vh] w-full rounded-xl bg-black object-contain"
        />
      )}
      <div className="flex gap-3">
        <BigButton onClick={snap} disabled={!!err}>
          <Camera className="size-6" /> {t(lang, "capture")}
        </BigButton>
        <BigButton variant="secondary" onClick={onCancel}>
          <X className="size-5" /> {t(lang, "cancel")}
        </BigButton>
      </div>
    </Panel>
  );
}
