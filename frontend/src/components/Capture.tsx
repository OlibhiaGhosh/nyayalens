import { Camera, FileText, ImageUp, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { t } from "../i18n";
import type { Lang } from "../types";
import { BigButton, Panel } from "./ui";

export function Capture({
  lang,
  onImage,
  onText,
  onSample,
}: {
  lang: Lang;
  onImage: (b: Blob) => void;
  onText: (s: string) => void;
  onSample: (id: string) => void;
}) {
  const [mode, setMode] = useState<"choose" | "camera" | "text">("choose");
  const [text, setText] = useState("");
  const [samples, setSamples] = useState<{ id: string; lang: string }[]>([]);
  const fileRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    api.samples().then(setSamples).catch(() => setSamples([]));
  }, []);

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      {mode === "choose" && (
        <div className="grid gap-4 sm:grid-cols-2">
          <button
            onClick={() => setMode("camera")}
            className="flex flex-col items-center gap-3 rounded-2xl border-2 border-ink/15 bg-white p-8 text-xl font-bold shadow-sm hover:border-ink"
          >
            <Camera className="size-14" />
            {t(lang, "takePhoto")}
          </button>
          <button
            onClick={() => fileRef.current?.click()}
            className="flex flex-col items-center gap-3 rounded-2xl border-2 border-ink/15 bg-white p-8 text-xl font-bold shadow-sm hover:border-ink"
          >
            <ImageUp className="size-14" />
            {t(lang, "uploadPhoto")}
          </button>
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
          <button
            onClick={() => setMode("text")}
            className="col-span-full flex items-center justify-center gap-2 rounded-xl p-3 text-ink/70 underline-offset-4 hover:underline"
          >
            <FileText className="size-5" />
            {t(lang, "pasteText")}
          </button>
          {samples.length > 0 && (
            <div className="col-span-full space-y-2 text-center">
              <p className="text-sm text-ink/60">{t(lang, "trySample")}</p>
              <div className="flex flex-wrap justify-center gap-2">
                {samples.map((s) => (
                  <button
                    key={s.id}
                    onClick={() => onSample(s.id)}
                    className="rounded-full border border-ink/20 bg-white px-3 py-1 text-sm hover:border-ink"
                  >
                    {s.id.replace(/^\d+_/, "").replaceAll("_", " ")}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
      {mode === "camera" && <Webcam lang={lang} onCapture={onImage} onCancel={() => setMode("choose")} />}
      {mode === "text" && (
        <Panel className="space-y-3">
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={14}
            className="w-full rounded-xl border border-ink/20 p-3 font-mono text-base"
            placeholder={"1. ...\n2. ..."}
          />
          <div className="flex gap-3">
            <BigButton onClick={() => onText(text)} disabled={text.trim().length < 20}>
              {t(lang, "checkMyPaper")}
            </BigButton>
            <BigButton variant="secondary" onClick={() => setMode("choose")}>
              {t(lang, "cancel")}
            </BigButton>
          </div>
        </Panel>
      )}
    </div>
  );
}

function Webcam({ lang, onCapture, onCancel }: { lang: Lang; onCapture: (b: Blob) => void; onCancel: () => void }) {
  const video = useRef<HTMLVideoElement>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let stream: MediaStream | null = null;
    navigator.mediaDevices
      ?.getUserMedia({ video: { facingMode: "environment", width: { ideal: 2560 }, height: { ideal: 1440 } } })
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
        <video ref={video} autoPlay playsInline muted className="w-full rounded-xl bg-black" />
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
