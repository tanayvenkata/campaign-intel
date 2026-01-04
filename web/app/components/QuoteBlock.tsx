import React from 'react';
import { RetrievalChunk } from '../types';

interface QuoteBlockProps {
    chunk: RetrievalChunk;
}

export default function QuoteBlock({ chunk }: QuoteBlockProps) {
    const content = chunk.content_original || chunk.content;

    return (
        <div className="bg-gray-50 border-l-4 border-indigo-500 p-5 rounded-r-lg hover:bg-gray-100 transition-colors duration-200 h-full flex flex-col shadow-sm hover:shadow-md">
            <div className="text-[1.05rem] text-gray-900 mb-4 font-serif leading-relaxed flex-grow">
                "{content}"
            </div>
            <div className="flex items-center justify-between text-xs text-gray-500 font-sans mt-auto pt-3 border-t border-gray-200">
                <div className="flex flex-col pr-2 min-w-0">
                    <span className="font-bold text-gray-900 truncate">— {chunk.participant}</span>
                    <span className="truncate text-[11px] block">{chunk.participant_profile}</span>
                    {chunk.source_file && chunk.line_number && (
                        <span className="text-[10px] text-gray-400 mt-1">
                            {chunk.source_file.split('/').pop()}, line {chunk.line_number}
                        </span>
                    )}
                </div>
                <span className="text-[10px] bg-gray-200 px-1.5 py-0.5 rounded-full flex-shrink-0 font-medium text-gray-600">
                    {chunk.score.toFixed(2)}
                </span>
            </div>
        </div>
    );
}
