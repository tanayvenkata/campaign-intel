import useSWR, { mutate } from 'swr';
import { SearchResponse } from '../types';

const fetcher = async (query: string): Promise<SearchResponse> => {
    if (!query) throw new Error('Query is required');

    const res = await fetch('http://localhost:8000/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            query,
            top_k: 5,
            score_threshold: 0.75
        }),
    });

    if (!res.ok) {
        throw new Error('Search failed');
    }

    return res.json();
};

export function useSearch(query: string | null) {
    const { data, error, isLoading, isValidating } = useSWR<SearchResponse>(
        query ? query : null,
        fetcher,
        {
            revalidateOnFocus: false, // Don't revalidate when window gets focus for static data
            dedupingInterval: 60000, // Cache results for 1 minute
            keepPreviousData: true, // Show previous data while fetching new data
        }
    );

    return {
        data,
        error,
        isLoading,
        isValidating
    };
}

export const prefetchSearch = (query: string) => {
    mutate(query, fetcher(query).catch(() => undefined));
};
