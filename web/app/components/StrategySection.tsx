'use client';

import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { StrategyGroupedResult } from '../types';
import { ENDPOINTS } from '../config/api';

import { CorpusItem } from '../hooks/useCorpusIndex';

interface StrategySectionProps {
    lessons: StrategyGroupedResult[];
    query: string;
    onSummariesReady?: (summaries: Record<string, string>) => void;
    selectedRaces: Set<string>;
    onToggleRace: (raceId: string) => void;
    onViewDocument?: (item: CorpusItem) => void;
}

interface RaceCardProps {
    race: StrategyGroupedResult;
    query: string;
    lightSummary: string;
    isLoadingSummary: boolean;
    isSelected: boolean;
    onToggle: () => void;
    onViewDocument?: (item: CorpusItem) => void;
}

function RaceCard({ race, query, lightSummary, isLoadingSummary, isSelected, onToggle, onViewDocument }: RaceCardProps) {
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
        <div className="bg-white border border-slate-200 shadow-sm hover:border-slate-300 transition-all">
            <div
                className="flex items-center justify-between cursor-pointer px-6 py-4 bg-slate-50 border-b border-slate-200"
                onClick={() => setIsExpanded(!isExpanded)}
            >
                <div className="flex items-center gap-3">
                    <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={(e) => { e.stopPropagation(); onToggle(); }}
                        onClick={(e) => e.stopPropagation()}
                        className="w-4 h-4 text-slate-800 rounded border-slate-300 focus:ring-slate-800 cursor-pointer"
                    />
                    <span className={`text-[10px] font-mono font-bold px-2 py-0.5 border uppercase ${meta.outcome === 'win'
                        ? 'bg-emerald-50 border-emerald-200 text-emerald-700'
                        : 'bg-rose-50 border-rose-200 text-rose-700'
                        }`}>
                        {meta.outcome === 'win' ? 'WIN' : 'LOSS'} {marginStr}
                    </span>
                    <h4 className="font-serif font-bold text-slate-800 text-sm uppercase tracking-wide">{raceName}</h4>
                </div>
                <div className="flex items-center gap-3">
                    {onViewDocument && (
                        <button
                            onClick={(e) => {
                                e.stopPropagation();
                                onViewDocument({
                                    id: race.race_id,
                                    type: 'strategy_memo',
                                    title: `Strategy: ${raceName}`,
                                    location: meta.state,
                                    race_name: `${meta.state} ${meta.office}`,
                                    outcome: meta.outcome
                                });
                            }}
                            className="text-[10px] font-bold text-slate-600 hover:text-slate-800 uppercase tracking-wider flex items-center gap-1"
                        >
                            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                            </svg>
                            View Source
                        </button>
                    )}
                    <svg
                        className={`w-4 h-4 text-slate-500 transition-transform ${isExpanded ? 'rotate-90' : ''}`}
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                    >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                </div>
            </div>

            {/* Light Summary - always visible */}
            <div className="px-6 py-4">
                {isLoadingSummary ? (
                    <div className="bg-white p-4 border-l-2 border-slate-100 animate-pulse space-y-3">
                        <div className="h-2 bg-slate-100 rounded w-1/3" />
                        <div className="space-y-1.5">
                            <div className="h-3 bg-slate-50 rounded w-full" />
                            <div className="h-3 bg-slate-50 rounded w-5/6" />
                        </div>
                    </div>
                ) : lightSummary ? (
                    <div className="bg-paper p-5 border-l-2 border-slate-400 text-sm text-slate-800 font-serif leading-relaxed">
                        <span className="font-bold text-slate-600 text-xs font-mono uppercase tracking-wider block mb-2">Strategic Overview</span>
                        {lightSummary}
                    </div>
                ) : null}
            </div>

            {/* Expanded: show chunks + deep synthesis option */}
            {isExpanded && (
                <div className="px-6 pb-6 space-y-4">
                    {/* Deep Synthesis Button */}
                    <div className="flex items-center gap-2">
                        <button
                            onClick={(e) => { e.stopPropagation(); handleDeepSynthesis(); }}
                            disabled={isLoadingDeep || !!deepSynthesis}
                            className="flex items-center gap-2 text-xs font-bold text-slate-500 hover:text-slate-800 uppercase tracking-wider transition-colors disabled:opacity-50"
                        >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.384-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
                            </svg>
                            {isLoadingDeep ? 'Generating Deep Analysis...' : deepSynthesis ? 'Analysis Complete' : 'Generate Deep Analysis'}
                        </button>
                    </div>

                    {/* Deep Synthesis Result */}
                    {(deepSynthesis || isLoadingDeep) && (
                        <div className="bg-slate-50 border border-slate-200 relative overflow-hidden group">
                            <div className="absolute top-0 left-0 w-1 h-full bg-slate-300 group-hover:bg-slate-400 transition-colors" />
                            <div className="p-4 pl-6">
                                {isLoadingDeep && !deepSynthesis ? (
                                    <div className="space-y-2">
                                        <div className="flex items-center gap-2 text-xs font-mono text-slate-500 uppercase animate-pulse">
                                            <span>Analyzing strategy...</span>
                                        </div>
                                        <div className="h-2 bg-slate-200 rounded w-3/4 animate-pulse" />
                                        <div className="h-2 bg-slate-200 rounded w-1/2 animate-pulse" />
                                    </div>
                                ) : (
                                    <>
                                        <div className="prose prose-sm max-w-none text-slate-700 font-serif leading-relaxed prose-headings:font-bold prose-headings:text-slate-900">
                                            <ReactMarkdown>{deepSynthesis}</ReactMarkdown>
                                        </div>
                                        {isLoadingDeep && <span className="inline-block w-2 h-4 ml-1 bg-slate-400 animate-pulse" />}
                                    </>
                                )}
                            </div>
                        </div>
                    )}

                    <h5 className="text-xs font-mono font-bold text-slate-500 uppercase tracking-widest">
                        Strategy Excerpts ({race.chunks.length})
                    </h5>
                    {race.chunks.map((chunk, idx) => (
                        <div key={chunk.chunk_id || idx} className="bg-paper border-l-2 border-slate-300 p-4 hover:border-slate-800 transition-all">
                            <div className="flex items-center gap-2 text-xs font-mono text-slate-500 mb-2">
                                <span className="font-bold uppercase tracking-wider">{chunk.section}</span>
                                {chunk.subsection && (
                                    <>
                                        <span className="text-slate-300">|</span>
                                        <span>{chunk.subsection}</span>
                                    </>
                                )}
                            </div>
                            <p className="text-sm text-slate-800 font-serif leading-relaxed">{chunk.content}</p>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}

export default function StrategySection({ lessons, query, onSummariesReady, selectedRaces, onToggleRace, onViewDocument }: StrategySectionProps) {
    const [isCollapsed, setIsCollapsed] = useState(false); // Default expanded
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
        <div className="mb-8">
            <div
                className="flex items-center justify-between p-4 bg-slate-100 border border-slate-200 cursor-pointer hover:bg-slate-50 transition-colors"
                onClick={() => setIsCollapsed(!isCollapsed)}
            >
                <div className="flex items-center gap-3">
                    <svg className="w-5 h-5 text-slate-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    <h3 className="font-serif font-bold text-slate-800 text-sm uppercase tracking-wide">
                        Campaign Strategies ({lessons.length} {lessons.length === 1 ? 'race' : 'races'})
                    </h3>
                    {/* Summary progress indicator */}
                    {!allReady && (
                        <span className="text-xs font-mono text-slate-500 flex items-center gap-1.5 uppercase">
                            <span className="w-2 h-2 border border-slate-500 border-t-transparent rounded-full animate-spin" />
                            {summariesReady}/{lessons.length}
                        </span>
                    )}
                    {allReady && (
                        <span className="text-[10px] font-mono text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 uppercase tracking-wider">
                            Ready
                        </span>
                    )}
                </div>
                <svg
                    className={`w-4 h-4 text-slate-500 transition-transform ${isCollapsed ? '' : 'rotate-90'}`}
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
            </div>

            {!isCollapsed && (
                <div className="mt-4 space-y-4">
                    {lessons.map((race, index) => (
                        <div
                            key={race.race_id}
                            className="animate-fadeIn"
                            style={{ animationDelay: `${index * 75}ms` }}
                        >
                            <RaceCard
                                race={race}
                                query={query}
                                lightSummary={summaries[race.race_id] || ''}
                                isLoadingSummary={loadingSummaries.has(race.race_id)}
                                isSelected={selectedRaces.has(race.race_id)}
                                onToggle={() => onToggleRace(race.race_id)}
                                onViewDocument={onViewDocument}
                            />
                        </div>
                    ))}
                </div>
            )}

            {/* Collapsed preview */}
            {isCollapsed && (
                <div className="mt-2 text-sm text-slate-600 px-4">
                    {lessons.map(r => (
                        <span key={r.race_id} className="inline-flex items-center gap-1.5 mr-4">
                            <span className={`w-2 h-2 rounded-full ${r.race_metadata.outcome === 'win' ? 'bg-emerald-500' : 'bg-rose-500'
                                }`} />
                            <span className="font-mono text-xs">{r.race_metadata.state} {r.race_metadata.year}</span>
                        </span>
                    ))}
                </div>
            )}
        </div>
    );
}
