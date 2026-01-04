'use client';

import React from 'react';

interface EmptyStateProps {
    query: string;
}

export default function EmptyState({ query }: EmptyStateProps) {
    return (
        <div className="flex flex-col items-center justify-center py-20 px-4 border border-dashed border-slate-300 rounded-lg bg-slate-50 mt-8">
            <div className="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center mb-4">
                <svg
                    className="w-6 h-6 text-slate-400"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                >
                    <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={1.5}
                        d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                    />
                </svg>
            </div>
            <h3 className="text-lg font-serif font-medium text-slate-900 mb-2">
                Zero Index Matches
            </h3>
            <p className="text-slate-500 text-center max-w-md mb-6 font-mono text-sm border-b border-slate-200 pb-4">
                Query: "{query}"
            </p>
            <p className="text-sm text-slate-400">
                Try broadening your criteria or checking spelling.
            </p>
        </div>
    );
}
