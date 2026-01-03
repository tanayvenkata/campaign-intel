'use client';

import React, { useState, useEffect } from 'react';
import { GroupedResult } from '../types';
import QuoteBlock from './QuoteBlock';
import SynthesisPanel from './SynthesisPanel';

interface SearchResultsProps {
    results: GroupedResult[];
    query: string;
}

export default function SearchResults({ results, query }: SearchResultsProps) {
    const [summaries, setSummaries] = useState<Record<string, string>>({});
    const [loadingSummaries, setLoadingSummaries] = useState<Set<string>>(new Set());
    const [selectedForMacro, setSelectedForMacro] = useState<Set<string>>(new Set());
    const [expandedCards, setExpandedCards] = useState<Set<string>>(new Set());
    const [macroResult, setMacroResult] = useState<string>('');
    const [isMacroLoading, setIsMacroLoading] = useState(false);

    // Auto-generate light summaries when results change
    useEffect(() => {
        if (!results.length) return;

        // Generate summaries for FGs that don't have one yet
        results.forEach(async (group, index) => {
            const fgId = group.focus_group_id;
            if (summaries[fgId] || loadingSummaries.has(fgId)) return;

            // Stagger requests to avoid overwhelming the server
            await new Promise(resolve => setTimeout(resolve, index * 200));

            setLoadingSummaries(prev => new Set(prev).add(fgId));

            try {
                const res = await fetch('http://localhost:8000/synthesize/light', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        quotes: group.chunks,
                        query,
                        focus_group_name: group.focus_group_metadata.location || fgId
                    })
                });

                if (res.ok) {
                    const data = await res.json();
                    setSummaries(prev => ({ ...prev, [fgId]: data.summary }));
                }
            } catch (e) {
                console.error('Failed to generate summary for', fgId);
            } finally {
                setLoadingSummaries(prev => {
                    const next = new Set(prev);
                    next.delete(fgId);
                    return next;
                });
            }
        });
    }, [results, query]);

    const toggleExpanded = (fgId: string) => {
        setExpandedCards(prev => {
            const next = new Set(prev);
            if (next.has(fgId)) {
                next.delete(fgId);
            } else {
                next.add(fgId);
            }
            return next;
        });
    };

    const toggleSelection = (fgId: string) => {
        const newSet = new Set(selectedForMacro);
        if (newSet.has(fgId)) {
            newSet.delete(fgId);
        } else {
            newSet.add(fgId);
        }
        setSelectedForMacro(newSet);
    };

    const handleMacroSynthesis = async () => {
        if (selectedForMacro.size === 0) return;

        setIsMacroLoading(true);
        setMacroResult('');

        // Prepare data for macro synthesis
        // We need summaries first - if we don't have them, we might skip or generate them on fly.
        // The current backend endpoint expects 'fg_summaries' and 'top_quotes'.
        // Use placeholders if summary missing or fetch them.

        // Simplification: We'll pass empty summaries if not present, but real app should rely on them.
        // In this plan, we haven't implemented auto-light-summary fetching yet in the frontend.
        // For now, let's assume we proceed without pre-fetched summaries, asking the backend 
        // to potentially handle it or just use quotes.
        // Actually, the backend prompt uses summaries. 

        // Let's filter the results
        const selectedResults = results.filter(r => selectedForMacro.has(r.focus_group_id));

        const topQuotesPayload: Record<string, any[]> = {};
        const summariesPayload: Record<string, string> = {};

        selectedResults.forEach(r => {
            topQuotesPayload[r.focus_group_id] = r.chunks;
            summariesPayload[r.focus_group_id] = summaries[r.focus_group_id] || "Summary not available";
        });

        try {
            const response = await fetch('http://localhost:8000/synthesize/macro', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    fg_summaries: summariesPayload,
                    top_quotes: topQuotesPayload,
                    query: query
                })
            });

            if (!response.body) return;
            const reader = response.body.getReader();
            const decoder = new TextDecoder();

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                setMacroResult(prev => prev + decoder.decode(value));
            }
        } catch (e) {
            console.error(e);
            setMacroResult("Error generating macro synthesis.");
        } finally {
            setIsMacroLoading(false);
        }
    };

    return (
        <div className="space-y-8">
            {/* Macro Synthesis Controls */}
            {results.length > 1 && (
                <div className="bg-white p-4 rounded-lg border border-gray-200 shadow-sm sticky top-4 z-10">
                    <div className="flex items-center justify-between mb-2">
                        <h3 className="font-semibold text-gray-700">Cross-Focus Group Analysis</h3>
                        <button
                            onClick={handleMacroSynthesis}
                            disabled={selectedForMacro.size === 0 || isMacroLoading}
                            className="bg-indigo-600 text-white px-4 py-2 rounded-md hover:bg-indigo-700 disabled:opacity-50 text-sm"
                        >
                            {isMacroLoading ? 'Synthesizing...' : `Synthesize Selected (${selectedForMacro.size})`}
                        </button>
                    </div>

                    {macroResult && (
                        <div className="mt-4 p-4 bg-green-50 border border-green-200 rounded-md prose prose-sm max-w-none">
                            <div className="whitespace-pre-wrap">{macroResult}</div>
                        </div>
                    )}
                </div>
            )}

            {/* List Results with staggered animation */}
            {results.map((group, index) => {
                const fgId = group.focus_group_id;
                const isExpanded = expandedCards.has(fgId);
                const summary = summaries[fgId];
                const isLoadingSummary = loadingSummaries.has(fgId);

                return (
                    <div
                        key={fgId}
                        className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 animate-fadeIn"
                        style={{ animationDelay: `${index * 75}ms` }}
                    >
                        <div className="flex items-start justify-between">
                            <div className="flex-1">
                                <div className="flex items-center gap-2">
                                    <input
                                        type="checkbox"
                                        checked={selectedForMacro.has(fgId)}
                                        onChange={() => toggleSelection(fgId)}
                                        className="w-4 h-4 text-indigo-600 rounded cursor-pointer"
                                    />
                                    <h2 className="text-xl font-bold text-gray-900">
                                        {group.focus_group_metadata.location || fgId}
                                    </h2>
                                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                                        group.focus_group_metadata.outcome === 'win'
                                            ? 'bg-green-100 text-green-700'
                                            : 'bg-red-100 text-red-700'
                                    }`}>
                                        {group.focus_group_metadata.outcome}
                                    </span>
                                </div>
                                <p className="text-gray-600 mt-1 text-sm">
                                    {group.focus_group_metadata.race_name} • {group.focus_group_metadata.date}
                                </p>
                            </div>
                        </div>

                        {/* Light Summary (auto-generated) */}
                        <div className="mt-4">
                            {isLoadingSummary ? (
                                <div className="bg-amber-50 border-l-4 border-amber-200 p-3 animate-pulse">
                                    <div className="h-4 bg-amber-100 rounded w-full mb-2" />
                                    <div className="h-4 bg-amber-100 rounded w-3/4" />
                                </div>
                            ) : summary ? (
                                <div className="bg-amber-50 border-l-4 border-amber-400 p-3 text-sm text-gray-700 italic">
                                    {summary}
                                </div>
                            ) : null}
                        </div>

                        {/* Expandable Quotes Section */}
                        <div className="mt-4">
                            <button
                                onClick={() => toggleExpanded(fgId)}
                                className="flex items-center gap-2 text-sm text-gray-600 hover:text-gray-900 transition-colors"
                            >
                                <svg
                                    className={`w-4 h-4 transition-transform ${isExpanded ? 'rotate-90' : ''}`}
                                    fill="none"
                                    stroke="currentColor"
                                    viewBox="0 0 24 24"
                                >
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                                </svg>
                                {isExpanded ? 'Hide' : 'Show'} {group.chunks.length} quotes
                            </button>

                            {isExpanded && (
                                <div className="mt-3 space-y-3 animate-fadeIn">
                                    {group.chunks.map((chunk) => (
                                        <QuoteBlock key={chunk.chunk_id} chunk={chunk} />
                                    ))}
                                </div>
                            )}
                        </div>

                        <SynthesisPanel
                            fgId={fgId}
                            fgName={group.focus_group_metadata.location || fgId}
                            quotes={group.chunks}
                            query={query}
                        />
                    </div>
                );
            })}
        </div>
    );
}
