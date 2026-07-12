import { Component, type ReactNode } from 'react'

type Props = { children: ReactNode }
type State = { failed: boolean }

export class ErrorBoundary extends Component<Props, State> {
  state: State = { failed: false }

  static getDerivedStateFromError(): State { return { failed: true } }

  componentDidCatch() {
    // Detailed runtime errors stay in browser diagnostics and are never rendered.
  }

  render() {
    if (this.state.failed) return <main className="mx-auto max-w-xl p-8 text-center" role="alert">
      <h1 className="text-2xl font-semibold">Something went wrong</h1>
      <p className="mt-3 text-slate-600">Reload the page to continue. Your documents remain stored safely.</p>
      <button className="mt-6 rounded bg-brand-700 px-4 py-2 text-white" onClick={() => window.location.reload()}>
        Reload application
      </button>
    </main>
    return this.props.children
  }
}
