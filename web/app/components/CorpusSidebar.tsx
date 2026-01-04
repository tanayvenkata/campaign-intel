'use client';

import React, { useState } from 'react';
import { useCorpusIndex } from '../hooks/useCorpusIndex';

interface CorpusSidebarProps {
    isOpen: boolean;
    onToggle: () => void;
    onSelectFg?: (fgId: string) => void;
}

export default function CorpusSidebar({ isOpen, onToggle, onSelectFg }: CorpusSidebarProps) {
    const { index, loading } = useCorpusIndex();

    if (!isOpen) {
        return (
            <button
                onClick={onToggle}
                className="fixed left-0 top-32 z-30 bg-white border border-slate-200 p-2 shadow-sm rounded-r-md hover:bg-slate-50 transition-all"
                title="Open Corpus Index"
            >
                <svg className="w-4 h-4 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
            </button>
        );
    }

    return (
        <aside className="fixed left-0 top-0 bottom-0 w-64 bg-slate-50 border-r border-slate-200 z-10 pt-20 flex flex-col transition-all duration-300">
            <div className="px-4 py-3 border-b border-slate-200 flex items-center justify-between bg-slate-100/50">
                <h3 className="text-xs font-bold font-mono text-slate-500 uppercase tracking-wider">
                    Corpus Index
                </h3>
                <button
                    onClick={onToggle}
                    className="text-slate-400 hover:text-slate-600"
                >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                    </svg>
                </button>
            </div>

            <div className="flex-1 overflow-y-auto py-2">
                {loading ? (
                    <div className="px-4 py-2 space-y-2">
                        {[1, 2, 3, 4, 5].map((i) => (
                            <div key={i} className="h-4 bg-slate-200/50 rounded animate-pulse" />
                        ))}
                    </div>
                ) : (
                    <div className="space-y-6 px-4">
                        {/* Group by Race Name (simple grouping for now) */}
                        {Array.from(new Set(index.map(fg => fg.race_name))).map(race => (
                            <div key={race}>
                                <div className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2 border-b border-slate-200/50 pb-1">
                                    {race}
                                </div>
                                <ul className="space-y-1">
                                    {index.filter(fg => fg.race_name === race).map(fg => (
                                        <li key={fg.id}>
                                            <button
                                                onClick={() => onSelectFg?.(fg.id)}
                                                className="w-full text-left text-xs text-slate-600 hover:text-slate-900 font-medium py-1 truncate flex items-center gap-2 group"
                                            >
                                                <span className={`w-1.5 h-1.5 rounded-full ${fg.outcome === 'win' ? 'bg-green-400 group-hover:bg-green-500' : 'bg-red-400 group-hover:bg-red-500'}`} />
                                                <span className="truncate">{fg.location}</span>
                                            </button>
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            <div className="px-4 py-3 border-t border-slate-200 bg-white text-[10px] font-mono text-slate-400">
                {index.length} Active Sessions
            </div>
        </aside>
    );
}
