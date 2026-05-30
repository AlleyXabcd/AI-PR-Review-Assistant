import type { RisksResponse, SummaryResponse } from "./types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

async function postReview<T>(path: string, prUrl: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pr_url: prUrl }),
  });

  if (!res.ok) {
    let detail = `请求失败 (${res.status})`;
    try {
      const data = await res.json();
      if (data?.detail) detail = data.detail;
    } catch {
      // 忽略非 JSON 错误体
    }
    throw new Error(detail);
  }

  return res.json();
}

export function fetchSummary(prUrl: string): Promise<SummaryResponse> {
  return postReview<SummaryResponse>("/review/summary", prUrl);
}

export function fetchRisks(prUrl: string): Promise<RisksResponse> {
  return postReview<RisksResponse>("/review/risks", prUrl);
}

export interface WritebackResponse {
  posted: boolean;
  dry_run: boolean;
  body: string;
  comment_url: string;
  model: string;
}

/** 调用 /review/writeback；dry_run=true 只取预览正文，false 真正发评论到 GitHub PR。 */
async function callWriteback(
  prUrl: string,
  dryRun: boolean,
): Promise<WritebackResponse> {
  const res = await fetch(`${API_BASE}/review/writeback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pr_url: prUrl, dry_run: dryRun }),
  });

  if (!res.ok) {
    let detail = `请求失败 (${res.status})`;
    try {
      const data = await res.json();
      if (data?.detail) detail = data.detail;
    } catch {
      // 忽略非 JSON 错误体
    }
    throw new Error(detail);
  }

  return res.json();
}

export function previewWriteback(prUrl: string): Promise<WritebackResponse> {
  return callWriteback(prUrl, true);
}

export function postWriteback(prUrl: string): Promise<WritebackResponse> {
  return callWriteback(prUrl, false);
}

export interface StreamHandlers {
  onStage?: (message: string) => void;
  onSummaryDelta?: (text: string) => void;
  onSummary?: (data: SummaryResponse) => void;
  onRisks?: (data: RisksResponse) => void;
  onError?: (message: string) => void;
  onDone?: () => void;
}

/**
 * 以 SSE 订阅 /review/stream：总结概述正文逐字到达（summary_delta），
 * 总结完成后补结构化要点（summary），风险整块到达（risks）。
 * 返回一个取消函数，调用后关闭连接（组件卸载或重新提交时清理）。
 */
export function streamReview(prUrl: string, handlers: StreamHandlers): () => void {
  const url = `${API_BASE}/review/stream?pr_url=${encodeURIComponent(prUrl)}`;
  const es = new EventSource(url);

  es.addEventListener("stage", (e) => {
    handlers.onStage?.(JSON.parse((e as MessageEvent).data).message ?? "");
  });
  es.addEventListener("summary_delta", (e) => {
    handlers.onSummaryDelta?.(JSON.parse((e as MessageEvent).data).text ?? "");
  });
  es.addEventListener("summary", (e) => {
    handlers.onSummary?.(JSON.parse((e as MessageEvent).data));
  });
  es.addEventListener("risks", (e) => {
    handlers.onRisks?.(JSON.parse((e as MessageEvent).data));
  });
  es.addEventListener("error", (e) => {
    // 后端主动发的 error 事件（带 data）与连接断开（无 data）都会到这里
    const data = (e as MessageEvent).data;
    if (data) {
      handlers.onError?.(JSON.parse(data).message ?? "分析失败");
    } else {
      handlers.onError?.("连接中断，请重试");
    }
    es.close();
  });
  es.addEventListener("done", () => {
    handlers.onDone?.();
    es.close();
  });

  return () => es.close();
}
