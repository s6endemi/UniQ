"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type {
  CodeEntry,
  ConfidenceLevel,
  MappingEntry,
  MappingUpdate,
  ReviewStatus,
} from "@/lib/api";

// ---------------------------------------------------------------
// Data adapter — map our API shape to the prototype's row shape.
// ---------------------------------------------------------------

type Tier = "high" | "med" | "low";

interface Row {
  id: string;              // our category name
  n: number;               // 1-based index
  category: string;        // display_label
  sample: string;          // raw category (UPPER_SNAKE_CASE)
  fhirType: string;        // fhir_resource_type
  code: string;            // formatted first code or placeholder
  conf: number;            // 0..1 — mapped from confidence level
  tier: Tier;
  raw: MappingEntry;       // keep original around for override editing
}

const CONFIDENCE_TO_NUMERIC: Record<ConfidenceLevel, number> = {
  high: 0.93,
  medium: 0.80,
  low: 0.60,
};
const CONFIDENCE_TO_TIER: Record<ConfidenceLevel, Tier> = {
  high: "high",
  medium: "med",
  low: "low",
};

function shortSystem(system: string): string {
  if (system.includes("loinc")) return "LOINC";
  if (system.includes("snomed")) return "SNOMED";
  if (system.includes("icd-10") || system.includes("icd10")) return "ICD-10";
  if (system.includes("rxnorm")) return "RxNorm";
  if (system.includes("whocc") || system.includes("atc")) return "ATC";
  return system.split("/").pop() ?? system;
}

function formatCode(codes: CodeEntry[]): string {
  if (!codes.length) return "— needs review";
  const c = codes[0];
  return `${shortSystem(c.system)} ${c.code}`;
}

function adaptEntry(entry: MappingEntry, index: number): Row {
  return {
    id: entry.category,
    n: index + 1,
    category: entry.display_label,
    sample: entry.category,
    fhirType: entry.fhir_resource_type,
    code: formatCode(entry.codes),
    conf: CONFIDENCE_TO_NUMERIC[entry.confidence],
    tier: CONFIDENCE_TO_TIER[entry.confidence],
    raw: entry,
  };
}

// ---------------------------------------------------------------
// API wiring
// ---------------------------------------------------------------

async function fetchMapping(): Promise<MappingEntry[]> {
  const res = await fetch("/api/uniq/mapping");
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? `mapping unreachable (${res.status})`);
  }
  return res.json();
}

async function patchMapping(
  category: string,
  update: MappingUpdate,
): Promise<MappingEntry> {
  const res = await fetch(`/api/uniq/mapping/${encodeURIComponent(category)}`, {
    method: "PATCH",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(update),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? `PATCH failed: ${res.status}`);
  }
  return res.json();
}

// ---------------------------------------------------------------
// Primitives
// ---------------------------------------------------------------

function ConfBar({ conf }: { conf: number }) {
  const cls = conf >= 0.9 ? "" : conf >= 0.7 ? "conf-bar--med" : "conf-bar--low";
  return (
    <div className={`conf-bar ${cls}`}>
      <div className="conf-bar__fill" style={{ width: `${Math.round(conf * 100)}%` }} />
    </div>
  );
}

interface EditorProps {
  row: Row;
  onSave: (update: MappingUpdate) => void;
  onCancel: () => void;
  saving: boolean;
}

function Editor({ row, onSave, onCancel, saving }: EditorProps) {
  const [category, setCategory] = useState(row.category);
  const [fhirType, setFhirType] = useState(row.fhirType);
  const [code, setCode] = useState(row.code);
  const [note, setNote] = useState("");
  const firstRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    firstRef.current?.focus();
  }, []);

  const submit = () => {
    const update: MappingUpdate = { review_status: "overridden" };
    if (category !== row.category) update.display_label = category;
    if (fhirType !== row.fhirType) update.fhir_resource_type = fhirType;
    if (note.trim()) update.reasoning = note.trim();
    onSave(update);
  };

  return (
    <div className="editor">
      <div
        className="t-meta"
        style={{
          marginBottom: 12,
          letterSpacing: "0.12em",
          textTransform: "uppercase",
        }}
      >
        Override · edit the AI&apos;s proposal
      </div>
      <div className="editor__grid">
        <div className="editor__field">
          <label>Display label</label>
          <input
            ref={firstRef}
            value={category}
            onChange={(e) => setCategory(e.target.value)}
          />
        </div>
        <div className="editor__field">
          <label>FHIR resource type</label>
          <input value={fhirType} onChange={(e) => setFhirType(e.target.value)} />
        </div>
        <div className="editor__field">
          <label>Medical code (read-only for now)</label>
          <input value={code} disabled onChange={(e) => setCode(e.target.value)} />
        </div>
        <div className="editor__field">
          <label>Reviewer note</label>
          <input
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Optional — becomes the new reasoning"
          />
        </div>
      </div>
      <div className="editor__actions">
        <button className="editor__btn editor__btn--cancel" onClick={onCancel}>
          Cancel
        </button>
        <button
          className="editor__btn editor__btn--save"
          onClick={submit}
          disabled={saving}
        >
          {saving ? "Saving…" : "Save override"}
        </button>
      </div>
    </div>
  );
}

