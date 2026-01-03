import React from 'react';
import { RetrievalChunk } from '../types';

interface QuoteBlockProps {
    chunk: RetrievalChunk;
}

export default function QuoteBlock({ chunk }: QuoteBlockProps) {
    const content = chunk.content_original || chunk.content;

    return (
        <div className="bg-gray-50 border-l-4 border-[#1f77b4] p-4 my-2 rounded-r-lg">
            <div className="text-[1.05rem] italic text-gray-900 mb-2">
                "{content}"
            </div>
            <div className="font-semibold text-gray-800">
                — {chunk.participant} ({chunk.participant_profile})
            </div>
            <div className="text-sm text-gray-500 mt-2">
                Score: {chunk.score.toFixed(3)}
            </div>
        </div>
    );
}
