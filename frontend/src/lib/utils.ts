export const cx = (...parts: (string | false | null | undefined)[]) => parts.filter(Boolean).join(" ");

export function formatBytes(n: number): string {
  if (!n) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.min(Math.floor(Math.log(n) / Math.log(1024)), units.length - 1);
  return `${(n / 1024 ** i).toFixed(i >= 3 ? 1 : 0)} ${units[i]}`;
}

export function timeAgo(ts: number): string {
  const s = Math.round((Date.now() - ts) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  if (s < 86400) return `${Math.round(s / 3600)} h ago`;
  return new Date(ts).toLocaleDateString();
}

export interface CodeBlock {
  lang: string;
  code: string;
}

/** Extracts fenced code blocks from Markdown (complete blocks only). */
export function extractCodeBlocks(markdown: string): CodeBlock[] {
  const blocks: CodeBlock[] = [];
  const re = /```([\w+#.-]*)[^\n]*\n([\s\S]*?)```/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(markdown))) {
    const code = m[2].replace(/\s+$/, "");
    if (code) blocks.push({ lang: (m[1] || "text").toLowerCase(), code });
  }
  return blocks;
}

/** Turns [1] / [2, 3] citations into links the Markdown renderer shows as chips. */
export function linkCitations(markdown: string, scope: string, count: number): string {
  if (!count) return markdown;
  const parts = markdown.split(/(```[\s\S]*?(?:```|$))/g);
  return parts
    .map((part) =>
      part.startsWith("```")
        ? part
        : part.replace(/\[(\d{1,2}(?:\s*[,–-]\s*\d{1,2})*)\](?!\()/g, (whole, inner: string) => {
            const nums = inner.split(/\s*[,–-]\s*/).map(Number);
            if (nums.some((n) => n < 1 || n > count)) return whole;
            return nums.map((n) => `[${n}](#cite-${scope}-${n})`).join("");
          }),
    )
    .join("");
}

export function downloadText(filename: string, text: string, type = "text/plain") {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const ta = document.createElement("textarea");
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand("copy");
    ta.remove();
    return ok;
  }
}

/** Downscale an image file to a small data URL thumbnail for the chat history. */
export function imageThumb(file: File, max = 180): Promise<string | undefined> {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      const scale = Math.min(1, max / Math.max(img.width, img.height));
      const canvas = document.createElement("canvas");
      canvas.width = Math.round(img.width * scale);
      canvas.height = Math.round(img.height * scale);
      canvas.getContext("2d")?.drawImage(img, 0, 0, canvas.width, canvas.height);
      URL.revokeObjectURL(url);
      resolve(canvas.toDataURL("image/jpeg", 0.8));
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      resolve(undefined);
    };
    img.src = url;
  });
}

export function stripMarkdown(md: string): string {
  return md
    .replace(/```[\s\S]*?```/g, " code block omitted. ")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\[(\d+)\]\(#cite[^)]*\)/g, "")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/[#>*_|~-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

/** Puts text into the visible composer (the user reviews it before sending). */
export function seedComposer(text: string) {
  window.dispatchEvent(new CustomEvent("nexgraft:seed", { detail: text }));
}
