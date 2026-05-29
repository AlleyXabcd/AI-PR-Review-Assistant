import type { SummaryResponse } from "./types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export async function fetchSummary(prUrl: string): Promise<SummaryResponse> {
  const res = await fetch(`${API_BASE}/review/summary`, {
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
