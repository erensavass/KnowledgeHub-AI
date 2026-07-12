import { Navigate, Route, Routes } from 'react-router-dom'
import { AuthPage } from './features/auth/AuthPage'
import { ProtectedRoute } from './routes/ProtectedRoute'
import { AppLayout } from './layouts/AppLayout'
import { HomePage } from './pages/HomePage'
import { DocumentsPage } from './features/documents/DocumentsPage'
import { ConversationPage } from './features/chat/ConversationPage'
import { SearchPage } from './features/documents/SearchPage'

export function App() { return <Routes>
  <Route path="/login" element={<AuthPage mode="login" />} />
  <Route path="/register" element={<AuthPage mode="register" />} />
  <Route element={<ProtectedRoute />}><Route element={<AppLayout />}>
    <Route index element={<HomePage />} />
    <Route path="library" element={<DocumentsPage />} />
    <Route path="semantic-search" element={<SearchPage />} />
    <Route path="chat/:conversationId" element={<ConversationPage />} />
  </Route></Route>
  <Route path="*" element={<Navigate to="/" replace />} />
</Routes> }
