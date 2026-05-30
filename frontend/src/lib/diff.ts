export type DiffLineType = "add" | "del" | "context" | "hunk";

export interface DiffLine {
  type: DiffLineType;
  content: string;
  // 新文件中的行号（add / context 行有值；del 行为 null）
  newLine: number | null;
  // 旧文件中的行号（del / context 行有值；add 行为 null）
  oldLine: number | null;
}

const HUNK_RE = /^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@/;

/**
 * 解析单个文件的 unified diff（GitHub patch 片段）为带行号的行列表。
 * 行号按 hunk header 推算，供 diff 高亮与按行叠加风险使用。
 */
export function parsePatch(patch: string | null | undefined): DiffLine[] {
  if (!patch) return [];

  const lines: DiffLine[] = [];
  let oldLine = 0;
  let newLine = 0;

  for (const raw of patch.split("\n")) {
    const hunk = HUNK_RE.exec(raw);
    if (hunk) {
      oldLine = parseInt(hunk[1], 10);
      newLine = parseInt(hunk[3], 10);
      lines.push({ type: "hunk", content: raw, newLine: null, oldLine: null });
      continue;
    }

    // GitHub patch 不含 file header（--- / +++），但 "\ No newline" 之类元行需跳过计数
    if (raw.startsWith("\\")) {
      lines.push({ type: "context", content: raw, newLine: null, oldLine: null });
      continue;
    }

    const marker = raw[0];
    if (marker === "+") {
      lines.push({ type: "add", content: raw.slice(1), newLine, oldLine: null });
      newLine += 1;
    } else if (marker === "-") {
      lines.push({ type: "del", content: raw.slice(1), newLine: null, oldLine });
      oldLine += 1;
    } else {
      // 上下文行（含以空格开头的行，以及空字符串结尾行）
      const content = marker === " " ? raw.slice(1) : raw;
      lines.push({ type: "context", content, newLine, oldLine });
      newLine += 1;
      oldLine += 1;
    }
  }

  return lines;
}
