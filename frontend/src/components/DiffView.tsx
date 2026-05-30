"use client";

import { useEffect, useState } from "react";
import type { FileChange, RiskItem } from "@/lib/types";
import { parsePatch, type DiffLine } from "@/lib/diff";
import {
  CATEGORY_LABEL,
  SEVERITY_LABEL,
  SEVERITY_STYLE,
  diffFileAnchor,
  diffLineAnchor,
} from "@/lib/risk";

// 点击概览项时下发的定位信号；nonce 保证重复点击同一目标也能再次触发
export interface LocateTarget {
  file: string;
  line: number | null;
  nonce: number;
}

function RiskCard({ risk }: { risk: RiskItem }) {
  return (
    <div
      className={`my-1 rounded-md border px-3 py-2 text-xs ${SEVERITY_STYLE[risk.severity]}`}
    >
      <div className="flex flex-wrap items-center gap-2 font-medium">
        <span className="rounded bg-black/30 px-1.5 py-0.5">
          {SEVERITY_LABEL[risk.severity]}
        </span>
        <span className="rounded bg-black/30 px-1.5 py-0.5">
          {CATEGORY_LABEL[risk.category] ?? risk.category}
        </span>
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
  locate,
}: {
  file: FileChange;
  risks: RiskItem[];
  locate: LocateTarget | null;
}) {
  const [open, setOpen] = useState(true);
  const [flashLine, setFlashLine] = useState<number | null>(null);
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

  // 收到指向本文件的定位信号：展开、滚动到目标行（无行号则滚到文件头）并短暂高亮
  useEffect(() => {
    if (!locate || locate.file !== file.filename) return;
    setOpen(true);
    const anchorId =
      locate.line != null
        ? diffLineAnchor(file.filename, locate.line)
        : diffFileAnchor(file.filename);
    // 等展开后的 DOM 就绪再滚动
    const t = setTimeout(() => {
      const el = document.getElementById(anchorId);
      el?.scrollIntoView({ behavior: "smooth", block: "center" });
      if (locate.line != null) {
        setFlashLine(locate.line);
        setTimeout(() => setFlashLine(null), 1600);
      }
    }, 0);
    return () => clearTimeout(t);
  }, [locate, file.filename]);

  const riskCount = risks.length;

  return (
    <div
      id={diffFileAnchor(file.filename)}
      className="scroll-mt-4 overflow-hidden rounded-lg border border-neutral-800"
    >
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
                    file={file.filename}
                    line={ln}
                    risks={ln.newLine != null ? risksByLine.get(ln.newLine) : undefined}
                    flash={ln.newLine != null && ln.newLine === flashLine}
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
  file,
  line,
  risks,
  flash,
}: {
  file: string;
  line: DiffLine;
  risks: RiskItem[] | undefined;
  flash: boolean;
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

  const anchorId =
    line.newLine != null ? diffLineAnchor(file, line.newLine) : undefined;

  return (
    <>
      <tr
        id={anchorId}
        className={`scroll-mt-16 transition-colors duration-700 ${
          flash ? "bg-blue-900/50" : LINE_BG[line.type]
        }`}
      >
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
  locate = null,
}: {
  files: FileChange[];
  risks: RiskItem[];
  locate?: LocateTarget | null;
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
        <FileDiff
          key={f.filename}
          file={f}
          risks={risksByFile.get(f.filename) ?? []}
          locate={locate}
        />
      ))}
    </div>
  );
}