interface RowProps {
  row: Row;
  status: ReviewStatus;
  focused: boolean;
  editing: boolean;
  saving: boolean;
  onFocus: () => void;
  onAction: (action: "approve" | "override" | "reject") => void;
  onSaveEdit: (update: MappingUpdate) => void;
  onCancelEdit: () => void;
}

function MappingRow({
  row,
  status,
  focused,
  editing,
  saving,
  onFocus,
  onAction,
  onSaveEdit,
  onCancelEdit,
}: RowProps) {
  const stampLabel =
    status === "approved"
      ? "Approved"
      : status === "overridden"
        ? "Overridden"
        : status === "rejected"
          ? "Rejected"
          : "Pending";
  const stampCls =
    status === "overridden"
      ? "stamp--override"
      : status === "rejected"
        ? "stamp--reject"
        : "";
  const stampVisible = status !== "pending";

  return (
    <>
      <div
        className="mapping-row"
        data-status={status}
        data-focused={focused}
        onClick={onFocus}
      >
        <div className="mapping-row__idx">{String(row.n).padStart(2, "0")}</div>
        <div className="mapping-row__cat">
          <span className="mapping-row__cat-name">{row.category}</span>
          <span className="mapping-row__cat-sample">source · {row.sample}</span>
        </div>
        <div className="mapping-row__fhir">
          <span className="mapping-row__fhir-type">{row.fhirType}</span>
          <span className="mapping-row__fhir-code">{row.code}</span>
        </div>
        <div>
          <div className="mapping-row__conf">{Math.round(row.conf * 100)}</div>
          <ConfBar conf={row.conf} />
        </div>
        <div
          className="mapping-row__actions"
          onClick={(e) => e.stopPropagation()}
        >
          <button
            className="is-approve"
            onClick={() => onAction("approve")}
            disabled={saving}
          >
            Approve
          </button>
          <button
            className="is-override"
            onClick={() => onAction("override")}
            disabled={saving}
          >
            Override
          </button>
          <button
            className="is-reject"
            onClick={() => onAction("reject")}
            disabled={saving}
          >
            Reject
          </button>
        </div>
        <div
          className={`stamp ${stampCls} ${stampVisible ? "is-visible" : ""}`}
          aria-hidden={!stampVisible}
        >
          {stampLabel}
        </div>
      </div>
      {editing && (
        <Editor
          row={row}
          onSave={onSaveEdit}
          onCancel={onCancelEdit}
          saving={saving}
        />
      )}
    </>
  );
}

// ---------------------------------------------------------------
// Page
// ---------------------------------------------------------------

type StatusFilter = "all" | ReviewStatus;

