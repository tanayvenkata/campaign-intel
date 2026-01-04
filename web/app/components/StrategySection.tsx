'use client';

import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { StrategyGroupedResult } from '../types';
import { ENDPOINTS } from '../config/api';

interface StrategySectionProps {
    lessons: StrategyGroupedResult[];
    query: string;
    onSummariesReady?: (summaries: Record<string, string>) => void;
    selectedRaces: Set<string>;
    onToggleRace: (raceId: string) => void;
}

interface RaceCardProps {
    race: StrategyGroupedResult;
    query: string;
    lightSummary: string;
    isLoadingSummary: boolean;
    isSelected: boolean;
    onToggle: () => void;
}

function RaceCard({ race, query, lightSummary, isLoadingSummary, isSelected, onToggle }: RaceCardProps) {
    const [isExpanded, setIsExpanded] = useState(false);
    const [deepSynthesis, setDeepSynthesis] = useState<string>('');
    const [isLoadingDeep, setIsLoadingDeep] = useState(false);

    const meta = race.race_metadata;
    const raceName = `${meta.state || 'Unknown'} ${meta.year || ''} (${meta.outcome || 'unknown'})`;
    const marginStr = meta.margin ? `${meta.margin > 0 ? '+' : ''}${meta.margin}%` : '';

    const handleDeepSynthesis = async () => {
        if (isLoadingDeep || deepSynthesis) return;
        setIsLoadingDeep(true);

        try {
            const res = await fetch(ENDPOINTS.synthesizeStrategyDeep, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    chunks: race.chunks,
                    query,
                    race_name: raceName,
                }),
            });

            if (!res.body) throw new Error('No response body');
            const reader = res.body.getReader();
            const decoder = new TextDecoder();

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                setDeepSynthesis(prev => prev + decoder.decode(value));
            }
        } catch (err) {
            console.error('Deep synthesis error:', err);
            setDeepSynthesis('Unable to generate deep synthesis.');
        } finally {
            setIsLoadingDeep(false);
        }
    };

    return (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
            <div
                className="flex items-center justify-between cursor-pointer"
                onClick={() => setIsExpanded(!isExpanded)}
            >
                <div className="flex items-center gap-2">
                    <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={(e) => { e.stopPropagation(); onToggle(); }}
                        onClick={(e) => e.stopPropagation()}
                        className="w-4 h-4 text-amber-600 rounded cursor-pointer"
                    />
                    <span className={`text-xs px-2 py-0.5 rounded font-medium ${
                        meta.outcome === 'win'
                            ? 'bg-green-100 text-green-800'
                            : 'bg-red-100 text-red-800'
                    }`}>
                        {meta.outcome === 'win' ? 'WIN' : 'LOSS'} {marginStr}
                    </span>
                    <h4 className="font-semibold text-gray-800">{raceName}</h4>
                </div>
                <button className="text-gray-500 hover:text-gray-700">
                    {isExpanded ? '▼' : '▶'}
                </button>
            </div>

            {/* Light Summary - always visible */}
            <div className="mt-2 text-sm text-gray-700">
                {isLoadingSummary ? (
                    <div className="flex items-center gap-2 text-amber-600">
                        <span className="w-3 h-3 border-2 border-amber-600 border-t-transparent rounded-full animate-spin" />
                        <span>Generating summary...</span>
                    </div>
                ) : (
                    <p>{lightSummary}</p>
                )}
            </div>

            {/* Expanded: show chunks + deep synthesis option */}
            {isExpanded && (
                <div className="mt-4 space-y-3">
                    {/* Deep Synthesis Button */}
                    <div className="flex items-center gap-2">
                        <button
                            onClick={(e) => { e.stopPropagation(); handleDeepSynthesis(); }}
                            disabled={isLoadingDeep || !!deepSynthesis}
                            className="text-xs bg-amber-600 text-white px-3 py-1.5 rounded hover:bg-amber-700 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            {isLoadingDeep ? 'Analyzing...' : deepSynthesis ? 'Analysis Complete' : 'Deep Analysis'}
                        </button>
                        {!deepSynthesis && !isLoadingDeep && (
                            <span className="text-xs text-gray-500">Detailed strategic breakdown</span>
                        )}
                    </div>

                    {/* Deep Synthesis Result */}
                    {(deepSynthesis || isLoadingDeep) && (
                        <div className="bg-amber-100 border border-amber-300 rounded-md p-3">
                            <div className="prose prose-sm max-w-none text-gray-800 prose-headings:font-bold prose-headings:text-amber-900">
                                <ReactMarkdown>{deepSynthesis}</ReactMarkdown>
                            </div>
                            {isLoadingDeep && <span className="inline-block w-2 h-4 ml-1 bg-amber-600 animate-pulse" />}
                        </div>
                    )}

                    <h5 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                        Strategy Excerpts ({race.chunks.length})
                    </h5>
                    {race.chunks.map((chunk, idx) => (
                        <div key={chunk.chunk_id || idx} className="bg-white border border-amber-100 rounded p-3">
                            <div className="flex items-center gap-2 text-xs text-gray-500 mb-1">
                                <span className="font-medium">{chunk.section}</span>
                                {chunk.subsection && (
                                    <>
                                        <span>•</span>
                                        <span>{chunk.subsection}</span>
                                    </>
                                )}
                            </div>
                            <p className="text-sm text-gray-800">{chunk.content}</p>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}

export default function StrategySection({ lessons, query, onSummariesReady, selectedRaces, onToggleRace }: StrategySectionProps) {
    const [isCollapsed, setIsCollapsed] = useState(true);
    const [summaries, setSummaries] = useState<Record<string, string>>({});
    const [loadingSummaries, setLoadingSummaries] = useState<Set<string>>(new Set());

    // Generate summaries eagerly on mount (even when collapsed)
    // This ensures they're ready for macro synthesis
    useEffect(() => {
        if (lessons.length === 0) return;

        lessons.forEach(async (race, index) => {
            if (summaries[race.race_id] || loadingSummaries.has(race.race_id)) return;

            // Stagger requests (strategy goes first, before FG summaries)
            await new Promise(resolve => setTimeout(resolve, index * 150));

            setLoadingSummaries(prev => new Set(prev).add(race.race_id));

            const meta = race.race_metadata;
            const raceName = `${meta.state || 'Unknown'} ${meta.year || ''} (${meta.outcome || 'unknown'})`;

            try {
                const res = await fetch(ENDPOINTS.synthesizeStrategyLight, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        chunks: race.chunks,
                        query,
                        race_name: raceName,
                    }),
                });

                if (!res.ok) throw new Error('Summary failed');
                const data = await res.json();

                setSummaries(prev => {
                    const updated = { ...prev, [race.race_id]: data.summary };
                    // Check if all summaries are ready
                    if (Object.keys(updated).length === lessons.length && onSummariesReady) {
                        onSummariesReady(updated);
                    }
                    return updated;
                });
            } catch (err) {
                console.error('Strategy summary error:', err);
                setSummaries(prev => ({ ...prev, [race.race_id]: 'Unable to generate summary.' }));
            } finally {
                setLoadingSummaries(prev => {
                    const next = new Set(prev);
                    next.delete(race.race_id);
                    return next;
                });
            }
        });
    }, [lessons, query]);

    if (lessons.length === 0) return null;

    // Count ready summaries for progress indicator
    const summariesReady = Object.keys(summaries).length;
    const allReady = summariesReady === lessons.length;

    return (
        <div className="mb-6">
            <div
                className="flex items-center justify-between p-3 bg-amber-100 border border-amber-300 rounded-lg cursor-pointer hover:bg-amber-150"
                onClick={() => setIsCollapsed(!isCollapsed)}
            >
                <div className="flex items-center gap-2">
                    <span className="text-amber-700 font-bold text-lg">📋</span>
                    <h3 className="font-semibold text-gray-800">
                        Campaign Lessons ({lessons.length} {lessons.length === 1 ? 'race' : 'races'})
                    </h3>
                    {/* Summary progress indicator */}
                    {!allReady && (
                        <span className="text-xs text-amber-600 flex items-center gap-1">
                            <span className="w-2 h-2 border border-amber-600 border-t-transparent rounded-full animate-spin" />
                            {summariesReady}/{lessons.length}
                        </span>
                    )}
                    {allReady && (
                        <span className="text-xs text-green-600">✓</span>
                    )}
                </div>
                <button className="text-gray-600 hover:text-gray-800 text-sm">
                    {isCollapsed ? 'Expand ▶' : 'Collapse ▼'}
                </button>
            </div>

            {!isCollapsed && (
                <div className="mt-3 space-y-3">
                    {lessons.map(race => (
                        <RaceCard
                            key={race.race_id}
                            race={race}
                            query={query}
                            lightSummary={summaries[race.race_id] || ''}
                            isLoadingSummary={loadingSummaries.has(race.race_id)}
                            isSelected={selectedRaces.has(race.race_id)}
                            onToggle={() => onToggleRace(race.race_id)}
                        />
                    ))}
                </div>
            )}

            {/* Collapsed preview */}
            {isCollapsed && (
                <div className="mt-2 text-sm text-gray-600 px-3">
                    {lessons.map(r => (
                        <span key={r.race_id} className="inline-flex items-center gap-1 mr-3">
                            <span className={`w-2 h-2 rounded-full ${
                                r.race_metadata.outcome === 'win' ? 'bg-green-500' : 'bg-red-500'
                            }`} />
                            {r.race_metadata.state} {r.race_metadata.year}
                        </span>
                    ))}
                </div>
            )}
        </div>
    );
}
