import type { Lang, Result, SessionView, StreamEvent, Terms } from "./types";

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let msg = `${res.status}`;
    try {
      msg = (await res.json()).detail ?? msg;
    } catch {
      /* not JSON */
    }
    throw new Error(msg);
  }
  return res.json() as Promise<T>;
}

export const api = {
  scan(file: Blob): Promise<SessionView> {
    const fd = new FormData();
    fd.append("file", file, "photo.jpg");
    return fetch("/api/scan", { method: "POST", body: fd }).then(json<SessionView>);
  },
  fromText(text: string): Promise<SessionView> {
    return fetch("/api/text", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    }).then(json<SessionView>);
  },
  samples(): Promise<{ id: string; lang: string; photo: boolean }[]> {
    return fetch("/api/samples").then(json<{ id: string; lang: string; photo: boolean }[]>);
  },
  loadSample(id: string): Promise<SessionView> {
    return fetch(`/api/samples/${encodeURIComponent(id)}`, { method: "POST" }).then(json<SessionView>);
  },
  correctText(sid: string, text: string): Promise<SessionView> {
    return fetch(`/api/session/${sid}/text`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    }).then(json<SessionView>);
  },
  imageUrl(sid: string, kind: "redacted" | "original") {
    return `/api/session/${sid}/image?kind=${kind}`;
  },
  async stream(path: string, onEvent: (e: StreamEvent) => void): Promise<void> {
    const res = await fetch(path, { method: "POST" });
    if (!res.ok || !res.body) throw new Error(`${res.status}`);
    const reader = res.body.getReader();
    const dec = new TextDecoder();
    let buf = "";
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let nl: number;
      while ((nl = buf.indexOf("\n")) >= 0) {
        const line = buf.slice(0, nl).trim();
        buf = buf.slice(nl + 1);
        if (line) onEvent(JSON.parse(line));
      }
    }
  },
  analyze(sid: string, lang: Lang, onEvent: (e: StreamEvent) => void) {
    return api.stream(`/api/session/${sid}/analyze?lang=${lang}`, onEvent);
  },
  localize(sid: string, lang: Lang, onEvent: (e: StreamEvent) => void) {
    return api.stream(`/api/session/${sid}/localize?lang=${lang}`, onEvent);
  },
  money(sid: string, lang: Lang, terms: Partial<Terms>): Promise<Result> {
    return fetch(`/api/session/${sid}/money?lang=${lang}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(terms),
    }).then(json<Result>);
  },
  ask(sid: string, lang: Lang, question: string) {
    return fetch(`/api/session/${sid}/ask?lang=${lang}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    }).then(json<{ answer: string; found: boolean; clause_ids: number[]; engine: string }>);
  },
  transcribe(sid: string, lang: Lang, wav: Blob): Promise<{ text: string; lang: Lang }> {
    const fd = new FormData();
    fd.append("file", wav, "question.wav");
    return fetch(`/api/session/${sid}/transcribe?lang=${lang}`, { method: "POST", body: fd }).then(
      json<{ text: string; lang: Lang }>,
    );
  },
  async tts(text: string, lang: Lang, sid?: string): Promise<Blob | null> {
    const res = await fetch("/api/tts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, lang, session_id: sid }),
    });
    if (res.status === 503) return null;
    if (!res.ok) throw new Error(`${res.status}`);
    return res.blob();
  },
  wipe(sid?: string) {
    return fetch(sid ? `/api/session/${sid}/wipe` : "/api/wipe", { method: "POST" }).then(json<{ wiped: unknown }>);
  },
  selfcheck(probe = false) {
    return fetch(`/api/selfcheck?probe_network=${probe}`).then(json<Record<string, any>>);
  },
};
