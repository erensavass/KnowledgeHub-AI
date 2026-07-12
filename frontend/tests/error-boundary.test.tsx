import { render, screen } from '@testing-library/react'
import { ErrorBoundary } from '../src/components/ErrorBoundary'

function BrokenComponent(): never { throw new Error('sensitive internal failure') }

test('error boundary renders a safe recovery view', () => {
  const original = console.error
  console.error = () => undefined
  render(<ErrorBoundary><BrokenComponent /></ErrorBoundary>)
  console.error = original
  expect(screen.getByRole('alert')).toHaveTextContent('Something went wrong')
  expect(screen.queryByText('sensitive internal failure')).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Reload application' })).toBeInTheDocument()
})
