import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import type { z } from 'zod'
import { safeError } from '../../api/client'
import { loginSchema, registerSchema } from '../../schemas/forms'
import { useAuth } from './AuthProvider'

export function AuthPage({ mode }: { mode: 'login' | 'register' }) {
  const schema = mode === 'login' ? loginSchema : registerSchema
  type Values = z.infer<typeof schema>
  const { user, login, register } = useAuth()
  const navigate = useNavigate(); const location = useLocation()
  const [error, setError] = useState('')
  const { register: field, handleSubmit, formState: { errors, isSubmitting } } = useForm<Values>({ resolver: zodResolver(schema) })
  if (user) return <Navigate to="/" replace />
  const submit = handleSubmit(async (values) => {
    setError('')
    try {
      await (mode === 'login' ? login(values.email, values.password) : register(values.email, values.password))
      const destination = (location.state as { from?: string } | null)?.from || '/'
      navigate(destination, { replace: true })
    } catch (reason) { setError(safeError(reason)) }
  })
  return <main className="grid min-h-screen place-items-center px-4">
    <section className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-8 shadow-sm dark:border-slate-800 dark:bg-slate-900" aria-labelledby="auth-title">
      <p className="mb-2 text-sm font-semibold text-brand-600">KnowledgeHub AI</p>
      <h1 id="auth-title" className="text-2xl font-semibold">{mode === 'login' ? 'Welcome back' : 'Create your account'}</h1>
      <p className="mt-2 text-sm text-slate-500">Secure access to your document knowledge workspace.</p>
      <form className="mt-6 space-y-4" onSubmit={submit} noValidate>
        <label className="block text-sm font-medium">Email<input className="mt-1 w-full rounded-lg border bg-transparent px-3 py-2" type="email" autoComplete="email" {...field('email')} /></label>
        {errors.email && <p className="text-sm text-red-600">{errors.email.message}</p>}
        <label className="block text-sm font-medium">Password<input className="mt-1 w-full rounded-lg border bg-transparent px-3 py-2" type="password" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} {...field('password')} /></label>
        {errors.password && <p className="text-sm text-red-600">{errors.password.message}</p>}
        {error && <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950">{error}</p>}
        <button className="w-full rounded-lg bg-brand-600 px-4 py-2.5 font-medium text-white hover:bg-brand-700" disabled={isSubmitting}>{isSubmitting ? 'Please wait…' : mode === 'login' ? 'Log in' : 'Register'}</button>
      </form>
      <p className="mt-5 text-center text-sm">{mode === 'login' ? 'New here?' : 'Already registered?'} <Link className="font-medium text-brand-600 underline" to={mode === 'login' ? '/register' : '/login'}>{mode === 'login' ? 'Create an account' : 'Log in'}</Link></p>
    </section>
  </main>
}
