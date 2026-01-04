import { useState, useEffect } from 'react';
import { ENDPOINTS } from '../config/api';

// Mock data for development
const MOCK_CORPUS = {
    focus_groups: [
        { id: 'OH-001', location: 'Ohio 2024 - Cleveland Suburbs', date: '2024-11-12', outcome: 'loss', race_name: 'Ohio Senate' },
        { id: 'OH-002', location: 'Ohio 2024 - Columbus Educated', date: '2024-11-14', outcome: 'loss', race_name: 'Ohio Senate' },
        { id: 'OH-003', location: 'Ohio 2024 - Youngstown Working Class', date: '2024-11-15', outcome: 'loss', race_name: 'Ohio Senate' },
        { id: 'WI-001', location: 'Wisconsin 2024 - Madison Liberals', date: '2024-10-02', outcome: 'win', race_name: 'WI Senate' },
        { id: 'WI-002', location: 'Wisconsin 2024 - Green Bay Swing', date: '2024-10-05', outcome: 'win', race_name: 'WI Senate' },
        { id: 'PA-001', location: 'PA 2022 - Philly Suburbs', date: '2022-09-10', outcome: 'win', race_name: 'PA Gov' },
        { id: 'PA-002', location: 'PA 2022 - Pittsburgh Union', date: '2022-09-12', outcome: 'win', race_name: 'PA Gov' },
        { id: 'MI-001', location: 'Michigan 2024 - Detroit Turnout', date: '2024-08-20', outcome: 'win', race_name: 'MI Senate' },
        { id: 'MT-001', location: 'Montana 2024 - Rural', date: '2024-07-15', outcome: 'loss', race_name: 'MT Senate' },
        { id: 'NV-001', location: 'Nevada 2024 - Las Vegas Service', date: '2024-09-01', outcome: 'win', race_name: 'NV Senate' },
        { id: 'AZ-001', location: 'Arizona 2024 - Maricopa Moms', date: '2024-09-10', outcome: 'win', race_name: 'AZ Senate' },
        { id: 'GA-001', location: 'Georgia 2022 - Atlanta Suburbs', date: '2022-10-20', outcome: 'win', race_name: 'GA Senate' },
    ]
};

export function useCorpusIndex() {
    const [index, setIndex] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        // In a real implementation, we would fetch from ENDPOINTS.corpus
        // fetch(ENDPOINTS.corpus).then(...)

        // For now, simulate loading mock data
        const timer = setTimeout(() => {
            setIndex(MOCK_CORPUS.focus_groups);
            setLoading(false);
        }, 800);

        return () => clearTimeout(timer);
    }, []);

    return { index, loading };
}
