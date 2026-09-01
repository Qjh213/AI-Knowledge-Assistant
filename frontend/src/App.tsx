import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/layout/AppShell'
import { KnowledgeBaseDetailPage } from './pages/KnowledgeBaseDetailPage'
import { KnowledgeBasesPage } from './pages/KnowledgeBasesPage'
import { ConversationPage } from './pages/ConversationPage'
import { RecentConversationsPage } from './pages/RecentConversationsPage'

function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Navigate to="/knowledge-bases" replace />} />
        <Route path="/knowledge-bases" element={<KnowledgeBasesPage />} />
        <Route path="/conversations" element={<RecentConversationsPage />} />
        <Route
          path="/knowledge-bases/:knowledgeBaseId"
          element={<KnowledgeBaseDetailPage />}
        />
        <Route
          path="/knowledge-bases/:knowledgeBaseId/conversations/:conversationId"
          element={<ConversationPage />}
        />
      </Route>
    </Routes>
  )
}

export default App
