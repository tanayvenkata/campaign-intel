import { useState, useCallback } from 'react';
import { UnifiedSearchResponse } from '../types';
import { ENDPOINTS, SEARCH_CONFIG } from '../config/api';

export function useUnifiedSearch() {
    const [data, setData] = useState<UnifiedSearchResponse | null>(null);
    const [isSearching, setIsSearching] = useState(false);
    const [error, setError] = useState<Error | null>(null);

    const search = useCallback(async (query: string) => {
        if (!query.trim()) return;

        setIsSearching(true);
        setData(null);
        setError(null);

        try {
            const res = await fetch(ENDPOINTS.searchUnified, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    query,
                    top_k: SEARCH_CONFIG.TOP_K,
                    score_threshold: SEARCH_CONFIG.SCORE_THRESHOLD,
                }),
            });

            if (!res.ok) {
                throw new Error('Search failed');
            }

            const result: UnifiedSearchResponse = await res.json();
            setData(result);
        } catch (e) {
            setError(e as Error);
        } finally {
            setIsSearching(false);
        }
    }, []);

    const reset = useCallback(() => {
        setData(null);
        setError(null);
        setIsSearching(false);
    }, []);

    return { search, reset, data, isSearching, error };
}
