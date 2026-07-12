import '@testing-library/jest-dom/vitest'
import { afterEach, vi } from 'vitest'
import { cleanup } from '@testing-library/react'
import { setAccessToken } from '../src/stores/auth-token'

afterEach(() => { cleanup(); setAccessToken(null); sessionStorage.clear(); vi.restoreAllMocks() })

HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', '') }
HTMLDialogElement.prototype.close = function () { this.removeAttribute('open'); this.dispatchEvent(new Event('close')) }
Element.prototype.scrollTo = vi.fn()
