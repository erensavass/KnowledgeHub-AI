import { expect, test } from '@playwright/test'

test.skip(process.env.RUN_REAL_BACKEND_E2E !== '1', 'real backend E2E is opt-in')

test('real backend document and grounded conversation flow', async ({ page }) => {
  test.setTimeout(10 * 60 * 1000)
  const email = `frontend-e2e-${Date.now()}@example.com`
  await page.goto('/register')
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password').fill('RealBackendPass123!')
  await page.getByRole('button', { name: 'Register' }).click()
  await page.getByRole('link', { name: 'Documents', exact: true }).click()
  await page.getByLabel('Upload PDF, DOCX, or TXT').setInputFiles({
    name: 'knowledge.txt',
    mimeType: 'text/plain',
    buffer: Buffer.from('Authentication uses signed access tokens.'),
  })
  await expect(page.getByText('knowledge.txt')).toBeVisible()
  await page.getByRole('button', { name: 'Process' }).click()
  await expect(page.getByRole('button', { name: 'Embed' })).toBeEnabled()
  await page.getByRole('button', { name: 'Embed' }).click()
  await expect(page.getByRole('button', { name: 'Re-embed' })).toBeEnabled({ timeout: 5 * 60 * 1000 })
  await page.getByRole('button', { name: /New conversation/ }).click()
  await page.getByLabel('Ask a question').fill('How does authentication work?')
  await page.getByRole('button', { name: 'Send' }).click()
  await expect(page.getByLabel('assistant message')).toBeVisible({ timeout: 5 * 60 * 1000 })
  await expect(page.getByText(/retrieved source excerpt/)).toBeVisible()
})
