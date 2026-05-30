"use client";

import { useMemo, useState } from "react";
import type { RiskItem, RiskSeverity } from "@/lib/types";
import {
  CATEGORY_LABEL,
  SEVERITIES,
  SEVERITY_DOT,
  SEVERITY_LABEL,
  SEVERITY_ORDER,
} from "@/lib/risk";

type Filter = RiskSeverity | "all";

interface Props {
  risks: RiskItem[];
  // 风险分析是否仍在进行（总结已出但风险未到）
  loading?: boolean;
  // 点击某条风险时回调，由父级负责滚动并高亮对应 diff 行
  onLocate?: (risk: RiskItem) => void;
}

export function RiskOverview({ risks, loading = false, onLocate }: Props) {
  const [filter, setFilter] = useState<Filter>("all");

  const sevCounts = useMemo(() => countBy(risks, (r) => r.severity), [risks]);
  const catCounts = useMemo(() => countBy(risks, (r) => r.category), [risks]);

  const visible = useMemo(() => {
    const list = filter === "all" ? risks : risks.filter((r) => r.severity === filter);
    return [...list].sort(
      (a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity],
    );
  }, [risks, filter]);

  return (
    <section className="rounded-lg border border-neutral-800 bg-neutral-900/40 p-5">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-neutral-200">风险概览</h3>
        {loading && (
          <span className="flex items-center gap-1.5 text-xs text-neutral-400">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-blue-500" />
            分析中…
          </span>
        )}
      </div>

      {risks.length === 0 ? (
        <p className="mt-3 text-sm text-neutral-400">
          {loading ? "正在识别风险代码…" : "未发现明显风险。"}
        </p>
      ) : (
        <RiskBody
          risks={risks}
          visible={visible}
          filter={filter}
          setFilter={setFilter}
          sevCounts={sevCounts}
          catCounts={catCounts}
          onLocate={onLocate}
        />
      )}
    </section>
  );
}

function countBy<T extends string>(
  risks: RiskItem[],
  pick: (r: RiskItem) => T,
): Record<string, number> {
  const out: Record<string, number> = {};
  for (const r of risks) {
    const k = pick(r);
    out[k] = (out[k] ?? 0) + 1;
  }
  return out;
}

function RiskBody({
  risks,
  visible,
  filter,
  setFilter,
  sevCounts,
  catCounts,
  onLocate,
}: {
  risks: RiskItem[];
  visible: RiskItem[];
  filter: Filter;
  setFilter: (f: Filter) => void;
  sevCounts: Record<string, number>;
  catCounts: Record<string, number>;
  onLocate?: (risk: RiskItem) => void;
}) {
  return (
    <>
      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-neutral-400">
        {SEVERITIES.map((s) => (
          <span key={s} className="flex items-center gap-1.5">
            <span className={`h-2 w-2 rounded-full ${SEVERITY_DOT[s]}`} />
            {SEVERITY_LABEL[s]} {sevCounts[s] ?? 0}
          </span>
        ))}
        <span className="text-neutral-600">·</span>
        {Object.entries(catCounts).map(([cat, n]) => (
          <span key={cat}>
            {CATEGORY_LABEL[cat as keyof typeof CATEGORY_LABEL] ?? cat} {n}
          </span>
        ))}
      </div>

      <div className="mt-3 flex flex-wrap gap-1.5">
        <FilterTab active={filter === "all"} onClick={() => setFilter("all")}>
          全部 {risks.length}
        </FilterTab>
        {SEVERITIES.map((s) => (
          <FilterTab
            key={s}
            active={filter === s}
            disabled={(sevCounts[s] ?? 0) === 0}
            onClick={() => setFilter(s)}
          >
            {SEVERITY_LABEL[s]} {sevCounts[s] ?? 0}
          </FilterTab>
        ))}
      </div>

      <ul className="mt-3 divide-y divide-neutral-800/60">
        {visible.map((r, i) => (
          <RiskRow key={`${r.file}-${r.line}-${i}`} risk={r} onLocate={onLocate} />
        ))}
      </ul>
    </>
  );
}

function FilterTab({
  active,
  disabled = false,
  onClick,
  children,
}: {
  active: boolean;
  disabled?: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={`rounded-full border px-2.5 py-0.5 text-xs transition ${
        active
          ? "border-neutral-500 bg-neutral-700/60 text-neutral-100"
          : "border-neutral-700 text-neutral-400 hover:border-neutral-500 hover:text-neutral-200"
      } disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:border-neutral-700 disabled:hover:text-neutral-400`}
    >
      {children}
    </button>
  );
}

function RiskRow({
  risk,
  onLocate,
}: {
  risk: RiskItem;
  onLocate?: (risk: RiskItem) => void;
}) {
  const loc = risk.line != null ? `${risk.file}:${risk.line}` : risk.file;
  return (
    <li>
      <button
        type="button"
        onClick={() => onLocate?.(risk)}
        className="flex w-full items-center gap-2 py-1.5 text-left text-sm transition hover:bg-neutral-800/40"
      >
        <span className={`h-2 w-2 shrink-0 rounded-full ${SEVERITY_DOT[risk.severity]}`} />
        <span className="shrink-0 text-xs text-neutral-500">
          {SEVERITY_LABEL[risk.severity]}
        </span>
        <span className="truncate text-neutral-200">{risk.title}</span>
        <span className="ml-auto shrink-0 truncate font-mono text-xs text-neutral-500">
          {loc}
          <span className="ml-1 text-blue-400">→</span>
        </span>
      </button>
    </li>
  );
}
