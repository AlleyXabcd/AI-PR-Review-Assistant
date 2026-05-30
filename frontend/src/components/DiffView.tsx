"use client";

import { useState } from "react";
import type { FileChange, RiskItem, RiskSeverity } from "@/lib/types";
import { parsePatch, type DiffLine } from "@/lib/diff";

const SEVERITY_STYLE: Record<RiskSeverity, string> = {
  high: "border-red-700 bg-red-950/40 text-red-300",
  medium: "border-amber-700 bg-amber-950/40 text-amber-300",
  low: "border-sky-700 bg-sky-950/40 text-sky-300",
};

const SEVERITY_LABEL: Record<RiskSeverity, string> = {
  high: "高危",
  medium: "中危",
  low: "低危",
};

function RiskCard({ risk }: { risk: RiskItem }) {
  return (
    <div
      className={`my-1 rounded-md border px-3 py-2 text-xs ${SEVERITY_STYLE[risk.severity]}`}
    >
      <div className="flex flex-wrap items-center gap-2 font-medium">
        <span className="rounded bg-black/30 px-1.5 py-0.5">
          {SEVERITY_LABEL[risk.severity]}
        </span>
        <span className="rounded bg-black/30 px-1.5 py-0.5">{risk.category}</span>
        <span>{risk.title}</span>
        <span className="ml-auto opacity-70">
          置信度 {(risk.confidence * 100).toFixed(0)}%
        </span>
      </div>
      {risk.detail && <p className="mt-1 leading-relaxed opacity-90">{risk.detail}</p>}
      {risk.suggestion && (
        <p className="mt-1 leading-relaxed">
          <span className="opacity-70">建议：</span>
          {risk.suggestion}
        </p>
      )}
    </div>
  );
}

const LINE_BG: Record<DiffLine["type"], string> = {
  add: "bg-green-950/40",
  del: "bg-red-950/40",
  context: "",
  hunk: "bg-neutral-800/40 text-neutral-400",
};

const LINE_MARK: Record<DiffLine["type"], string> = {
  add: "+",
  del: "-",
  context: " ",
  hunk: "",
};

function FileDiff({
  file,
  risks,
}: {
  file: FileChange;
  risks: RiskItem[];
}) {
  const [open, setOpen] = useState(true);
  const lines = parsePatch(file.patch);

  // 把风险按新文件行号归组，渲染时叠加到对应行下方
  const risksByLine = new Map<number, RiskItem[]>();
  const fileLevelRisks: RiskItem[] = [];
  for (const r of risks) {
    if (r.line == null) {
      fileLevelRisks.push(r);
    } else {
      const arr = risksByLine.get(r.line) ?? [];
      arr.push(r);
      risksByLine.set(r.line, arr);
    }
  }

  const riskCount = risks.length;

  return (
    <div className="overflow-hidden rounded-lg border border-neutral-800">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-3 bg-neutral-900/60 px-4 py-2 text-left text-sm hover:bg-neutral-900"
      >
        <span className="truncate font-mono text-neutral-200">{file.filename}</span>
        <span className="flex shrink-0 items-center gap-3 text-xs">
          {riskCount > 0 && (
            <span className="rounded bg-red-900/60 px-1.5 py-0.5 text-red-200">
              {riskCount} 风险
            </span>
          )}
          <span className="font-mono">
            <span className="text-green-400">+{file.additions}</span>{" "}
            <span className="text-red-400">-{file.deletions}</span>
          </span>
          <span className="text-neutral-500">{open ? "▾" : "▸"}</span>
        </span>
      </button>

      {open && (
        <div>
          {fileLevelRisks.length > 0 && (
            <div className="border-b border-neutral-800 px-3 py-2">
              {fileLevelRisks.map((r, i) => (
                <RiskCard key={`f${i}`} risk={r} />
              ))}
            </div>
          )}
          {lines.length === 0 ? (
            <p className="px-4 py-3 text-xs text-neutral-500">
              （无文本 diff，可能为二进制或过大文件）
            </p>
          ) : (
            <table className="w-full border-collapse font-mono text-xs">
              <tbody>
                {lines.map((ln, i) => (
                  <DiffRow
                    key={i}
                    line={ln}
                    risks={ln.newLine != null ? risksByLine.get(ln.newLine) : undefined}
                  />
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}

function DiffRow({
  line,
  risks,
}: {
  line: DiffLine;
  risks: RiskItem[] | undefined;
}) {
  if (line.type === "hunk") {
    return (
      <tr className={LINE_BG.hunk}>
        <td className="select-none px-2 text-right text-neutral-600" />
        <td className="select-none px-2 text-right text-neutral-600" />
        <td className="whitespace-pre-wrap px-2 py-0.5">{line.content}</td>
      </tr>
    );
  }

  return (
    <>
      <tr className={LINE_BG[line.type]}>
        <td className="w-10 select-none px-2 text-right text-neutral-600">
          {line.oldLine ?? ""}
        </td>
        <td className="w-10 select-none px-2 text-right text-neutral-600">
          {line.newLine ?? ""}
        </td>
        <td className="whitespace-pre-wrap px-2 py-0.5">
          <span className="select-none text-neutral-500">{LINE_MARK[line.type]}</span>
          {line.content}
        </td>
      </tr>
      {risks && risks.length > 0 && (
        <tr>
          <td colSpan={3} className="px-3">
            {risks.map((r, i) => (
              <RiskCard key={i} risk={r} />
            ))}
          </td>
        </tr>
      )}
    </>
  );
}

export function DiffView({
  files,
  risks,
}: {
  files: FileChange[];
  risks: RiskItem[];
}) {
  const risksByFile = new Map<string, RiskItem[]>();
  for (const r of risks) {
    const arr = risksByFile.get(r.file) ?? [];
    arr.push(r);
    risksByFile.set(r.file, arr);
  }

  return (
    <div className="space-y-3">
      {files.map((f) => (
        <FileDiff key={f.filename} file={f} risks={risksByFile.get(f.filename) ?? []} />
      ))}
    </div>
  );
}
