import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { vi } from 'vitest'
import { AuthProvider, useAuth } from '../src/features/auth/AuthProvider'
import { AuthPage } from '../src/features/auth/AuthPage'
import { ProtectedRoute } from '../src/routes/ProtectedRoute'
import { apiRequest } from '../src/api/client'
import { setAccessToken } from '../src/stores/auth-token'
import { renderWithProviders, jsonResponse } from './test-utils'

const user = { id: 'u1', email: 'person@example.com', is_active: true, created_at: '2026-01-01T00:00:00Z' }
function RoutesUnderTest() { return <AuthProvider><Routes><Route path="/login" element={<AuthPage mode="login" />} /><Route path="/register" element={<AuthPage mode="register" />} /><Route element={<ProtectedRoute />}><Route path="/" element={<Dashboard />} /></Route></Routes></AuthProvider> }
function Dashboard() { const auth = useAuth(); return <><h1>Dashboard</h1><span>{auth.user?.email}</span><button onClick={auth.logout}>Logout</button></> }

test('protected routes wait for restoration and redirect without credentials', async () => {
  renderWithProviders(<RoutesUnderTest />)
  expect(await screen.findByRole('heading', { name: 'Welcome back' })).toBeInTheDocument()
  expect(screen.queryByText('Dashboard')).not.toBeInTheDocument()
})

test('restores the current user through auth me before rendering protected content', async () => {
  setAccessToken('token')
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse(user))
  renderWithProviders(<RoutesUnderTest />)
  expect(screen.getByRole('status')).toHaveTextContent('Restoring')
  expect(await screen.findByText('person@example.com')).toBeInTheDocument()
})

test('logs in and logs out without exposing the token', async () => {
  const fetch = vi.spyOn(globalThis, 'fetch')
    .mockResolvedValueOnce(jsonResponse({ access_token: 'private-token', token_type: 'bearer' }))
    .mockResolvedValueOnce(jsonResponse(user))
  renderWithProviders(<RoutesUnderTest />)
  const actor = userEvent.setup()
  await actor.type(await screen.findByLabelText('Email'), user.email)
  await actor.type(screen.getByLabelText('Password'), 'Password123!')
  await actor.click(screen.getByRole('button', { name: 'Log in' }))
  expect(await screen.findByText('Dashboard')).toBeInTheDocument()
  expect(fetch.mock.calls.flat().join(' ')).not.toContain('private-token')
  await actor.click(screen.getByRole('button', { name: 'Logout' }))
  await waitFor(() => expect(sessionStorage.getItem('knowledgehub.access_token')).toBeNull())
})

test('registers then authenticates a valid account', async () => {
  vi.spyOn(globalThis, 'fetch')
    .mockResolvedValueOnce(jsonResponse(user, 201))
    .mockResolvedValueOnce(jsonResponse({ access_token: 'token', token_type: 'bearer' }))
    .mockResolvedValueOnce(jsonResponse(user))
  renderWithProviders(<RoutesUnderTest />, '/register')
  const actor = userEvent.setup()
  await actor.type(screen.getByLabelText('Email'), user.email)
  await actor.type(screen.getByLabelText('Password'), 'StrongPassword123!')
  await actor.click(screen.getByRole('button', { name: 'Register' }))
  expect(await screen.findByText('Dashboard')).toBeInTheDocument()
})

test('renders safe invalid credential errors', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse({ error: { code: 'unauthorized', message: 'Invalid email or password' } }, 401))
  renderWithProviders(<RoutesUnderTest />)
  const actor = userEvent.setup()
  await actor.type(await screen.findByLabelText('Email'), user.email)
  await actor.type(screen.getByLabelText('Password'), 'wrong')
  await actor.click(screen.getByRole('button', { name: 'Log in' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Invalid email or password')
})

test('a 401 clears authentication globally', async () => {
  setAccessToken('expired')
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse({ error: { message: 'Expired' } }, 401))
  await expect(apiRequest('/auth/me')).rejects.toThrow('Expired')
  expect(sessionStorage.getItem('knowledgehub.access_token')).toBeNull()
})
