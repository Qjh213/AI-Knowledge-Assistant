import { Navigate, Route, Routes } from 'react-router-dom'
import { lazy, Suspense } from 'react'
import { AppShell } from './components/layout/AppShell'
import { KnowledgeBaseDetailPage } from './pages/KnowledgeBaseDetailPage'
import { KnowledgeBasesPage } from './pages/KnowledgeBasesPage'
import { ConversationPage } from './pages/ConversationPage'
import { RecentConversationsPage } from './pages/RecentConversationsPage'
import { AuthProvider } from './auth/AuthProvider'
import { AuthGate } from './auth/AuthGate'
import { LoginPage } from './pages/LoginPage'
import { ChangePasswordPage } from './pages/ChangePasswordPage'
const AdminUsersPage = lazy(() => import('./pages/AdminUsersPage').then(module => ({ default: module.AdminUsersPage })))

function App() {
  return (
    <AuthProvider><Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/change-password" element={<ChangePasswordPage />} />
      <Route element={<AuthGate />}>
      <Route element={<AppShell />}>
        <Route element={<AuthGate adminOnly />}>
          <Route path="/admin/users" element={<Suspense fallback={<p>正在加载管理后台…</p>}><AdminUsersPage /></Suspense>} />
        </Route>
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
      </Route>
      <Route path="*" element={<Navigate to="/knowledge-bases" replace />} />
    </Routes></AuthProvider>
  )
}

export default App
