"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import AppShell from "@/components/AppShell";
import { Button, Card, ErrorMessage, PageTitle, PriorityBadge, TableWrap, Td, Th } from "@/components/ui";
import { upload } from "@/lib/api";
import { formatDateTime, label } from "@/lib/format";
import type { ImportPreview, ImportResult } from "@/lib/types";

export default function ImportPage() {
  return (
    <AppShell>
      <Import />
    </AppShell>
  );
}

function Issues({ title, items }: { title: string; items: { row: number; message: string }[] }) {
  if (!items.length) return null;
  return (
    <div className="mt-4">
      <p className="text-xs font-semibold uppercase text-slate-500">{title}</p>
      <ul className="mt-1 space-y-1 text-sm text-amber-800" data-testid="skipped-rows">
        {items.map((s) => (
          <li key={`${s.row}-${s.message}`}>
            Row {s.row}: {s.message}
          </li>
        ))}
      </ul>
    </div>
  );
}

function Import() {
  const queryClient = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const run = async (action: "preview" | "import") => {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      if (action === "preview") {
        setPreview(await upload<ImportPreview>("/imports/jsm/preview", file));
        setResult(null);
      } else {
        setResult(await upload<ImportResult>("/imports/jsm", file));
        await queryClient.invalidateQueries();
      }
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };

  const loadSample = async () => {
    const response = await fetch("/jsm_export_sample.csv");
    const sample = new File([await response.blob()], "jsm_export_sample.csv", { type: "text/csv" });
    setFile(sample);
    setPreview(null);
    setResult(null);
  };

  return (
    <>
      <PageTitle
        title="Import from Jira Service Management"
        subtitle="Upload a CSV export from Jira (Filters → Export → Export CSV, all fields). The import is safe to repeat: tickets are matched by their issue key and updated instead of duplicated. SLA times are calculated by ServiceQualityHub's own engine, so every source is measured the same way."
      />
      <Card title="1. Choose a file">
        <div className="flex flex-wrap items-center gap-3">
          <input
            type="file"
            accept=".csv,text/csv"
            data-testid="csv-input"
            onChange={(e) => {
              setFile(e.target.files?.[0] ?? null);
              setPreview(null);
              setResult(null);
            }}
            className="text-sm"
          />
          <Button onClick={loadSample} data-testid="use-sample">
            Use the sample export
          </Button>
          <a href="/jsm_export_sample.csv" download className="text-sm text-brand-700 hover:underline">
            Download the sample CSV
          </a>
        </div>
        {file && <p className="mt-2 text-sm text-slate-600">Selected: {file.name}</p>}
        <p className="mt-2 text-xs text-slate-500">
          Max 5 MB. Comma or semicolon, UTF-8 or Windows encoding (Excel). Dates are read in Europe/Vienna time.
        </p>
        <div className="mt-4 flex gap-2">
          <Button variant="primary" disabled={!file || busy} onClick={() => run("preview")} data-testid="preview">
            Preview
          </Button>
          <Button disabled={!file || !preview || busy} onClick={() => run("import")} data-testid="import">
            Import {preview ? `${preview.valid_rows} rows` : ""}
          </Button>
        </div>
        <div className="mt-3">
          <ErrorMessage error={error} />
        </div>
      </Card>

      {result && (
        <Card className="mt-6" title="3. Import result">
          <p className="text-sm" data-testid="import-result">
            <strong>{result.created}</strong> created · <strong>{result.updated}</strong> updated ·{" "}
            <strong>{result.skipped.length}</strong> skipped
          </p>
          <Issues title="Skipped rows" items={result.skipped} />
        </Card>
      )}

      {preview && (
        <Card
          className="mt-6"
          title={`2. Preview – ${preview.valid_rows} of ${preview.total_rows} rows can be imported`}
        >
          <dl className="mb-4 grid gap-x-6 gap-y-1 text-xs sm:grid-cols-2">
            {Object.entries(preview.detected).map(([k, v]) => (
              <div key={k} className="flex gap-2">
                <dt className="text-slate-500">{k}:</dt>
                <dd className="text-slate-700">{v}</dd>
              </div>
            ))}
          </dl>
          <TableWrap>
            <thead className="bg-slate-50">
              <tr>
                <Th>Row</Th>
                <Th>Key</Th>
                <Th>Type</Th>
                <Th>Plant</Th>
                <Th>Service</Th>
                <Th>Priority</Th>
                <Th>Status</Th>
                <Th>Created</Th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100" data-testid="preview-table">
              {preview.rows.map((r) => (
                <tr key={r.key}>
                  <Td className="text-xs text-slate-400">{r.row}</Td>
                  <Td className="font-medium">
                    {r.key}
                    <span className="block max-w-xs text-xs font-normal text-slate-500">{r.title}</span>
                  </Td>
                  <Td className="text-xs">{label(r.type)}</Td>
                  <Td>{r.plant_code}</Td>
                  <Td className="text-xs">{r.service_name}</Td>
                  <Td>
                    <PriorityBadge priority={r.priority} />
                  </Td>
                  <Td className="text-xs">{r.status}</Td>
                  <Td className="whitespace-nowrap text-xs">{formatDateTime(r.created_at)}</Td>
                </tr>
              ))}
            </tbody>
          </TableWrap>
          <Issues title="Rows that will be skipped" items={preview.skipped} />
          {preview.warnings.length > 0 && (
            <ul className="mt-4 list-disc pl-5 text-xs text-slate-500">
              {preview.warnings.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
          )}
        </Card>
      )}
    </>
  );
}
