"use client";

import { useEffect, useRef, useState } from "react";
import { streamReview } from "@/lib/api";
import type { RisksResponse, SummaryResponse } from "@/lib/types";
import { SummaryView } from "@/components/SummaryView";
import { DiffView } from "@/components/DiffView";

export default function Home() {
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [stage, setStage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [streamingOverview, setStreamingOverview] = useState("");
  const [summary, setSummary] = useState<SummaryResponse | null>(null);
  const [risks, setRisks] = useState<RisksResponse | null>(null);
  const cancelRef = useRef<(() => void) | null>(null);

  // 卸载时关闭可能仍打开的 SSE 连接
  useEffect(() => () => cancelRef.current?.(), []);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!url.trim() || loading) return;
    cancelRef.current?.();
    setLoading(true);
    setError(null);
    setStage(null);
    setStreamingOverview("");
    setSummary(null);
    setRisks(null);

    cancelRef.current = streamReview(url.trim(), {
      onStage: (msg) => setStage(msg),
      onSummaryDelta: (text) => setStreamingOverview((prev) => prev + text),
      onSummary: (s) => setSummary(s),
      onRisks: (r) => setRisks(r),
      onError: (msg) => {
        setError(msg);
        setLoading(false);
        setStage(null);
      },
      onDone: () => {
        setLoading(false);
        setStage(null);
      },
    });
  }

  return (
    <main className="mx-auto max-w-3xl px-4 py-10">
      <header className="mb-8">
        <h1 className="text-2xl font-semibold">AI PR Review 助手</h1>
        <p className="mt-1 text-sm text-neutral-400">
          粘贴一个 GitHub PR 地址，自动获取变更并由 AI 生成总结、识别风险代码。
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

      {loading && stage && (
        <div className="mt-6 flex items-center gap-2 text-sm text-neutral-400">
          <span className="h-2 w-2 animate-pulse rounded-full bg-blue-500" />
          {stage}
        </div>
      )}

      {/* 总结结构化结果到达前，先逐字显示概述正文 */}
      {!summary && streamingOverview && (
        <section className="mt-6 rounded-lg border border-neutral-800 bg-neutral-900/40 p-5">
          <h3 className="mb-2 text-sm font-semibold text-neutral-200">变更概述</h3>
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-neutral-300">
            {streamingOverview}
            <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-blue-400 align-middle" />
          </p>
        </section>
      )}

      {summary && (
        <div className="mt-8">
          <SummaryView data={summary} />
        </div>
      )}

      {summary && (
        <section className="mt-8">
          <h2 className="mb-3 text-lg font-semibold">
            {risks
              ? `代码变更与风险（${risks.risks.length} 个风险点）`
              : "代码变更与风险（风险分析中…）"}
          </h2>
          <DiffView files={summary.files} risks={risks?.risks ?? []} />
        </section>
      )}
    </main>
  );
}
