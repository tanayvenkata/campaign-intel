/**
 * API Configuration
 *
 * Centralized configuration for all API endpoints.
 * Uses environment variable NEXT_PUBLIC_API_URL for production deployments.
 */

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const ENDPOINTS = {
  search: `${API_BASE_URL}/search`,
  searchStream: `${API_BASE_URL}/search/stream`,
  synthesizeLight: `${API_BASE_URL}/synthesize/light`,
  synthesizeDeep: `${API_BASE_URL}/synthesize/deep`,
  synthesizeMacroLight: `${API_BASE_URL}/synthesize/macro/light`,
  synthesizeMacroDeep: `${API_BASE_URL}/synthesize/macro/deep`,
} as const;

export const SEARCH_CONFIG = {
  TOP_K: 5,
  SCORE_THRESHOLD: 0.75,
} as const;
