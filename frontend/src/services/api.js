/** Browser HTTP boundary. Use relative paths through the gateway; never embed a server secret. */
import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "",
  timeout: 60000,
});
/** Convert network failures and Pydantic field errors into readable UI messages. */
export function errorText(error) {
  const detail = error?.response?.data?.detail;
  if (Array.isArray(detail))
    return detail
      .map((item) => `${(item.loc || []).join(".")}: ${item.msg}`)
      .join("; ");
  return typeof detail === "string"
    ? detail
    : error?.message || "Service unavailable.";
}
/** Download a server-produced file and release its temporary in-browser URL. */
export async function download(path, filename, params) {
  const response = await api.get(path, { params, responseType: "blob" });
  const url = URL.createObjectURL(response.data);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
/** Read dataset contracts and which scoring policies are actually available. */
export const fetchProfiles = () => api.get("/api/v1/profiles");
/** Read matching frozen evaluation; AbortSignal cancels obsolete profile requests. */
export const fetchReport = (profile, signal) =>
  api.get(`/api/v1/profiles/${profile}/evaluation`, { signal });
/** Read selected validation examples, which are demonstrations rather than a test set. */
export const fetchSamples = (profile, signal) =>
  api.get(`/api/v1/profiles/${profile}/samples`, { signal });
/** Start an isolated dataset history; seeded BankSim demos use a fixed earlier cutoff. */
export const createSession = (profile, seeded = false) =>
  api.post("/api/v1/sessions", { profile, seeded });
/** Fetch durable prediction rows using filters and an optional pagination cursor. */
export const fetchLogs = (params) => api.get("/api/v1/predictions", { params });
/** Save analyst state/notes without replacing the original model prediction. */
export const reviewPrediction = (id, state, notes) =>
  api.patch(`/api/v1/predictions/${id}/review`, { state, notes });
/** Read measured request counters and recent prediction latency statistics. */
export const fetchOperations = () => api.get("/api/v1/operations");
/** Score once with an explicit policy; reuse requestId only for an exact retry. */
export const predict = (
  profile,
  sessionId,
  transaction,
  requestId = crypto.randomUUID(),
  modelChoice = "champion",
) =>
  api.post(`/api/v1/profiles/${profile}/predictions`, {
    session_id: sessionId,
    request_id: requestId,
    transaction,
    model_choice: modelChoice,
  });
/** Send a bounded CSV as multipart data, keeping the requested scoring policy explicit. */
export function scoreCsv(profile, sessionId, file, modelChoice = "champion") {
  const body = new FormData();
  body.append("file", file);
  body.append("session_id", sessionId);
  body.append("request_id", crypto.randomUUID());
  body.append("model_choice", modelChoice);
  return api.post(`/api/v1/profiles/${profile}/batch-predictions`, body);
}
export default api;
