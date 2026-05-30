export interface FileChange {
  filename: string;
  status: string;
  additions: number;
  deletions: number;
  patch?: string | null;
}

export interface PRCommit {
  sha: string;
  message: string;
  author: string | null;
  date: string | null;
}

export interface PRSummary {
  overview: string;
  key_changes: string[];
  impact: string;
}

export interface TokenUsage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

export interface SummaryResponse {
  title: string;
  author: string | null;
  state: string;
  base_branch: string;
  head_branch: string;
  html_url: string;
  additions: number;
  deletions: number;
  changed_files: number;
  files: FileChange[];
  commits: PRCommit[];
  summary: PRSummary;
  model: string;
  usage: TokenUsage;
}

export type RiskSeverity = "high" | "medium" | "low";
export type RiskCategory =
  | "security"
  | "performance"
  | "correctness"
  | "maintainability";

export interface RiskItem {
  file: string;
  line: number | null;
  severity: RiskSeverity;
  category: RiskCategory;
  title: string;
  detail: string;
  suggestion: string;
  confidence: number;
}

export interface RisksResponse {
  title: string;
  author: string | null;
  state: string;
  base_branch: string;
  head_branch: string;
  html_url: string;
  additions: number;
  deletions: number;
  changed_files: number;
  files: FileChange[];
  risks: RiskItem[];
  model: string;
  usage: TokenUsage;
}
