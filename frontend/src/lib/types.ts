export interface FileChange {
  filename: string;
  status: string;
  additions: number;
  deletions: number;
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
