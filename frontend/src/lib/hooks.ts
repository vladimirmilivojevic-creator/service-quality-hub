"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import type { Meta, Plant, Scorecard, Service, SimulationResult } from "./types";

/** GET an API path with TanStack Query (caching, loading and error state). Pass null to wait. */
export function useApi<T>(path: string | null, options: { refetchInterval?: number } = {}) {
  return useQuery({
    queryKey: [path],
    queryFn: () => api<T>(path!),
    enabled: path !== null,
    ...options,
  });
}

/** POST/PATCH helper: refreshes all cached data afterwards so every page shows the new state. */
export function useApiMutation<TBody, TResult>(method: "POST" | "PATCH", path: string | ((body: TBody) => string)) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: TBody) =>
      api<TResult>(typeof path === "function" ? path(body) : path, {
        method,
        body: body === undefined ? undefined : JSON.stringify(body),
      }),
    onSuccess: () => queryClient.invalidateQueries(),
  });
}

export function useMeta() {
  return useApi<Meta>("/meta");
}

export function usePlants() {
  return useApi<Plant[]>("/plants");
}

export function useServices() {
  return useApi<Service[]>("/services");
}

export function useProviders() {
  const { data } = useApi<{ rows: Scorecard[] }>("/suppliers");
  return (data?.rows ?? []).map((r) => ({ id: r.provider_id, name: r.name }));
}

export function useSimulateDay() {
  return useApiMutation<void, SimulationResult>("POST", "/simulate/next-day");
}
