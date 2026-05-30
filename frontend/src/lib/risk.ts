import type { RiskCategory, RiskSeverity } from "./types";

export const SEVERITY_STYLE: Record<RiskSeverity, string> = {
  high: "border-red-700 bg-red-950/40 text-red-300",
  medium: "border-amber-700 bg-amber-950/40 text-amber-300",
  low: "border-sky-700 bg-sky-950/40 text-sky-300",
};

export const SEVERITY_LABEL: Record<RiskSeverity, string> = {
  high: "高危",
  medium: "中危",
  low: "低危",
};

export const SEVERITY_DOT: Record<RiskSeverity, string> = {
  high: "bg-red-500",
  medium: "bg-amber-500",
  low: "bg-sky-500",
};

export const CATEGORY_LABEL: Record<RiskCategory, string> = {
  security: "安全",
  performance: "性能",
  correctness: "正确性",
  maintainability: "可维护性",
};

// 列表/筛选默认按严重级别从高到低排序
export const SEVERITY_ORDER: Record<RiskSeverity, number> = {
  high: 0,
  medium: 1,
  low: 2,
};

export const SEVERITIES: RiskSeverity[] = ["high", "medium", "low"];

/** 行级风险锚点：定位到 diff 中新文件的某一行。 */
export function diffLineAnchor(file: string, line: number): string {
  return `diff-${file}-L${line}`;
}

/** 文件级风险锚点：无具体行号时定位到文件标题。 */
export function diffFileAnchor(file: string): string {
  return `diff-file-${file}`;
}
