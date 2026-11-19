export async function api<T>(
  path: string,
  body?: unknown,
  signal?: AbortSignal,
): Promise<T> {
  const response = await fetch("/api" + path, {
    signal,
    method: body === undefined ? "GET" : "POST",
    headers:
      body === undefined
        ? {}
        : { "Content-Type": "application/json", "X-Workbench": "local" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: response.statusText }));
    throw new Error(
      typeof error.detail === "string"
        ? error.detail
        : JSON.stringify(error.detail),
    );
  }
  return response.json();
}
export const fmt = (value: unknown) =>
  value === null || value === undefined
    ? "—"
    : typeof value === "string"
      ? value
      : JSON.stringify(value, null, 2);
export const time = (seconds: number | null | undefined): string => {
  if (seconds == null) return "—";
  if (seconds < 0) return "−" + time(-seconds);
  if (seconds > 0 && seconds < 0.001) return "<1 ms";
  return seconds < 1
    ? (seconds * 1000).toFixed(0) + " ms"
    : seconds < 60
      ? seconds.toFixed(1).replace(".", ",") + " s"
      : Math.floor(Math.round(seconds) / 60) +
        " min " +
        (Math.round(seconds) % 60) +
        " s";
};
export const money = (value: number | null | undefined, currency = "BRL") =>
  value == null
    ? "Não configurado"
    : new Intl.NumberFormat("pt-BR", {
        style: "currency",
        currency,
        maximumFractionDigits: 4,
      }).format(value);
export const percent = (value: number | null | undefined) =>
  value == null ? "—" : (value * 100).toFixed(1).replace(".", ",") + "%";
export const statusLabel: Record<string, string> = {
  queued: "Na fila",
  starting: "Iniciando",
  running: "Em execução",
  complete: "Concluída",
  partial: "Parcial",
  failed: "Falhou",
  cancelled: "Cancelada",
  interrupted: "Interrompida",
  pending: "Pendente",
  skipped: "Não necessária",
  reused: "Reaproveitada",
  not_executed: "Não executada",
};
