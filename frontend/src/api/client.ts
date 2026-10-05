/** 统一请求封装：拼后端地址、带值班人身份头、抛网络错误、给页脚留一句可读的说明。 */
import { useSessionStore } from '@/stores/session'

const API_BASE = import.meta.env.VITE_API_BASE ?? ''

function authHeaders(init?: RequestInit): HeadersInit {
  const session = useSessionStore()
  return {
    'Content-Type': 'application/json',
    'X-Operator': session.operatorCode,
    ...(init?.headers ?? {}),
  }
}

export function request(path: string, init?: RequestInit): Promise<Response> {
  const url = path.startsWith('http') ? path : `${API_BASE}${path}`
  return fetch(url, {
    ...init,
    headers: authHeaders(init),
  }).catch((error: unknown) => {
    const detail = error instanceof Error ? error.message : '请求未送达'
    throw new Error(`接口请求失败：${detail}`)
  })
}

/** 读取后端错误：优先取 FastAPI 的 detail，其次取 ActionResult.message。 */
export async function readError(response: Response, fallback: string): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: string; message?: string }
    return payload.detail || payload.message || fallback
  } catch {
    return fallback
  }
}

export async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await request(path, init)
  if (!response.ok) {
    throw new Error(await readError(response, `接口返回 ${response.status}，数据未更新`))
  }
  return (await response.json()) as T
}
