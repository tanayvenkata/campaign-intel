/**
 * API Configuration
 *
 * Centralized configuration for all API endpoints.
 * Uses environment variable NEXT_PUBLIC_API_URL for production deployments.
 */

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const ENDPOINTS = {
  // FG-only search (legacy)
  search: `${API_BASE_URL}/search`,
  searchStream: `${API_BASE_URL}/search/stream`,
  // Unified search (FG + Strategy)
  searchUnified: `${API_BASE_URL}/search/unified`,
  // FG synthesis
  synthesizeLight: `${API_BASE_URL}/synthesize/light`,
  synthesizeDeep: `${API_BASE_URL}/synthesize/deep`,
  synthesizeMacroLight: `${API_BASE_URL}/synthesize/macro/light`,
  synthesizeMacroDeep: `${API_BASE_URL}/synthesize/macro/deep`,
  // Strategy synthesis
  synthesizeStrategyLight: `${API_BASE_URL}/synthesize/strategy/light`,
  synthesizeStrategyDeep: `${API_BASE_URL}/synthesize/strategy/deep`,
  // Unified macro (FG + Strategy combined)
  synthesizeUnifiedMacro: `${API_BASE_URL}/synthesize/unified/macro`,
} as const;

export const SEARCH_CONFIG = {
  TOP_K: parseInt(process.env.NEXT_PUBLIC_TOP_K || '5', 10),
  SCORE_THRESHOLD: parseFloat(process.env.NEXT_PUBLIC_SCORE_THRESHOLD || '0.50'),
} as const;
