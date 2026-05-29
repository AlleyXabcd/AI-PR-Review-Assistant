import type { FileChange, SummaryResponse } from "@/lib/types";

function statusColor(status: string): string {
  switch (status) {
    case "added":
      return "text-green-400";
    case "removed":
      return "text-red-400";
    case "renamed":
      return "text-purple-400";
    default:
      return "text-yellow-400";
  }
}

function FileRow({ f }: { f: FileChange }) {
  return (
    <li className="flex items-center justify-between gap-3 py-1 text-sm">
      <span className="truncate">
        <span className={`mr-2 uppercase ${statusColor(f.status)}`}>
          {f.status.slice(0, 3)}
        </span>
        <span className="text-neutral-300">{f.filename}</span>
      </span>
      <span className="shrink-0 font-mono text-xs">
        <span className="text-green-400">+{f.additions}</span>{" "}
        <span className="text-red-400">-{f.deletions}</span>
      </span>
    </li>
  );
}

export function SummaryView({ data }: { data: SummaryResponse }) {
  const { summary } = data;
  return (
    <div className="space-y-6">
      <section className="rounded-lg border border-neutral-800 bg-neutral-900/40 p-5">
        <div className="flex items-start justify-between gap-4">
          <h2 className="text-lg font-semibold">{data.title}</h2>
          <a
            href={data.html_url}
            target="_blank"
            rel="noreferrer"
            className="shrink-0 text-xs text-blue-400 hover:underline"
          >
            在 GitHub 查看 ↗
          </a>
        </div>
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-neutral-400">
          <span>作者 {data.author ?? "未知"}</span>
          <span>状态 {data.state}</span>
          <span>
            {data.head_branch} → {data.base_branch}
          </span>
          <span>
            <span className="text-green-400">+{data.additions}</span>{" "}
            <span className="text-red-400">-{data.deletions}</span> · {data.changed_files} 个文件
          </span>
        </div>
      </section>

      <section className="rounded-lg border border-neutral-800 bg-neutral-900/40 p-5">
        <h3 className="mb-2 text-sm font-semibold text-neutral-200">变更概述</h3>
        <p className="text-sm leading-relaxed text-neutral-300">
          {summary.overview || "（无）"}
        </p>

        {summary.key_changes.length > 0 && (
          <>
            <h3 className="mb-2 mt-4 text-sm font-semibold text-neutral-200">
              关键改动
            </h3>
            <ul className="list-disc space-y-1 pl-5 text-sm text-neutral-300">
              {summary.key_changes.map((k, i) => (
                <li key={i}>{k}</li>
              ))}
            </ul>
          </>
        )}

        {summary.impact && (
          <>
            <h3 className="mb-2 mt-4 text-sm font-semibold text-neutral-200">
              影响与关注点
            </h3>
            <p className="text-sm leading-relaxed text-neutral-300">
              {summary.impact}
            </p>
          </>
        )}
      </section>

      <section className="rounded-lg border border-neutral-800 bg-neutral-900/40 p-5">
        <h3 className="mb-2 text-sm font-semibold text-neutral-200">
          变更文件（{data.files.length}）
        </h3>
        <ul className="divide-y divide-neutral-800/60">
          {data.files.map((f) => (
            <FileRow key={f.filename} f={f} />
          ))}
        </ul>
      </section>

      <p className="text-right text-xs text-neutral-500">
        模型 {data.model} · 用量 {data.usage.total_tokens} tokens
      </p>
    </div>
  );
}
