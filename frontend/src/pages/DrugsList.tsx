import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { api } from '../api/client'

type TherapeuticAreaFilter = 'all' | 'ssri_snri' | 'statin'

const FILTER_LABEL: Record<TherapeuticAreaFilter, string> = {
  all: 'All',
  ssri_snri: 'SSRI / SNRI',
  statin: 'Statin',
}

function labelForArea(area: string): string {
  if (area === 'ssri_snri') return 'SSRI / SNRI'
  if (area === 'statin') return 'Statin'
  return area
}

export function DrugsList() {
  const [filter, setFilter] = useState<TherapeuticAreaFilter>('all')

  const { data, isLoading, error } = useQuery({
    queryKey: ['drugs', filter],
    queryFn: async () => {
      const { data, error } = await api.GET('/drugs', {
        params: {
          query: filter === 'all' ? {} : { therapeutic_area: filter },
        },
      })
      if (error) throw new Error('Failed to load drugs')
      return data
    },
  })

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold text-slate-900">Drugs</h2>
        <p className="text-sm text-slate-500">
          17 curated drugs across SSRIs/SNRIs and statins, with adverse-event report
          counts from openFDA.
        </p>
      </div>

      <div className="flex items-center gap-3">
        <label htmlFor="ta-filter" className="text-sm font-medium text-slate-700">
          Therapeutic area:
        </label>
        <select
          id="ta-filter"
          value={filter}
          onChange={(e) => setFilter(e.target.value as TherapeuticAreaFilter)}
          className="rounded border border-slate-300 bg-white px-2 py-1 text-sm shadow-sm"
        >
          {(Object.keys(FILTER_LABEL) as TherapeuticAreaFilter[]).map((key) => (
            <option key={key} value={key}>
              {FILTER_LABEL[key]}
            </option>
          ))}
        </select>
      </div>

      {isLoading && <p className="text-slate-500">Loading…</p>}

      {error && (
        <p className="text-red-600">Error loading drugs: {String(error)}</p>
      )}

      {data && (
        <div className="overflow-hidden rounded border border-slate-200 bg-white">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wider text-slate-500">
              <tr>
                <th className="px-4 py-2">Name</th>
                <th className="px-4 py-2">Therapeutic area</th>
                <th className="px-4 py-2 text-right">Reports</th>
              </tr>
            </thead>
            <tbody>
              {data.map((drug) => (
                <tr
                  key={drug.id}
                  className="border-b border-slate-100 last:border-0 hover:bg-slate-50"
                >
                  <td className="px-4 py-2">
                    <Link
                      to={`/drugs/${drug.id}`}
                      className="font-medium text-blue-600 hover:underline"
                    >
                      {drug.name}
                    </Link>
                  </td>
                  <td className="px-4 py-2 text-slate-600">
                    {labelForArea(drug.therapeutic_area)}
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums text-slate-700">
                    {drug.report_count.toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
