"use client";

import { useState } from "react";
import {
  postWriteback,
  previewWriteback,
  type WritebackResponse,
} from "@/lib/api";

type Phase = "idle" | "previewing" | "preview" | "posting" | "posted";

export function WritebackPanel({ prUrl }: { prUrl: string }) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [body, setBody] = useState("");
  const [result, setResult] = useState<WritebackResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handlePreview() {
    setPhase("previewing");
    setError(null);
    try {
      const r = await previewWriteback(prUrl);
      setBody(r.body);
      setPhase("preview");
    } catch (e) {
      setError(e instanceof Error ? e.message : "预览失败");
      setPhase("idle");
    }
  }

  async function handlePost() {
    setPhase("posting");
    setError(null);
    try {
      const r = await postWriteback(prUrl);
      setResult(r);
      setPhase("posted");
    } catch (e) {
      setError(e instanceof Error ? e.message : "回写失败");
      setPhase("preview");
    }
  }

  function reset() {
    setPhase("idle");
    setBody("");
    setResult(null);
    setError(null);
  }

  return (
    <section className="rounded-lg border border-neutral-800 bg-neutral-900/40 p-5">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-neutral-200">回写到 GitHub PR</h3>
        {phase === "idle" && (
          <button
            type="button"
            onClick={handlePreview}
            className="rounded-md border border-neutral-700 px-3 py-1.5 text-xs text-neutral-200 transition hover:border-neutral-500 hover:bg-neutral-800"
          >
            预览评论
          </button>
        )}
        {phase === "previewing" && (
          <span className="text-xs text-neutral-400">生成预览中…</span>
        )}
      </div>

      <p className="mt-2 text-xs text-neutral-500">
        将分析结果拼成一条评论发布到该 PR 的对话区。需要 GITHUB_TOKEN 对目标仓库有写权限。
      </p>

      {error && (
        <div className="mt-3 rounded-md border border-red-800 bg-red-950/50 px-3 py-2 text-xs text-red-300">
          {error}
        </div>
      )}

      <WritebackBody
        phase={phase}
        body={body}
        result={result}
        onPost={handlePost}
        onReset={reset}
      />
    </section>
  );
}

function WritebackBody({
  phase,
  body,
  result,
  onPost,
  onReset,
}: {
  phase: Phase;
  body: string;
  result: WritebackResponse | null;
  onPost: () => void;
  onReset: () => void;
}) {
  if (phase === "posted" && result) {
    return (
      <div className="mt-3 rounded-md border border-emerald-800 bg-emerald-950/40 px-3 py-3 text-sm text-emerald-200">
        <p>评论已发布到 GitHub PR。</p>
        {result.comment_url && (
          <a
            href={result.comment_url}
            target="_blank"
            rel="noreferrer"
            className="mt-1 inline-block text-xs text-emerald-300 underline"
          >
            在 GitHub 查看评论 ↗
          </a>
        )}
        <button
          type="button"
          onClick={onReset}
          className="ml-3 text-xs text-neutral-400 underline hover:text-neutral-200"
        >
          重新预览
        </button>
      </div>
    );
  }

  if (phase !== "preview" && phase !== "posting") return null;

  return (
    <div className="mt-3">
      <pre className="max-h-80 overflow-auto whitespace-pre-wrap rounded-md border border-neutral-800 bg-neutral-950 p-3 text-xs leading-relaxed text-neutral-300">
        {body}
      </pre>
      <div className="mt-3 flex items-center gap-2">
        <button
          type="button"
          onClick={onPost}
          disabled={phase === "posting"}
          className="rounded-md bg-blue-600 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {phase === "posting" ? "发送中…" : "确认回写到 GitHub"}
        </button>
        <button
          type="button"
          onClick={onReset}
          disabled={phase === "posting"}
          className="rounded-md border border-neutral-700 px-3 py-1.5 text-xs text-neutral-300 transition hover:border-neutral-500 disabled:opacity-50"
        >
          取消
        </button>
      </div>
    </div>
  );
}
