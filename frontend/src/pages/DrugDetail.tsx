import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { api } from '../api/client'

const BAR_COLOR = '#2563eb' // tailwind blue-600

function truncate(text: string, max: number): string {
  return text.length > max ? text.slice(0, max - 1) + '…' : text
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

function labelForArea(area: string): string {
  if (area === 'ssri_snri') return 'SSRI / SNRI'
  if (area === 'statin') return 'Statin'
  return area
}

export function DrugDetail() {
  const { id } = useParams<{ id: string }>()
  const drugId = id ? parseInt(id, 10) : NaN

  const [minPrr, setMinPrr] = useState(2.0)
  const [minCount, setMinCount] = useState(3)
  const [limit, setLimit] = useState(10)

  const drugQuery = useQuery({
    queryKey: ['drug', drugId],
    queryFn: async () => {
      const { data, error } = await api.GET('/drugs/{drug_id}', {
        params: { path: { drug_id: drugId } },
      })
      if (error) throw new Error('Drug not found')
      return data
    },
    enabled: !isNaN(drugId),
  })

  const signalsQuery = useQuery({
    queryKey: ['signals', drugId, minPrr, minCount, limit],
    queryFn: async () => {
      const { data, error } = await api.GET('/drugs/{drug_id}/signals', {
        params: {
          path: { drug_id: drugId },
          query: { min_prr: minPrr, min_count: minCount, limit },
        },
      })
      if (error) throw new Error('Failed to load signals')
      return data
    },
    enabled: !isNaN(drugId),
  })

  if (isNaN(drugId)) {
    return <p className="text-red-600">Invalid drug ID in URL.</p>
  }

  // Pre-flatten signal data so Recharts can use ae_label as the YAxis dataKey
  // (Recharts dataKey doesn't traverse nested objects).
  const chartData = signalsQuery.data?.map((s) => ({
    ...s,
    ae_label: truncate(s.ae.meddra_pt, 35),
  }))

  return (
    <div className="space-y-6">
      <Link to="/" className="text-sm text-blue-600 hover:underline">
        ← Back to drugs
      </Link>

      {/* Header */}
      {drugQuery.isLoading && <p className="text-slate-500">Loading drug…</p>}
      {drugQuery.error && (
        <p className="text-red-600">Error: {String(drugQuery.error)}</p>
      )}
      {drugQuery.data && (
        <div>
          <h2 className="text-3xl font-semibold capitalize text-slate-900">
            {drugQuery.data.name}
          </h2>
          <div className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-sm text-slate-600">
            <span>
              <span className="text-slate-400">Class:</span>{' '}
              {labelForArea(drugQuery.data.therapeutic_area)}
            </span>
            <span>
              <span className="text-slate-400">Reports:</span>{' '}
              {drugQuery.data.report_count.toLocaleString()}
            </span>
            <span>
              <span className="text-slate-400">Date range:</span>{' '}
              {formatDate(drugQuery.data.first_report_date)} –{' '}
              {formatDate(drugQuery.data.last_report_date)}
            </span>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="rounded border border-slate-200 bg-white p-4">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div>
            <label className="block text-xs font-medium text-slate-700">
              Min PRR: <span className="font-semibold">{minPrr.toFixed(1)}</span>
            </label>
            <input
              type="range"
              min="0"
              max="10"
              step="0.5"
              value={minPrr}
              onChange={(e) => setMinPrr(parseFloat(e.target.value))}
              className="mt-1 w-full"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-700">
              Min reports: <span className="font-semibold">{minCount}</span>
            </label>
            <input
              type="range"
              min="1"
              max="50"
              step="1"
              value={minCount}
              onChange={(e) => setMinCount(parseInt(e.target.value, 10))}
              className="mt-1 w-full"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-700">
              Show top
            </label>
            <select
              value={limit}
              onChange={(e) => setLimit(parseInt(e.target.value, 10))}
              className="mt-1 w-full rounded border border-slate-300 bg-white px-2 py-1 text-sm"
            >
              {[10, 25, 50, 100].map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Signals chart */}
      {signalsQuery.isLoading && (
        <p className="text-slate-500">Loading signals…</p>
      )}
      {signalsQuery.error && (
        <p className="text-red-600">Error: {String(signalsQuery.error)}</p>
      )}
      {chartData && chartData.length === 0 && (
        <div className="rounded border border-slate-200 bg-white p-6 text-center text-slate-500">
          No signals match these thresholds. Try lowering Min PRR or Min reports.
        </div>
      )}
      {chartData && chartData.length > 0 && (
        <>
          <div className="rounded border border-slate-200 bg-white p-4">
            <h3 className="mb-1 text-lg font-medium text-slate-900">
              Top {chartData.length} signals by PRR
            </h3>
            <p className="mb-3 text-xs text-slate-500">
              Adverse events disproportionately reported with this drug compared to
              all other drugs in the database. Hover a bar for the contingency table.
            </p>
            <ResponsiveContainer
              width="100%"
              height={Math.max(300, chartData.length * 32)}
            >
              <BarChart
                layout="vertical"
                data={chartData}
                margin={{ top: 5, right: 30, left: 0, bottom: 5 }}
              >
                <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                <XAxis
                  type="number"
                  tick={{ fontSize: 12 }}
                  label={{
                    value: 'PRR',
                    position: 'insideBottom',
                    offset: -2,
                    style: { fontSize: 12, fill: '#64748b' },
                  }}
                />
                <YAxis
                  type="category"
                  dataKey="ae_label"
                  tick={{ fontSize: 12 }}
                  width={220}
                  interval={0}
                />
                <Tooltip
                  cursor={{ fill: '#f1f5f9' }}
                  content={({ active, payload }) => {
                    if (!active || !payload?.length) return null
                    const s = payload[0].payload as (typeof chartData)[number]
                    return (
                      <div className="rounded border border-slate-200 bg-white p-3 text-xs shadow-md">
                        <div className="font-medium text-slate-900">
                          {s.ae.meddra_pt}
                        </div>
                        <div className="mt-1 text-slate-600">
                          PRR:{' '}
                          <span className="font-semibold text-slate-900">
                            {s.prr.toFixed(2)}
                          </span>
                          {' · '}
                          Reports:{' '}
                          <span className="font-semibold text-slate-900">
                            {s.report_count}
                          </span>
                        </div>
                        <div className="mt-2 grid grid-cols-2 gap-x-3 gap-y-0.5 text-slate-500">
                          <div>
                            a (drug + AE):{' '}
                            <span className="tabular-nums text-slate-700">
                              {s.contingency.a.toLocaleString()}
                            </span>
                          </div>
                          <div>
                            b (drug + other):{' '}
                            <span className="tabular-nums text-slate-700">
                              {s.contingency.b.toLocaleString()}
                            </span>
                          </div>
                          <div>
                            c (others + AE):{' '}
                            <span className="tabular-nums text-slate-700">
                              {s.contingency.c.toLocaleString()}
                            </span>
                          </div>
                          <div>
                            d (others + other):{' '}
                            <span className="tabular-nums text-slate-700">
                              {s.contingency.d.toLocaleString()}
                            </span>
                          </div>
                        </div>
                      </div>
                    )
                  }}
                />
                <Bar dataKey="prr" fill={BAR_COLOR} radius={[0, 3, 3, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Signals table */}
          <div className="overflow-hidden rounded border border-slate-200 bg-white">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="px-4 py-2">Adverse event</th>
                  <th className="px-4 py-2 text-right">PRR</th>
                  <th className="px-4 py-2 text-right">Reports (a)</th>
                  <th className="px-4 py-2 text-right">Drug + other (b)</th>
                  <th className="px-4 py-2 text-right">Other + AE (c)</th>
                </tr>
              </thead>
              <tbody>
                {chartData.map((s, i) => (
                  <tr
                    key={i}
                    className="border-b border-slate-100 last:border-0 hover:bg-slate-50"
                  >
                    <td className="px-4 py-2 text-slate-900">{s.ae.meddra_pt}</td>
                    <td className="px-4 py-2 text-right tabular-nums font-semibold text-slate-900">
                      {s.prr.toFixed(2)}
                    </td>
                    <td className="px-4 py-2 text-right tabular-nums text-slate-700">
                      {s.contingency.a.toLocaleString()}
                    </td>
                    <td className="px-4 py-2 text-right tabular-nums text-slate-500">
                      {s.contingency.b.toLocaleString()}
                    </td>
                    <td className="px-4 py-2 text-right tabular-nums text-slate-500">
                      {s.contingency.c.toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}
