/** One fetch boundary: callers can cancel requests when a customer changes. */
const BASE = import.meta.env.VITE_API_BASE_URL || "/api";
export async function get(path, signal) {
  const response = await fetch(`${BASE}${path}`, { signal });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : `Request failed (${response.status}).`,
    );
  }
  return response.json();
}
