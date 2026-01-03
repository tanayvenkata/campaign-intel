'use client';

import React from 'react';

interface EmptyStateProps {
    query: string;
}

export default function EmptyState({ query }: EmptyStateProps) {
    return (
        <div className="flex flex-col items-center justify-center py-16 px-4">
            <svg
                className="w-16 h-16 text-gray-300 mb-4"
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
            <h3 className="text-lg font-medium text-gray-900 mb-2">
                No results found
            </h3>
            <p className="text-gray-500 text-center max-w-md mb-4">
                No focus groups mentioned "<span className="font-medium">{query}</span>".
            </p>
            <p className="text-sm text-gray-400">
                Try searching for broader terms like "economy", "inflation", or "healthcare".
            </p>
        </div>
    );
}
