type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';

type RequestConfig = {
  readonly method?: HttpMethod;
  readonly body?: unknown;
  readonly headers?: Record<string, string>;
  readonly signal?: AbortSignal;
};

type ApiResponse<T> = {
  readonly data: T;
  readonly status: number;
};

type ApiError = {
  readonly message: string;
  readonly status: number;
};

function getApiBase(): string {
  if (typeof window === 'undefined') {
    return process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
  }
  return process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
}

function getProxyBase(): string {
  if (typeof window === 'undefined') {
    return '';
  }
  return '';
}

function getAuthToken(): string | null {
  if (typeof window === 'undefined') return null;
  try {
    const stored = localStorage.getItem('gtm_auth_token');
    return stored;
  } catch {
    return null;
  }
}

async function request<T>(path: string, config: RequestConfig = {}): Promise<ApiResponse<T>> {
  const { method = 'GET', body, headers = {}, signal } = config;
  const token = getAuthToken();

  const requestHeaders: Record<string, string> = {
    'Content-Type': 'application/json',
    ...headers,
  };

  if (token) {
    requestHeaders['Authorization'] = `Bearer ${token}`;
  }

  const fetchConfig: RequestInit = {
    method,
    headers: requestHeaders,
    cache: 'no-store',
    signal,
  };

  if (body !== undefined) {
    fetchConfig.body = JSON.stringify(body);
  }

  const res = await fetch(`${getApiBase()}${path}`, fetchConfig);

  if (!res.ok) {
    const errorText = await res.text().catch(() => 'Unknown error');
    const error: ApiError = {
      message: errorText,
      status: res.status,
    };
    throw error;
  }

  const data = await res.json() as T;
  return { data, status: res.status };
}

async function proxyRequest<T>(path: string, config: RequestConfig = {}): Promise<ApiResponse<T>> {
  const { method = 'GET', body, headers = {}, signal } = config;
  const token = getAuthToken();

  const requestHeaders: Record<string, string> = {
    'Content-Type': 'application/json',
    ...headers,
  };

  if (token) {
    requestHeaders['Authorization'] = `Bearer ${token}`;
  }

  const fetchConfig: RequestInit = {
    method,
    headers: requestHeaders,
    signal,
  };

  if (body !== undefined) {
    fetchConfig.body = JSON.stringify(body);
  }

  const res = await fetch(`${getProxyBase()}${path}`, fetchConfig);

  if (!res.ok) {
    const errorText = await res.text().catch(() => 'Unknown error');
    throw { message: errorText, status: res.status } as ApiError;
  }

  const data = await res.json() as T;
  return { data, status: res.status };
}

export const api = {
  get: <T>(path: string, signal?: AbortSignal) =>
    request<T>(path, { signal }),

  post: <T>(path: string, body: unknown, signal?: AbortSignal) =>
    request<T>(path, { method: 'POST', body, signal }),

  put: <T>(path: string, body: unknown, signal?: AbortSignal) =>
    request<T>(path, { method: 'PUT', body, signal }),

  patch: <T>(path: string, body: unknown, signal?: AbortSignal) =>
    request<T>(path, { method: 'PATCH', body, signal }),

  delete: <T>(path: string, signal?: AbortSignal) =>
    request<T>(path, { method: 'DELETE', signal }),

  proxy: {
    post: <T>(path: string, body: unknown, signal?: AbortSignal) =>
      proxyRequest<T>(path, { method: 'POST', body, signal }),
  },

  streamSSE: (path: string, body: unknown, onMessage: (data: string) => void, onDone: () => void, onError: (err: string) => void) => {
    const controller = new AbortController();
    const token = getAuthToken();
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    fetch(`${getApiBase()}${path}`, {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
      signal: controller.signal,
    })
      .then(async (res) => {
        if (!res.ok) {
          onError(`Stream failed: ${res.status}`);
          return;
        }
        const reader = res.body?.getReader();
        if (!reader) {
          onError('No stream reader available');
          return;
        }
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const payload = line.slice(6);
              if (payload === '[DONE]') {
                onDone();
                return;
              }
              onMessage(payload);
            }
          }
        }
        onDone();
      })
      .catch((err) => {
        if (err.name !== 'AbortError') {
          onError(String(err?.message || err));
        }
      });

    return () => controller.abort();
  },
} as const;

export type { ApiResponse, ApiError };
