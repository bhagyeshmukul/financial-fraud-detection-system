// Shared API client and endpoint helpers for frontend-backend communication.
import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://localhost:8000",
  timeout: 15000,
});

export const predictFraud = (payload) => api.post("/predict-fraud", payload);
export const fetchPredictionLogs = (limit = 20) => api.get(`/prediction-logs?limit=${limit}`);
export const fetchSampleTransactions = () => api.get("/sample-transactions");

export default api;
