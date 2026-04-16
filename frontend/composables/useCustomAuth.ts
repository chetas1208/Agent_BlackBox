export interface User {
  id: string
  email: string
  name: string
  github_username: string | null
}

export function useCustomAuth() {
  const config = useRuntimeConfig()
  const base = config.public.apiBase

  const token = useCookie<string | null>('abb_token', { default: () => null, maxAge: 60 * 60 * 24 * 7 })
  const user = useState<User | null>('auth_user', () => null)

  const isLoggedIn = computed(() => !!token.value)

  async function register(email: string, password: string, name: string) {
    const res = await fetch(`${base}/api/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, name }),
    })
    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail || 'Registration failed')
    }
    const data = await res.json()
    token.value = data.token
    user.value = data.user
    return data.user
  }

  async function login(email: string, password: string) {
    const res = await fetch(`${base}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    })
    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail || 'Login failed')
    }
    const data = await res.json()
    token.value = data.token
    user.value = data.user
    return data.user
  }

  async function fetchMe() {
    if (!token.value) return null
    try {
      const res = await fetch(`${base}/api/auth/me`, {
        headers: { Authorization: `Bearer ${token.value}` },
      })
      if (!res.ok) { token.value = null; user.value = null; return null }
      user.value = await res.json()
      return user.value
    } catch {
      return null
    }
  }

  function logout() {
    token.value = null
    user.value = null
    navigateTo('/login')
  }

  async function saveGithubToken(ghToken: string, username: string) {
    if (!token.value) return
    await fetch(`${base}/api/auth/github-token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token.value}` },
      body: JSON.stringify({ token: ghToken, username }),
    })
    if (user.value) user.value.github_username = username
  }

  async function listGithubRepos() {
    if (!token.value) return []
    const res = await fetch(`${base}/api/auth/github/repos`, {
      headers: { Authorization: `Bearer ${token.value}` },
    })
    if (!res.ok) return []
    return res.json()
  }

  function getAuthHeaders(): Record<string, string> {
    if (!token.value) return {}
    return { Authorization: `Bearer ${token.value}` }
  }

  return {
    token,
    user,
    isLoggedIn,
    register,
    login,
    logout,
    fetchMe,
    saveGithubToken,
    listGithubRepos,
    getAuthHeaders,
  }
}
