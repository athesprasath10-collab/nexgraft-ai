import { Download, ImageDown } from "lucide-react";
import type { CircuitPart, Schematic } from "../lib/types";
import { downloadText } from "../lib/utils";
import { toast } from "./Toast";

const slug = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "circuit";

async function svgToPng(svg: string, scale = 3): Promise<Blob> {
  const url = URL.createObjectURL(new Blob([svg], { type: "image/svg+xml" }));
  try {
    const img = new Image();
    await new Promise<void>((resolve, reject) => {
      img.onload = () => resolve();
      img.onerror = () => reject(new Error("The schematic could not be rendered."));
      img.src = url;
    });
    const canvas = document.createElement("canvas");
    canvas.width = Math.ceil(img.naturalWidth * scale);
    canvas.height = Math.ceil(img.naturalHeight * scale);
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("Canvas is not available.");
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    return await new Promise((resolve, reject) => canvas.toBlob((b) => (b ? resolve(b) : reject(new Error("PNG export failed."))), "image/png"));
  } finally {
    URL.revokeObjectURL(url);
  }
}

export function SchematicView({ schematic, parts }: { schematic: Schematic; parts?: CircuitPart[] }) {
  const name = `nexgraft-${slug(schematic.title)}`;
  const savePng = async () => {
    try {
      const blob = await svgToPng(schematic.svg);
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `${name}.png`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : String(err));
    }
  };

  return (
    <figure className="schematic">
      <div className="schematic-paper">
        <img src={`data:image/svg+xml;charset=utf-8,${encodeURIComponent(schematic.svg)}`} alt={`Schematic: ${schematic.title}`} />
      </div>
      <figcaption>
        <span className="schematic-title">{schematic.title}</span>
        {schematic.caption && <span className="faint small">{schematic.caption}</span>}
        <span className="schematic-actions">
          <button className="btn btn-sm btn-ghost" onClick={savePng} title="Download as PNG image">
            <ImageDown size={14} /> PNG
          </button>
          <button className="btn btn-sm btn-ghost" onClick={() => downloadText(`${name}.svg`, schematic.svg, "image/svg+xml")} title="Download as SVG (scalable)">
            <Download size={14} /> SVG
          </button>
        </span>
      </figcaption>
      {parts && parts.length > 0 && (
        <table className="table parts-table">
          <thead>
            <tr>
              <th>Ref</th>
              <th>Value</th>
              <th>Role</th>
            </tr>
          </thead>
          <tbody>
            {parts.map((p) => (
              <tr key={p.ref}>
                <td className="mono">{p.ref}</td>
                <td>{p.value}</td>
                <td className="faint">{p.description}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </figure>
  );
}
