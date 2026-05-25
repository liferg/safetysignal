import { Link, Route, Routes } from 'react-router-dom'

import { DrugDetail } from './pages/DrugDetail'
import { DrugsList } from './pages/DrugsList'

function App() {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto max-w-6xl px-6 py-4">
          <Link to="/" className="text-xl font-semibold hover:text-blue-600">
            SafetySignal
          </Link>
          <p className="text-sm text-slate-500">
            Pharmacovigilance signal explorer ·{' '}
            <span className="italic">demo project, not for clinical use</span>
          </p>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-8">
        <Routes>
          <Route path="/" element={<DrugsList />} />
          <Route path="/drugs/:id" element={<DrugDetail />} />
        </Routes>
      </main>
    </div>
  )
}

export default App
