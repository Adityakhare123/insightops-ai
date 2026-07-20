import {
  getJson,
  postJson,
} from "../../api/client";

import type {
  CurrentUserResponse,
  LoginRequest,
  LoginResponse,
} from "../../types/auth";

export function loginUser(
  credentials: LoginRequest,
): Promise<LoginResponse> {
  return postJson<LoginResponse, LoginRequest>(
    "/auth/login",
    credentials,
    {
      auth: false,
      retryOnUnauthorized: false,
    },
  );
}

export function getCurrentUser():
Promise<CurrentUserResponse> {
  return getJson<CurrentUserResponse>(
    "/auth/me",
  );
}