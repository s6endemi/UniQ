"use client";

import type { TableData } from "@/lib/api";

/**
 * TableData renderer — the one shared table layout for every artifact
 * kind. Alignment comes from the column metadata, not inferred here;
 * the backend's builder decides numeric → right, string → left. That
 * keeps visual rhythm consistent whether the table is the centrepiece
 * of a `table` artifact or the supporting table under a cohort chart.
 *
 * Cells render empty on null / undefined so a gappy result shows gaps
 * rather than a sea of "null".
 */
export function ArtifactTable({ data }: { data: TableData }) {
  if (data.rows.length === 0) {
    return (
      <div className="cohort-table__empty">
        <span>No rows</span>
      </div>
    );
  }

  return (
    <table className="cohort-table">
      <thead>
        <tr>
          {data.columns.map((c) => (
            <th
              key={c.key}
              style={{ textAlign: c.align === "right" ? "right" : "left" }}
            >
              {c.label}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {data.rows.map((row, i) => (
          <tr key={i}>
            {data.columns.map((c) => {
              const v = row[c.key];
              const display =
                v === null || v === undefined
                  ? ""
                  : typeof v === "number"
                    ? Number.isInteger(v)
                      ? v.toLocaleString()
                      : v.toFixed(2)
                    : String(v);
              return (
                <td
                  key={c.key}
                  style={{
                    textAlign: c.align === "right" ? "right" : "left",
                    color: c.emphasis ? "var(--signal-ink)" : undefined,
                  }}
                >
                  {display}
                </td>
              );
            })}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
