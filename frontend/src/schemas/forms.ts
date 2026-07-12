import { z } from 'zod'

export const loginSchema = z.object({
  email: z.string().email('Enter a valid email address.'),
  password: z.string().min(1, 'Password is required.'),
})
export const registerSchema = loginSchema.extend({
  password: z.string().min(12, 'Use at least 12 characters.').max(128)
    .regex(/[a-z]/, 'Include a lowercase letter.')
    .regex(/[A-Z]/, 'Include an uppercase letter.')
    .regex(/\d/, 'Include a number.')
    .regex(/[^\w\s]/, 'Include a special character.'),
})
export const titleSchema = z.object({ title: z.string().trim().min(1).max(120) })
export const querySchema = z.object({ query: z.string().trim().min(1, 'Enter a question.').max(4000) })
export const searchSchema = z.object({
  query: z.string().trim().min(1, 'Enter a search query.').max(2000),
  top_k: z.coerce.number().int().min(1).max(20),
  score_threshold: z.coerce.number().min(-1).max(1),
})

const allowedExtensions = ['pdf', 'docx', 'txt']
export function validateUpload(file: File, maxMegabytes: number) {
  const extension = file.name.split('.').pop()?.toLowerCase() || ''
  if (!allowedExtensions.includes(extension)) return 'Choose a PDF, DOCX, or TXT file.'
  if (file.size === 0) return 'The selected file is empty.'
  if (file.size > maxMegabytes * 1024 * 1024) return `File must be ${maxMegabytes} MB or smaller.`
  return null
}
