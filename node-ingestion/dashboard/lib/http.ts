import axios from 'axios';

/**
 * In production this dashboard is a static export served by the SAME
 * node-ingestion Fastify server (see next.config.ts), so a relative baseURL
 * ('') just works. In dev, `next dev` runs on its own port — point it at the
 * Fastify server via NEXT_PUBLIC_API_URL (see .env.local).
 */
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? '';

export class ApiError extends Error {
  statusCode: number;
  body: unknown;

  constructor(message: string, statusCode: number, body?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.statusCode = statusCode;
    this.body = body;
  }
}

export const http = axios.create({
  baseURL: API_BASE_URL,
  timeout: 35_000, // joint interpretation calls out to the LLM agent server-side
});

http.interceptors.response.use(
  (response) => response,
  (error) => {
    if (axios.isAxiosError(error)) {
      const body = error.response?.data as { message?: string; status?: string } | undefined;
      const message = body?.message ?? body?.status ?? error.message;
      return Promise.reject(new ApiError(message, error.response?.status ?? 0, body));
    }
    return Promise.reject(error);
  },
);
