import { ArrowUp, FileText, Image as ImageIcon, Languages, LoaderCircle, Mic, Paperclip, Square, TriangleAlert, Type, X } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { api, ApiError } from "../lib/api";
import { useSpeechInput } from "../lib/speech";
import { useStore } from "../lib/store";
import type { Attachment } from "../lib/types";
import { cx, formatBytes, imageThumb } from "../lib/utils";

interface Pending {
  key: string;
  name: string;
  kind: "document" | "image";
  status: "uploading" | "ready" | "error";
  attachment?: Attachment;
  thumb?: string;
  error?: string;
}

export interface ComposerProps {
  variant: "hero" | "dock";
  placeholder: string;
  busy: boolean;
  onSend: (text: string, attachments: Attachment[], voice: boolean) => void;
  onStop?: () => void;
  accent?: string;
  footer?: ReactNode;
  seed?: { text: string; n: number };
  autoFocus?: boolean;
}

const IMAGE_ACCEPT = "image/png,image/jpeg,image/webp,image/gif,image/bmp";

export function Composer({ variant, placeholder, busy, onSend, onStop, accent, footer, seed, autoFocus }: ComposerProps) {
  const config = useStore((s) => s.config);
  const language = useStore((s) => s.settings.language);
  const updateSettings = useStore((s) => s.updateSettings);
  const [text, setText] = useState("");
  const [interim, setInterim] = useState("");
  const [pending, setPending] = useState<Pending[]>([]);
  const [usedVoice, setUsedVoice] = useState(false);
  const [dragging, setDragging] = useState(false);
  const ta = useRef<HTMLTextAreaElement>(null);
  const docInput = useRef<HTMLInputElement>(null);
  const imgInput = useRef<HTMLInputElement>(null);

  const speechLang = config?.languages.find((l) => l.code === language)?.speech || "en-IN";
  const speech = useSpeechInput((finalText, interimText) => {
    if (finalText) {
      setText((t) => (t ? `${t.replace(/\s+$/, "")} ${finalText.trim()}` : finalText.trim()));
      setUsedVoice(true);
    }
    setInterim(interimText);
  });

  useEffect(() => {
    if (seed?.text) {
      setText(seed.text);
      requestAnimationFrame(() => {
        ta.current?.focus();
        autosize();
      });
    }
  }, [seed?.n]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(autosize, [text, interim]);

  useEffect(() => {
    const onSeed = (e: Event) => {
      setText((e as CustomEvent<string>).detail);
      requestAnimationFrame(() => ta.current?.focus());
    };
    window.addEventListener("nexgraft:seed", onSeed);
    return () => window.removeEventListener("nexgraft:seed", onSeed);
  }, []);

  function autosize() {
    const el = ta.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, variant === "hero" ? 320 : 260)}px`;
  }

  const docAccept = (config?.features.document_types || []).join(",");
  const uploading = pending.some((p) => p.status === "uploading");
  const ready = pending.filter((p) => p.status === "ready" && p.attachment).map((p) => p.attachment!);
  const canSend = !busy && !uploading && (text.trim().length > 0 || ready.length > 0);

  async function addFiles(files: FileList | File[]) {
    for (const file of Array.from(files).slice(0, 6)) {
      const isImage = file.type.startsWith("image/") || /\.(png|jpe?g|webp|gif|bmp)$/i.test(file.name);
      const key = `${file.name}-${file.size}-${Math.random()}`;
      const thumb = isImage ? await imageThumb(file) : undefined;
      setPending((p) => [...p, { key, name: file.name, kind: isImage ? "image" : "document", status: "uploading", thumb }]);
      api
        .upload(file, isImage ? text.slice(0, 300) : "")
        .then((att) => setPending((p) => p.map((x) => (x.key === key ? { ...x, status: "ready", attachment: { ...att, thumb } } : x))))
        .catch((err) =>
          setPending((p) => p.map((x) => (x.key === key ? { ...x, status: "error", error: err instanceof ApiError ? err.message : String(err) } : x))),
        );
    }
  }

  function onPick(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files || []);
    e.target.value = "";
    if (files.length) addFiles(files);
  }

  function send() {
    if (!canSend) return;
    if (speech.listening) speech.stop();
    onSend(text.trim(), ready, usedVoice);
    setText("");
    setInterim("");
    setPending([]);
    setUsedVoice(false);
  }

  return (
    <div
      className={cx("composer", `composer-${variant}`, dragging && "dragging", busy && "busy")}
      style={accent ? ({ "--accent": accent } as React.CSSProperties) : undefined}
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        if (e.dataTransfer.files.length) addFiles(e.dataTransfer.files);
      }}
    >
      {pending.length > 0 && (
        <div className="attach-row">
          {pending.map((p) => (
            <div key={p.key} className={cx("attach-chip", p.status)} title={p.error || p.attachment?.preview?.slice(0, 300)}>
              {p.thumb ? <img src={p.thumb} alt="" /> : <FileText size={15} />}
              <div className="attach-meta">
                <span className="attach-name">{p.name}</span>
                <span className="attach-sub">
                  {p.status === "uploading" && (
                    <>
                      <LoaderCircle size={11} className="spin" /> {p.kind === "image" ? "Vision model reading image…" : "Extracting text…"}
                    </>
                  )}
                  {p.status === "ready" &&
                    (p.kind === "image" ? `Described by ${p.attachment?.model}` : `${p.attachment?.chars.toLocaleString()} chars · ${formatBytes(p.attachment?.size || 0)}`)}
                  {p.status === "error" && (
                    <>
                      <TriangleAlert size={11} /> {p.error}
                    </>
                  )}
                </span>
              </div>
              <button className="icon-btn sm" onClick={() => setPending((x) => x.filter((y) => y.key !== p.key))} aria-label="Remove attachment">
                <X size={13} />
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="composer-input">
        <textarea
          ref={ta}
          rows={variant === "hero" ? 3 : 1}
          value={interim ? `${text}${text ? " " : ""}${interim}` : text}
          placeholder={speech.listening ? "Listening… speak your requirement" : placeholder}
          autoFocus={autoFocus}
          onChange={(e) => {
            setText(e.target.value);
            setInterim("");
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              send();
            }
          }}
          onPaste={(e) => {
            const files = Array.from(e.clipboardData.files);
            if (files.length) {
              e.preventDefault();
              addFiles(files);
            }
          }}
        />
      </div>

      <div className="composer-bar">
        <div className="input-modes" role="group" aria-label="Input options">
          {variant === "hero" && (
            <span className="mode-pill active" title="Type your problem">
              <Type size={14} /> <span>Text</span>
            </span>
          )}
          <button
            className={cx("mode-pill", speech.listening && "recording")}
            onClick={() => (speech.listening ? speech.stop() : speech.start(speechLang))}
            title={speech.supported ? `Voice input (${speechLang})` : "Voice input needs Chrome or Edge"}
            disabled={!speech.supported}
          >
            <Mic size={14} /> <span>{speech.listening ? "Stop" : "Voice"}</span>
          </button>
          <button className="mode-pill" onClick={() => imgInput.current?.click()} title="Attach an image (read by a local vision model)">
            <ImageIcon size={14} /> <span>Image</span>
          </button>
          <button className="mode-pill" onClick={() => docInput.current?.click()} title="Attach PDF, DOCX, text, CSV, FASTA…">
            {variant === "hero" ? <FileText size={14} /> : <Paperclip size={14} />} <span>Document</span>
          </button>
          <label className="lang-select" title="Response language">
            <Languages size={14} />
            <select value={language} onChange={(e) => updateSettings({ language: e.target.value })} aria-label="Response language">
              <option value="auto">Auto</option>
              {config?.languages.map((l) => (
                <option key={l.code} value={l.code}>
                  {l.native === l.name ? l.name : `${l.native} · ${l.name}`}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="composer-send">
          {footer}
          {busy && onStop ? (
            <button className="send-btn stop" onClick={onStop} title="Stop generating" aria-label="Stop">
              <Square size={14} fill="currentColor" />
            </button>
          ) : (
            <button className="send-btn" onClick={send} disabled={!canSend} title="Send (Enter)" aria-label="Send">
              <ArrowUp size={18} strokeWidth={2.4} />
            </button>
          )}
        </div>
      </div>
      {speech.error && (
        <p className="composer-error">
          <TriangleAlert size={13} /> {speech.error}
        </p>
      )}
      <input ref={docInput} type="file" hidden multiple accept={docAccept} onChange={onPick} />
      <input ref={imgInput} type="file" hidden multiple accept={IMAGE_ACCEPT} onChange={onPick} />
    </div>
  );
}
