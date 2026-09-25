import { useCallback, useEffect, useRef, useState } from "react";

/* Browser speech APIs. Recognition (Chrome/Edge) uses the browser vendor's
   speech service; synthesis uses voices installed on the device. */

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyRecognition = any;

function recognitionCtor(): (new () => AnyRecognition) | null {
  const w = window as unknown as { SpeechRecognition?: new () => AnyRecognition; webkitSpeechRecognition?: new () => AnyRecognition };
  return w.SpeechRecognition || w.webkitSpeechRecognition || null;
}

export const speechInputSupported = () => !!recognitionCtor();

export function useSpeechInput(onText: (finalText: string, interim: string) => void) {
  const [listening, setListening] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const rec = useRef<AnyRecognition>(null);
  const handler = useRef(onText);
  handler.current = onText;

  const stop = useCallback(() => {
    rec.current?.stop();
  }, []);

  const start = useCallback((lang: string) => {
    const Ctor = recognitionCtor();
    if (!Ctor) {
      setError("Voice input needs Chrome or Edge (Web Speech API).");
      return;
    }
    setError(null);
    const r = new Ctor();
    r.lang = lang;
    r.continuous = true;
    r.interimResults = true;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    r.onresult = (e: any) => {
      let finalText = "";
      let interim = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const res = e.results[i];
        if (res.isFinal) finalText += res[0].transcript;
        else interim += res[0].transcript;
      }
      handler.current(finalText, interim);
    };
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    r.onerror = (e: any) => {
      if (e.error === "not-allowed") setError("Microphone permission was denied.");
      else if (e.error === "network") setError("Browser speech service unreachable (it needs internet in Chrome).");
      else if (e.error !== "aborted" && e.error !== "no-speech") setError(`Voice input error: ${e.error}`);
    };
    r.onend = () => setListening(false);
    rec.current = r;
    r.start();
    setListening(true);
  }, []);

  useEffect(() => () => rec.current?.abort(), []);
  return { listening, error, start, stop, supported: !!recognitionCtor() };
}

export function speak(text: string, lang: string, onEnd?: () => void) {
  if (!("speechSynthesis" in window)) return false;
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text.slice(0, 4000));
  u.lang = lang;
  const voice = window.speechSynthesis.getVoices().find((v) => v.lang.toLowerCase().startsWith(lang.slice(0, 2).toLowerCase()));
  if (voice) u.voice = voice;
  u.onend = () => onEnd?.();
  u.onerror = () => onEnd?.();
  window.speechSynthesis.speak(u);
  return true;
}

export function stopSpeaking() {
  if ("speechSynthesis" in window) window.speechSynthesis.cancel();
}
