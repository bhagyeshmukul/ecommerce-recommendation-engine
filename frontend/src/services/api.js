import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
});

export const fetchUsers = async () => (await api.get('/users')).data.users;
export const fetchRecommendations = async (userId, topK = 5) =>
  (await api.get(`/recommend/${userId}`, { params: { top_k: topK } })).data;
export const fetchPopularProducts = async () => (await api.get('/products/popular')).data.products;
export const fetchUserHistory = async (userId) => (await api.get(`/users/${userId}/history`)).data;
export const fetchMetrics = async () => (await api.get('/metrics')).data;
export const fetchLogs = async () => (await api.get('/recommendation-logs')).data;
