const TOKEN_KEY = 'knowledgehub.access_token'
let token: string | null = sessionStorage.getItem(TOKEN_KEY)

export function getAccessToken() { return token }

export function setAccessToken(value: string | null) {
  token = value
  if (value) sessionStorage.setItem(TOKEN_KEY, value)
  else sessionStorage.removeItem(TOKEN_KEY)
}

export function notifyUnauthorized() {
  setAccessToken(null)
  window.dispatchEvent(new CustomEvent('knowledgehub:unauthorized'))
}
