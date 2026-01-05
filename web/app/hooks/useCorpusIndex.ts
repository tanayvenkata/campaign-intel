import { useState, useEffect } from 'react';
import { ENDPOINTS } from '../config/api';

export interface CorpusItem {
    id: string;
    type: 'focus_group' | 'strategy_memo';
    title: string;
    date?: string;
    location?: string;
    race_name?: string;
    outcome?: string;
    file_path?: string;
}

export function useCorpusIndex() {
    const [index, setIndex] = useState<CorpusItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<Error | null>(null);

    useEffect(() => {
        async function fetchIndex() {
            try {
                const res = await fetch(ENDPOINTS.corpus);
                if (!res.ok) throw new Error('Failed to fetch corpus index');
                const data = await res.json();
                setIndex(data);
            } catch (e) {
                console.error(e);
                setError(e as Error);
            } finally {
                setLoading(false);
            }
        }

        fetchIndex();
    }, []);

    return { index, loading, error };
}
