import { useState, useCallback } from 'react';
import { SearchResponse } from '../types';

export interface SearchStep {
    step: string;
    message: string;
    timestamp: number;
}

export function useStreamingSearch() {
    const [steps, setSteps] = useState<SearchStep[]>([]);
    const [data, setData] = useState<SearchResponse | null>(null);
    const [isSearching, setIsSearching] = useState(false);
    const [error, setError] = useState<Error | null>(null);

    const search = useCallback(async (query: string) => {
        if (!query.trim()) return;

        setIsSearching(true);
        setSteps([]);
        setData(null);
        setError(null);

        try {
            const res = await fetch('http://localhost:8000/search/stream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query, top_k: 5, score_threshold: 0.75 }),
            });

            if (!res.ok) {
                throw new Error('Search failed');
            }

            if (!res.body) {
                throw new Error('No response body');
            }

            const reader = res.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() || '';

                for (const line of lines) {
                    if (!line.trim()) continue;

                    try {
                        const event = JSON.parse(line);

                        if (event.type === 'status') {
                            setSteps(prev => [...prev, {
                                step: event.step,
                                message: event.message,
                                timestamp: Date.now()
                            }]);
                        } else if (event.type === 'results') {
                            setData(event.data);
                        }
                    } catch (parseError) {
                        console.error('Failed to parse event:', line);
                    }
                }
            }
        } catch (e) {
            setError(e as Error);
        } finally {
            setIsSearching(false);
        }
    }, []);

    const reset = useCallback(() => {
        setSteps([]);
        setData(null);
        setError(null);
        setIsSearching(false);
    }, []);

    return { search, reset, steps, data, isSearching, error };
}
