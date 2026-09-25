import { CircleCheck, Info, TriangleAlert, X } from "lucide-react";
import { create } from "zustand";

type Kind = "info" | "success" | "error";
interface Toast {
  id: number;
  kind: Kind;
  text: string;
}

const useToasts = create<{ toasts: Toast[]; push: (kind: Kind, text: string) => void; dismiss: (id: number) => void }>((set) => ({
  toasts: [],
  push: (kind, text) => {
    const id = Date.now() + Math.random();
    set((s) => ({ toasts: [...s.toasts.slice(-3), { id, kind, text }] }));
    setTimeout(() => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })), kind === "error" ? 7000 : 3500);
  },
  dismiss: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}));

export const toast = {
  info: (t: string) => useToasts.getState().push("info", t),
  success: (t: string) => useToasts.getState().push("success", t),
  error: (t: string) => useToasts.getState().push("error", t),
};

export function Toasts() {
  const { toasts, dismiss } = useToasts();
  return (
    <div className="toasts" role="status" aria-live="polite">
      {toasts.map((t) => (
        <div key={t.id} className={`toast toast-${t.kind}`}>
          {t.kind === "success" ? <CircleCheck size={16} /> : t.kind === "error" ? <TriangleAlert size={16} /> : <Info size={16} />}
          <span>{t.text}</span>
          <button className="icon-btn sm" onClick={() => dismiss(t.id)} aria-label="Dismiss">
            <X size={14} />
          </button>
        </div>
      ))}
    </div>
  );
}
