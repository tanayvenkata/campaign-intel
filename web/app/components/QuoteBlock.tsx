import React from 'react';
import { RetrievalChunk } from '../types';

interface QuoteBlockProps {
    chunk: RetrievalChunk;
}

export default function QuoteBlock({ chunk }: QuoteBlockProps) {
    const content = chunk.content_original || chunk.content;

    return (
        <div className="bg-paper border-l-2 border-slate-300 p-4 rounded-r hover:bg-white hover:border-slate-800 transition-all duration-200 h-full flex flex-col group">
            <div className="text-sm text-slate-800 mb-3 font-serif leading-relaxed flex-grow">
                "{content}"
            </div>
            <div className="flex items-end justify-between text-[10px] text-slate-400 font-mono mt-auto pt-2 border-t border-slate-200/50">
                <div className="flex flex-col pr-2 min-w-0">
                    <span className="font-bold text-slate-600 truncate uppercase tracking-wide group-hover:text-slate-900 transition-colors">— {chunk.participant}</span>
                    <span className="truncate block opacity-75">{chunk.participant_profile}</span>
                </div>
                <span className="bg-slate-100 px-1.5 py-0.5 rounded text-slate-500 font-bold">
                    {chunk.score.toFixed(2)}
                </span>
            </div>
        </div>
    );
}
