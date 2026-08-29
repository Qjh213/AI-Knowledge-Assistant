import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/layout/AppShell'
import { KnowledgeBaseDetailPage } from './pages/KnowledgeBaseDetailPage'
import { KnowledgeBasesPage } from './pages/KnowledgeBasesPage'

function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Navigate to="/knowledge-bases" replace />} />
        <Route path="/knowledge-bases" element={<KnowledgeBasesPage />} />
        <Route
          path="/knowledge-bases/:knowledgeBaseId"
          element={<KnowledgeBaseDetailPage />}
        />
      </Route>
    </Routes>
  )
}

export default App
