import { computed, ref } from 'vue'


const SESSION_KEY = 'big-bear-auth-session'
const apiUrl = import.meta.env.VITE_LANGGRAPH_API_URL ?? '/api/langgraph'
const savedSession = readSession()

export const authSession = ref(savedSession)
export const isAuthenticated = computed(() => Boolean(authSession.value?.accessToken))


export async function login(credentials) {
  const response = await request('/auth/login', credentials)
  saveSession({
    accessToken: response.access_token,
    user: response.user,
  })
  return response.user
}


export async function register(registration) {
  await request('/auth/register', registration)
  return login({ username: registration.username, password: registration.password })
}


export function logout() {
  authSession.value = null
  localStorage.removeItem(SESSION_KEY)
}


export function accessToken() {
  return authSession.value?.accessToken ?? null
}


async function request(path, body) {
  const response = await fetch(resolveUrl(path), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(payload.detail ?? '认证请求失败，请稍后重试。')
  }
  return payload
}


function saveSession(session) {
  authSession.value = session
  localStorage.setItem(SESSION_KEY, JSON.stringify(session))
}


function readSession() {
  try {
    const saved = localStorage.getItem(SESSION_KEY)
    return saved ? JSON.parse(saved) : null
  } catch {
    localStorage.removeItem(SESSION_KEY)
    return null
  }
}


function resolveUrl(path) {
  const base = apiUrl.replace(/\/$/, '')
  return `${base}${path}`
}