export default function ReviewPage() {
  const qc = useQueryClient();
  const { data, isLoading, error } = useQuery({
    queryKey: ["mapping"],
    queryFn: fetchMapping,
  });

  const rows: Row[] = useMemo(
    () => (data ? data.map((e, i) => adaptEntry(e, i)) : []),
    [data],
  );

  const [filter, setFilter] = useState<StatusFilter>("all");
  const [focusId, setFocusId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);

  const patchMutation = useMutation({
    mutationFn: ({ id, update }: { id: string; update: MappingUpdate }) =>
      patchMapping(id, update),
    onSuccess: (updated) => {
      qc.setQueryData<MappingEntry[]>(["mapping"], (old) =>
        old ? old.map((e) => (e.category === updated.category ? updated : e)) : old,
      );
      setEditingId(null);
    },
  });

  const currentStatus = (id: string): ReviewStatus => {
    const found = data?.find((e) => e.category === id);
    return found?.review_status ?? "pending";
  };

  const act = (id: string, action: "approve" | "override" | "reject") => {
    if (action === "override") {
      setEditingId(id);
      return;
    }
    const update: MappingUpdate = {
      review_status: action === "approve" ? "approved" : "rejected",
    };
    patchMutation.mutate({ id, update });
  };

  const moveFocus = (dir: 1 | -1) => {
    if (!rows.length) return;
    const idx = rows.findIndex((r) => r.id === focusId);
    const nextIdx = idx < 0 ? 0 : Math.max(0, Math.min(rows.length - 1, idx + dir));
    setFocusId(rows[nextIdx].id);
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (target && target.matches("input, textarea")) return;
      if (!focusId) return;
      const k = e.key.toLowerCase();
      if (k === "a") {
        e.preventDefault();
        act(focusId, "approve");
      } else if (k === "o") {
        e.preventDefault();
        act(focusId, "override");
      } else if (k === "r") {
        e.preventDefault();
        act(focusId, "reject");
      } else if (k === "j" || e.key === "ArrowDown") {
        e.preventDefault();
        moveFocus(1);
      } else if (k === "k" || e.key === "ArrowUp") {
        e.preventDefault();
        moveFocus(-1);
      } else if (e.key === "Escape") {
        setEditingId(null);
        setFocusId(null);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusId, rows.length]);

  const counts = useMemo(() => {
    const statuses = data?.map((e) => e.review_status) ?? [];
    return {
      all: rows.length,
      pending: statuses.filter((s) => s === "pending").length,
      approved: statuses.filter((s) => s === "approved").length,
      overridden: statuses.filter((s) => s === "overridden").length,
      rejected: statuses.filter((s) => s === "rejected").length,
    };
  }, [rows.length, data]);

  const reviewed = counts.all - counts.pending;
  const pct = counts.all ? Math.round((reviewed / counts.all) * 100) : 0;

  const filtered = useMemo(() => {
    if (filter === "all") return rows;
    return rows.filter((r) => currentStatus(r.id) === filter);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, filter, data]);

  const tiers: Array<{ id: Tier; label: string; sub: string }> = [
    { id: "high", label: "High confidence", sub: "≥ 90%" },
    { id: "med", label: "Medium confidence", sub: "70 – 89%" },
    { id: "low", label: "Low confidence", sub: "< 70%" },
  ];

  const filters: Array<{ id: StatusFilter; label: string }> = [
    { id: "all", label: "All" },
    { id: "pending", label: "Pending" },
    { id: "approved", label: "Approved" },
    { id: "overridden", label: "Overridden" },
    { id: "rejected", label: "Rejected" },
  ];

  return (
    <div className="room" data-screen-label="02 Review">
      <div className="container container--wide review">
        <div className="review__head">
          <div>
            <div className="t-eyebrow">Human-in-the-loop · pipeline run 0612</div>
            <h1 className="review__title">
              Twenty proposals, <em>one hand</em> on the pen.
            </h1>
            <p className="review__subtitle">
              Each entry below is a mapping the AI proposes from raw source fields
              to a FHIR resource and medical code. You are the clinical authority.
              Nothing ships until you say so.
            </p>
          </div>
          <div className="review__progress">
            <div>
              {reviewed} OF {counts.all} REVIEWED · {pct}%
            </div>
            <div className="review__progress-bar">
              <div
                className="review__progress-fill"
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
        </div>

        <div className="review__filters">
          {filters.map((f) => (
            <button
              key={f.id}
              className="review__filter"
              aria-pressed={filter === f.id}
              onClick={() => setFilter(f.id)}
            >
              {f.label} <span className="count">{counts[f.id]}</span>
            </button>
          ))}
          <div className="review__shortcuts">
            <span>
              <span className="kbd">A</span> approve
            </span>
            <span>
              <span className="kbd">O</span> override
            </span>
            <span>
              <span className="kbd">R</span> reject
            </span>
            <span>
              <span className="kbd">↑↓</span> move
            </span>
          </div>
        </div>

        {isLoading && (
          <div style={{ padding: "64px 0", textAlign: "center" }}>
            <div className="t-meta">loading mappings…</div>
          </div>
        )}

        {error && (
          <div
            style={{
              padding: "24px",
              marginTop: 24,
              border: "1px solid var(--alert)",
              background: "var(--alert-wash)",
              color: "var(--alert)",
              fontFamily: "var(--f-mono)",
              fontSize: 13,
            }}
          >
            {(error as Error).message}
          </div>
        )}

        {patchMutation.error && (
          <div
            style={{
              padding: "12px 24px",
              marginTop: 16,
              border: "1px solid var(--alert)",
              background: "var(--alert-wash)",
              color: "var(--alert)",
              fontFamily: "var(--f-mono)",
              fontSize: 12,
            }}
          >
            {(patchMutation.error as Error).message}
          </div>
        )}

        {data &&
          tiers.map((tier) => {
            const tierRows = filtered.filter((r) => r.tier === tier.id);
            if (!tierRows.length) return null;
            return (
              <div className="mapping-group" key={tier.id}>
                <div className="mapping-group__title">
                  <h3>{tier.label}</h3>
                  <span className="t-meta">
                    {tier.sub} · {tierRows.length}{" "}
                    {tierRows.length === 1 ? "entry" : "entries"}
                  </span>
                </div>
                {tierRows.map((row) => (
                  <MappingRow
                    key={row.id}
                    row={row}
                    status={currentStatus(row.id)}
                    focused={focusId === row.id}
                    editing={editingId === row.id}
                    saving={
                      patchMutation.isPending &&
                      patchMutation.variables?.id === row.id
                    }
                    onFocus={() => setFocusId(row.id)}
                    onAction={(a) => {
                      setFocusId(row.id);
                      act(row.id, a);
                    }}
                    onSaveEdit={(update) =>
                      patchMutation.mutate({ id: row.id, update })
                    }
                    onCancelEdit={() => setEditingId(null)}
                  />
                ))}
              </div>
            );
          })}

        {data && filtered.length === 0 && (
          <div style={{ padding: "48px 0", textAlign: "center" }}>
            <div className="t-meta">No mappings in this filter.</div>
          </div>
        )}
      </div>
    </div>
  );
}
