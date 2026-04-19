import { render, screen, waitFor } from '@testing-library/react'
import App from './App'

beforeEach(() => {
  global.fetch = vi.fn(() =>
    Promise.resolve({
      json: () => Promise.resolve({ message: 'Hello from backend' })
    })
  )
})

test('renders main app header and pipeline sections', async () => {
  render(<App />)

  expect(screen.getByRole('heading', { name: /my ci\/cd framework/i })).toBeInTheDocument()
  expect(screen.getByText(/pipeline stages/i)).toBeInTheDocument()
  expect(screen.getByText(/backend connection/i)).toBeInTheDocument()

  await waitFor(() => expect(screen.getByText(/connected/i)).toBeInTheDocument())
})
