'use client';

import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { GroupedResult, StrategyGroupedResult, RetrievalChunk, StrategyChunk } from '../types';
import { RaceGroup as RaceGroupType } from '../utils/groupByRace';
import { CorpusItem } from '../hooks/useCorpusIndex';
import { ENDPOINTS } from '../config/api';
import QuoteBlock from './QuoteBlock';
import SynthesisPanel from './SynthesisPanel';

interface RaceGroupProps {
    raceGroup: RaceGroupType;
    query: string;
    // Focus group selection
    selectedFocusGroups: Set<string>;
    onToggleFocusGroup: (fgId: string) => void;
    // Strategy selection
    selectedRaces: Set<string>;
    onToggleRace: (raceId: string) => void;
    // Summaries
    fgSummaries: Record<string, string>;
    loadingFgSummaries: Set<string>;
    strategySummaries: Record<string, string>;
    loadingStrategySummaries: Set<string>;
    // Document viewing
    onViewDocument?: (item: CorpusItem) => void;
    // Synthesis callbacks
    onDeepSynthesisComplete?: (fgId: string, synthesis: string) => void;
    // Animation delay
    animationDelay?: number;
}

// Strategy Card Component (inline)
function StrategyCard({
    strategy,
    query,
    lightSummary,
    isLoadingSummary,
    isSelected,
    onToggle,
    onViewDocument,
}: {
    strategy: StrategyGroupedResult;
    query: string;
    lightSummary: string;
    isLoadingSummary: boolean;
    isSelected: boolean;
    onToggle: () => void;
    onViewDocument?: (item: CorpusItem) => void;
}) {
    const [isExpanded, setIsExpanded] = useState(false);
    const [deepSynthesis, setDeepSynthesis] = useState('');
    const [isLoadingDeep, setIsLoadingDeep] = useState(false);

    const meta = strategy.race_metadata;
    const raceName = `${meta.state || 'Unknown'} ${meta.year || ''}`;

    const handleDeepSynthesis = async () => {
        if (isLoadingDeep || deepSynthesis) return;
        setIsLoadingDeep(true);

        try {
            const res = await fetch(ENDPOINTS.synthesizeStrategyDeep, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    chunks: strategy.chunks,
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
        <div className="bg-slate-50 border border-slate-200">
            <div
                className="flex items-center justify-between cursor-pointer px-6 py-4"
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
                    <svg className="w-4 h-4 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    <span className="text-xs font-mono font-bold text-slate-600 uppercase tracking-wider">Strategy Memo</span>
                </div>
                <div className="flex items-center gap-3">
                    {onViewDocument && (
                        <button
                            onClick={(e) => {
                                e.stopPropagation();
                                onViewDocument({
                                    id: strategy.race_id,
                                    type: 'strategy_memo',
                                    title: `Strategy: ${raceName}`,
                                    location: meta.state,
                                    race_name: `${meta.state} ${meta.office}`,
                                    outcome: meta.outcome
                                });
                            }}
                            className="text-[10px] font-bold text-slate-600 hover:text-slate-800 uppercase tracking-wider flex items-center gap-1"
                        >
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

            {/* Light Summary */}
            <div className="px-6 pb-4">
                {isLoadingSummary ? (
                    <div className="bg-paper p-4 border-l-2 border-slate-200 animate-pulse">
                        <div className="h-4 bg-slate-100 rounded w-full mb-2" />
                        <div className="h-4 bg-slate-100 rounded w-3/4" />
                    </div>
                ) : lightSummary ? (
                    <div className="bg-paper p-4 border-l-2 border-slate-400 text-sm text-slate-800 font-serif leading-relaxed">
                        <span className="font-bold text-slate-600 text-xs font-mono uppercase tracking-wider block mb-2">Strategic Overview</span>
                        {lightSummary}
                    </div>
                ) : null}
            </div>

            {/* Expanded content */}
            {isExpanded && (
                <div className="px-6 pb-6 space-y-4 border-t border-slate-200 pt-4">
                    {/* Deep Synthesis Button */}
                    <button
                        onClick={(e) => { e.stopPropagation(); handleDeepSynthesis(); }}
                        disabled={isLoadingDeep || !!deepSynthesis}
                        className="flex items-center gap-2 text-xs font-bold text-slate-500 hover:text-slate-800 uppercase tracking-wider transition-colors disabled:opacity-50"
                    >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.384-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
                        </svg>
                        {isLoadingDeep ? 'Generating...' : deepSynthesis ? 'Analysis Complete' : 'Generate Deep Analysis'}
                    </button>

                    {/* Deep Synthesis Result */}
                    {(deepSynthesis || isLoadingDeep) && (
                        <div className="bg-white border border-slate-200 relative overflow-hidden">
                            <div className="absolute top-0 left-0 w-1 h-full bg-slate-300" />
                            <div className="p-4 pl-6">
                                {isLoadingDeep && !deepSynthesis ? (
                                    <div className="space-y-2">
                                        <div className="h-2 bg-slate-200 rounded w-3/4 animate-pulse" />
                                        <div className="h-2 bg-slate-200 rounded w-1/2 animate-pulse" />
                                    </div>
                                ) : (
                                    <div className="prose prose-sm max-w-none text-slate-700 font-serif leading-relaxed">
                                        <ReactMarkdown>{deepSynthesis}</ReactMarkdown>
                                    </div>
                                )}
                            </div>
                        </div>
                    )}

                    {/* Strategy Excerpts */}
                    <h5 className="text-xs font-mono font-bold text-slate-500 uppercase tracking-widest">
                        Strategy Excerpts ({strategy.chunks.length})
                    </h5>
                    {strategy.chunks.map((chunk, idx) => (
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

// Focus Group Card Component (inline)
function FocusGroupCard({
    group,
    query,
    summary,
    isLoadingSummary,
    isSelected,
    onToggle,
    onViewDocument,
    onDeepSynthesisComplete,
}: {
    group: GroupedResult;
    query: string;
    summary: string;
    isLoadingSummary: boolean;
    isSelected: boolean;
    onToggle: () => void;
    onViewDocument?: (item: CorpusItem) => void;
    onDeepSynthesisComplete?: (fgId: string, synthesis: string) => void;
}) {
    const [isExpanded, setIsExpanded] = useState(false);
    const fgId = group.focus_group_id;

    return (
        <div className="bg-white border border-slate-200 shadow-sm hover:border-slate-300 transition-all">
            {/* Header */}
            <div className="bg-slate-50 border-b border-slate-200 px-6 py-4 flex items-start justify-between">
                <div className="flex items-center gap-3">
                    <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={onToggle}
                        className="w-4 h-4 text-slate-800 rounded border-slate-300 focus:ring-slate-800 cursor-pointer"
                    />
                    <div>
                        <h3 className="text-sm font-bold font-serif text-slate-900 tracking-wide uppercase">
                            {group.focus_group_metadata.location || fgId}
                        </h3>
                        <div className="flex items-center gap-3 mt-1">
                            <span className="text-xs font-mono text-slate-500">
                                {group.focus_group_metadata.date}
                            </span>
                            {onViewDocument && (
                                <>
                                    <span className="text-slate-300">|</span>
                                    <button
                                        onClick={() => onViewDocument({
                                            id: fgId,
                                            type: 'focus_group',
                                            title: group.focus_group_metadata.location || 'Focus Group Transcript',
                                            location: group.focus_group_metadata.location,
                                            race_name: group.focus_group_metadata.race_name,
                                            outcome: group.focus_group_metadata.outcome
                                        })}
                                        className="text-[10px] font-bold text-slate-600 hover:text-slate-800 uppercase tracking-wider flex items-center gap-1"
                                    >
                                        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                        </svg>
                                        Read Transcript
                                    </button>
                                </>
                            )}
                        </div>
                    </div>
                </div>
            </div>

            <div className="p-6">
                {/* Light Summary */}
                <div className="mb-6">
                    {isLoadingSummary ? (
                        <div className="bg-white p-4 border-l-2 border-slate-100 animate-pulse space-y-3">
                            <div className="h-2 bg-slate-100 rounded w-1/3" />
                            <div className="space-y-1.5">
                                <div className="h-3 bg-slate-50 rounded w-full" />
                                <div className="h-3 bg-slate-50 rounded w-5/6" />
                            </div>
                        </div>
                    ) : summary ? (
                        <div className="bg-paper p-5 border-l-2 border-slate-400 text-sm text-slate-800 font-serif leading-relaxed">
                            <span className="font-bold text-slate-600 text-xs font-mono uppercase tracking-wider block mb-2">Moderator Note</span>
                            {summary}
                        </div>
                    ) : null}
                </div>

                {/* Expandable Quotes Section */}
                <button
                    onClick={() => setIsExpanded(!isExpanded)}
                    className="flex items-center gap-2 text-xs font-mono text-slate-500 hover:text-slate-800 transition-colors uppercase tracking-wider"
                >
                    <svg
                        className={`w-3 h-3 transition-transform ${isExpanded ? 'rotate-90' : ''}`}
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                    >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                    {isExpanded ? 'Hide' : 'Review'} {group.chunks.length} Verbatim Quotes
                </button>

                {isExpanded && (
                    <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4 animate-fadeIn">
                        {group.chunks.map((chunk) => (
                            <QuoteBlock key={chunk.chunk_id} chunk={chunk} />
                        ))}
                    </div>
                )}
            </div>

            {/* Deep Synthesis Panel */}
            <SynthesisPanel
                fgId={fgId}
                fgName={group.focus_group_metadata.location || fgId}
                quotes={group.chunks}
                query={query}
                onSynthesisComplete={onDeepSynthesisComplete}
            />
        </div>
    );
}

export default function RaceGroup({
    raceGroup,
    query,
    selectedFocusGroups,
    onToggleFocusGroup,
    selectedRaces,
    onToggleRace,
    fgSummaries,
    loadingFgSummaries,
    strategySummaries,
    loadingStrategySummaries,
    onViewDocument,
    onDeepSynthesisComplete,
    animationDelay = 0,
}: RaceGroupProps) {
    const { raceName, raceMetadata, focusGroups, strategies } = raceGroup;
    const marginStr = raceMetadata.margin ? `${raceMetadata.margin > 0 ? '+' : ''}${raceMetadata.margin}%` : '';

    return (
        <div
            className="space-y-4 animate-fadeIn"
            style={{ animationDelay: `${animationDelay}ms` }}
        >
            {/* Race Header */}
            <div className="flex items-center gap-4 py-3 border-b border-slate-200">
                <span className={`text-[10px] font-mono font-bold px-2 py-0.5 border uppercase ${raceMetadata.outcome === 'win'
                    ? 'bg-emerald-50 border-emerald-200 text-emerald-700'
                    : 'bg-rose-50 border-rose-200 text-rose-700'
                    }`}>
                    {raceMetadata.outcome === 'win' ? 'WIN' : 'LOSS'} {marginStr}
                </span>
                <h2 className="text-lg font-serif font-bold text-slate-900 tracking-tight">
                    {raceName}
                </h2>
                <span className="text-xs font-mono text-slate-400 ml-auto">
                    {strategies.length > 0 && `${strategies.length} memo${strategies.length > 1 ? 's' : ''}`}
                    {strategies.length > 0 && focusGroups.length > 0 && ' + '}
                    {focusGroups.length > 0 && `${focusGroups.length} focus group${focusGroups.length > 1 ? 's' : ''}`}
                </span>
            </div>

            {/* Strategy Memos */}
            {strategies.map((strategy, idx) => (
                <StrategyCard
                    key={strategy.race_id}
                    strategy={strategy}
                    query={query}
                    lightSummary={strategySummaries[strategy.race_id] || ''}
                    isLoadingSummary={loadingStrategySummaries.has(strategy.race_id)}
                    isSelected={selectedRaces.has(strategy.race_id)}
                    onToggle={() => onToggleRace(strategy.race_id)}
                    onViewDocument={onViewDocument}
                />
            ))}

            {/* Focus Groups */}
            {focusGroups.map((group, idx) => (
                <FocusGroupCard
                    key={group.focus_group_id}
                    group={group}
                    query={query}
                    summary={fgSummaries[group.focus_group_id] || ''}
                    isLoadingSummary={loadingFgSummaries.has(group.focus_group_id)}
                    isSelected={selectedFocusGroups.has(group.focus_group_id)}
                    onToggle={() => onToggleFocusGroup(group.focus_group_id)}
                    onViewDocument={onViewDocument}
                    onDeepSynthesisComplete={onDeepSynthesisComplete}
                />
            ))}
        </div>
    );
}
