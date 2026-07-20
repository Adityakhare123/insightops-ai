import {
  clearAuthSession,
  getAccessToken,
  getRefreshToken,
  updateStoredTokenPair,
} from "./tokenStorage";

import type {
  ApiErrorPayload,
  RefreshTokenResponse,
} from "../types/auth";

const DEFAULT_API_BASE_URL =
  "http://localhost:8000/api/v1";

export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL
  ?? DEFAULT_API_BASE_URL
).replace(/\/+$/, "");

export interface ApiRequestOptions extends RequestInit {
  auth?: boolean;
  retryOnUnauthorized?: boolean;
}

export class ApiError extends Error {
  readonly status: number;
  readonly payload: unknown;

  constructor(
    message: string,
    status: number,
    payload: unknown = null,
  ) {
    super(message);

    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

let refreshRequest:
  Promise<string | null> | null = null;

function createRequestUrl(path: string): string {
  const normalizedPath = path.startsWith("/")
    ? path
    : `/${path}`;

  return `${API_BASE_URL}${normalizedPath}`;
}

function isFormDataBody(
  body: BodyInit | null | undefined,
): body is FormData {
  return typeof FormData !== "undefined"
    && body instanceof FormData;
}

function createHeaders(
  options: ApiRequestOptions,
  accessToken: string | null,
): Headers {
  const headers = new Headers(options.headers);

  if (
    options.body
    && !isFormDataBody(options.body)
    && !headers.has("Content-Type")
  ) {
    headers.set(
      "Content-Type",
      "application/json",
    );
  }

  headers.set(
    "Accept",
    "application/json",
  );

  if (options.auth !== false && accessToken) {
    headers.set(
      "Authorization",
      `Bearer ${accessToken}`,
    );
  }

  return headers;
}

async function parseResponseBody(
  response: Response,
): Promise<unknown> {
  if (response.status === 204) {
    return null;
  }

  const contentType =
    response.headers.get("content-type") ?? "";

  if (contentType.includes("application/json")) {
    return response.json();
  }

  const responseText = await response.text();

  return responseText || null;
}

function getApiErrorMessage(
  status: number,
  payload: unknown,
): string {
  if (
    payload
    && typeof payload === "object"
  ) {
    const errorPayload =
      payload as ApiErrorPayload;

    if (typeof errorPayload.detail === "string") {
      return errorPayload.detail;
    }

    if (
      Array.isArray(errorPayload.detail)
      && errorPayload.detail.length > 0
    ) {
      return errorPayload.detail
        .map((error) => error.msg ?? "Validation error")
        .join(", ");
    }

    if (typeof errorPayload.message === "string") {
      return errorPayload.message;
    }
  }

  if (status === 401) {
    return "Your session is invalid or has expired.";
  }

  if (status === 403) {
    return "You do not have permission to perform this action.";
  }

  if (status === 404) {
    return "The requested resource was not found.";
  }

  if (status >= 500) {
    return "The server encountered an unexpected error.";
  }

  return `Request failed with status ${status}.`;
}

async function requestNewAccessToken():
Promise<string | null> {
  const refreshToken = getRefreshToken();

  if (!refreshToken) {
    clearAuthSession();
    return null;
  }

  if (refreshRequest) {
    return refreshRequest;
  }

  refreshRequest = (async () => {
    const response = await fetch(
      createRequestUrl("/auth/refresh"),
      {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          refresh_token: refreshToken,
        }),
      },
    );

    const responsePayload =
      await parseResponseBody(response);

    if (!response.ok) {
      clearAuthSession();

      throw new ApiError(
        getApiErrorMessage(
          response.status,
          responsePayload,
        ),
        response.status,
        responsePayload,
      );
    }

    const tokenPair =
      responsePayload as RefreshTokenResponse;

    updateStoredTokenPair(tokenPair);

    return tokenPair.access_token;
  })();

  try {
    return await refreshRequest;
  } finally {
    refreshRequest = null;
  }
}

async function executeRequest(
  path: string,
  options: ApiRequestOptions,
  accessToken: string | null,
): Promise<Response> {
  const {
    auth: _auth,
    retryOnUnauthorized: _retry,
    ...requestOptions
  } = options;

  return fetch(
    createRequestUrl(path),
    {
      ...requestOptions,
      headers: createHeaders(
        options,
        accessToken,
      ),
    },
  );
}

export async function apiRequest<T>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<T> {
  const shouldAuthenticate =
    options.auth !== false;

  const shouldRetry =
    options.retryOnUnauthorized !== false;

  let response = await executeRequest(
    path,
    options,
    shouldAuthenticate
      ? getAccessToken()
      : null,
  );

  if (
    response.status === 401
    && shouldAuthenticate
    && shouldRetry
    && getRefreshToken()
  ) {
    try {
      const refreshedAccessToken =
        await requestNewAccessToken();

      if (refreshedAccessToken) {
        response = await executeRequest(
          path,
          {
            ...options,
            retryOnUnauthorized: false,
          },
          refreshedAccessToken,
        );
      }
    } catch {
      clearAuthSession();
    }
  }

  const responsePayload =
    await parseResponseBody(response);

  if (!response.ok) {
    if (response.status === 401) {
      clearAuthSession();
    }

    throw new ApiError(
      getApiErrorMessage(
        response.status,
        responsePayload,
      ),
      response.status,
      responsePayload,
    );
  }

  return responsePayload as T;
}

export function getJson<T>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<T> {
  return apiRequest<T>(
    path,
    {
      ...options,
      method: "GET",
    },
  );
}

export function postJson<TResponse, TRequest>(
  path: string,
  payload: TRequest,
  options: ApiRequestOptions = {},
): Promise<TResponse> {
  return apiRequest<TResponse>(
    path,
    {
      ...options,
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export const apiClient = {
  request: apiRequest,

  get<T>(
    path: string,
    options: ApiRequestOptions = {},
  ): Promise<T> {
    return getJson<T>(
      path,
      options,
    );
  },

  post<TResponse, TRequest>(
    path: string,
    payload: TRequest,
    options: ApiRequestOptions = {},
  ): Promise<TResponse> {
    return postJson<TResponse, TRequest>(
      path,
      payload,
      options,
    );
  },
};