/**
 * Prefetch Utility
 *
 * Prefetches search results on hover for faster UX.
 */

import { mutate } from 'swr';
import { ENDPOINTS } from '../config/api';

export function prefetchSearch(query: string): void {
  mutate(`search-${query}`, async () => {
    const res = await fetch(ENDPOINTS.search, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query }),
    });
    return res.json();
  });
}
