"use client";

import { useState } from "react";
import { fetchSummary } from "@/lib/api";
import type { SummaryResponse } from "@/lib/types";
import { SummaryView } from "@/components/SummaryView";

export default function Home() {
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<SummaryResponse | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!url.trim() || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await fetchSummary(url.trim());
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "未知错误");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto max-w-3xl px-4 py-10">
      <header className="mb-8">
        <h1 className="text-2xl font-semibold">AI PR Review 助手</h1>
        <p className="mt-1 text-sm text-neutral-400">
          粘贴一个 GitHub PR 地址，自动获取变更并由 AI 生成总结。
        </p>
      </header>

      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="text"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://github.com/owner/repo/pull/123"
          className="flex-1 rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm outline-none focus:border-neutral-500"
        />
        <button
          type="submit"
          disabled={loading || !url.trim()}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? "分析中…" : "分析"}
        </button>
      </form>

      {error && (
        <div className="mt-6 rounded-md border border-red-800 bg-red-950/50 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {loading && (
        <div className="mt-6 text-sm text-neutral-400">
          正在抓取 PR 并调用模型，请稍候…
        </div>
      )}

      {result && (
        <div className="mt-8">
          <SummaryView data={result} />
        </div>
      )}
    </main>
  );
}
