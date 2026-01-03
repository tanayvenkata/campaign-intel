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
