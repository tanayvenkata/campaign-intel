export interface RetrievalChunk {
    chunk_id: string;
    score: number;
    content: string;
    content_original: string | null;
    focus_group_id: string;
    participant: string;
    participant_profile: string;
    section: string;
    source_file: string;
    line_number: number;
    preceding_moderator_q: string;
}

export interface FocusGroupMetadata {
    location?: string;
    date?: string;
    race_name?: string;
    participant_summary?: string;
    moderator_notes?: {
        key_themes?: string[];
    };
    outcome?: string;
    [key: string]: any;
}

export interface GroupedResult {
    focus_group_id: string;
    focus_group_metadata: FocusGroupMetadata;
    chunks: RetrievalChunk[];
}

export interface SearchResponse {
    results: GroupedResult[];
    stats: {
        retrieval_time_ms: number;
        total_quotes: number;
        focus_groups_count: number;
    };
}

// Strategy types
export interface StrategyChunk {
    chunk_id: string;
    score: number;
    content: string;
    race_id: string;
    section: string;
    subsection: string;
    outcome: string;
    state: string;
    year: number;
    margin: number;
    source_file: string;
    line_number: number;
}

export interface StrategyMetadata {
    state?: string;
    year?: number;
    outcome?: string;
    margin?: number;
    office?: string;
    [key: string]: any;
}

export interface StrategyGroupedResult {
    race_id: string;
    race_metadata: StrategyMetadata;
    chunks: StrategyChunk[];
}

export interface UnifiedSearchResponse {
    content_type: 'quotes' | 'lessons' | 'both';
    quotes: GroupedResult[];
    lessons: StrategyGroupedResult[];
    stats: {
        retrieval_time_ms: number;
        total_quotes: number;
        total_lessons: number;
        focus_groups_count: number;
        races_count: number;
        routed_to: string;
        outcome_filter: string | null;
    };
}
