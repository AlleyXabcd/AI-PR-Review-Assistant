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
