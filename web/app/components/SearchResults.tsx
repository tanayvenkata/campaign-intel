'use client';

import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { GroupedResult, StrategyGroupedResult } from '../types';
import QuoteBlock from './QuoteBlock';
import SynthesisPanel from './SynthesisPanel';
import StrategySection from './StrategySection';
import { exportToMarkdown } from '../utils/exportMarkdown';
import { ENDPOINTS } from '../config/api';

interface SearchResultsProps {
    results: GroupedResult[];
    lessons?: StrategyGroupedResult[];
    query: string;
    stats?: {
        total_quotes: number;
        total_lessons?: number;
        focus_groups_count: number;
        races_count?: number;
        retrieval_time_ms: number;
    };
}

export default function SearchResults({ results, lessons = [], query, stats }: SearchResultsProps) {
    const [summaries, setSummaries] = useState<Record<string, string>>({});
    const [loadingSummaries, setLoadingSummaries] = useState<Set<string>>(new Set());
    const [selectedForMacro, setSelectedForMacro] = useState<Set<string>>(new Set());
    const [expandedCards, setExpandedCards] = useState<Set<string>>(new Set());
    const [macroResult, setMacroResult] = useState<string>('');
    const [isMacroLoading, setIsMacroLoading] = useState(false);
    const [isWaitingForSummaries, setIsWaitingForSummaries] = useState(false);
    const [isMacroPanelCollapsed, setIsMacroPanelCollapsed] = useState(false);
    // Deep synthesis per focus group (from SynthesisPanel)
    const [deepSyntheses, setDeepSyntheses] = useState<Record<string, string>>({});
    // Keep deepMacroThemes for export compatibility
    const [deepMacroThemes] = useState<Array<{ name: string; synthesis: string; focus_groups: string[] }>>([]);
    // Strategy summaries (from StrategySection)
    const [strategySummaries, setStrategySummaries] = useState<Record<string, string>>({});
    // Selected strategy races for macro synthesis
    const [selectedRaces, setSelectedRaces] = useState<Set<string>>(new Set());
    // Track last synthesized set to prevent redundancy
    const [lastSynthesizedSet, setLastSynthesizedSet] = useState<string>('');

    // Callback for SynthesisPanel to report deep synthesis
    const handleDeepSynthesisComplete = (fgId: string, synthesis: string) => {
        setDeepSyntheses(prev => ({ ...prev, [fgId]: synthesis }));
    };

    // Callback for StrategySection to report all summaries
    const handleStrategySummariesReady = (summaries: Record<string, string>) => {
        setStrategySummaries(summaries);
    };

    // Toggle race selection
    const toggleRaceSelection = (raceId: string) => {
        setSelectedRaces(prev => {
            const next = new Set(prev);
            if (next.has(raceId)) {
                next.delete(raceId);
            } else {
                next.add(raceId);
            }
            return next;
        });
    };

    // Auto-select all races when lessons arrive
    useEffect(() => {
        if (lessons.length > 0 && selectedRaces.size === 0) {
            setSelectedRaces(new Set(lessons.map(r => r.race_id)));
        }
    }, [lessons]);

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
                const res = await fetch(ENDPOINTS.synthesizeLight, {
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

    const selectAll = () => {
        setSelectedForMacro(new Set(results.map(r => r.focus_group_id)));
    };

    const deselectAll = () => {
        setSelectedForMacro(new Set());
    };

    const allSelected = results.length > 0 && selectedForMacro.size === results.length;

    // Track how many selected FGs have summaries ready
    const selectedFgIds = Array.from(selectedForMacro);
    const summariesReady = selectedFgIds.filter(fgId => summaries[fgId]).length;
    const allSummariesReady = selectedForMacro.size > 0 && summariesReady === selectedForMacro.size;

    // Auto-trigger macro synthesis when waiting and summaries become ready
    useEffect(() => {
        if (isWaitingForSummaries && allSummariesReady) {
            setIsWaitingForSummaries(false);
            handleMacroSynthesis();
        }
    }, [isWaitingForSummaries, allSummariesReady, summaries]);

    const handleExport = () => {
        exportToMarkdown({
            query,
            results,
            summaries,
            deepSyntheses,
            macroResult,
            deepMacroThemes,
            stats: stats ? {
                ...stats,
                total_lessons: stats.total_lessons,
                races_count: stats.races_count,
            } : undefined,
            lessons,
            strategySummaries,
        });
    };

    const handleMacroSynthesis = async () => {
        if (selectedForMacro.size === 0) return;

        // If summaries aren't ready, queue it up
        if (!allSummariesReady) {
            setIsWaitingForSummaries(true);
            return;
        }

        setIsMacroLoading(true);
        setMacroResult('');

        // Prepare FG data for macro synthesis
        const selectedResults = results.filter(r => selectedForMacro.has(r.focus_group_id));

        const fgQuotesPayload: Record<string, any[]> = {};
        const fgSummariesPayload: Record<string, string> = {};
        const fgMetadataPayload: Record<string, any> = {};

        selectedResults.forEach(r => {
            fgQuotesPayload[r.focus_group_id] = r.chunks;
            fgSummariesPayload[r.focus_group_id] = summaries[r.focus_group_id] || "Summary not available";
            fgMetadataPayload[r.focus_group_id] = r.focus_group_metadata;
        });

        // Prepare strategy data if available (only selected races)
        const strategyChunksPayload: Record<string, any[]> = {};
        const strategySummariesPayload: Record<string, string> = {};
        const strategyMetadataPayload: Record<string, any> = {};

        const selectedLessons = lessons.filter(race => selectedRaces.has(race.race_id));
        selectedLessons.forEach(race => {
            strategyChunksPayload[race.race_id] = race.chunks;
            strategySummariesPayload[race.race_id] = strategySummaries[race.race_id] || "Summary not available";
            strategyMetadataPayload[race.race_id] = race.race_metadata;
        });

        try {
            // Use unified endpoint if we have selected strategy races
            const hasStrategy = selectedLessons.length > 0 && Object.keys(strategySummaries).length > 0;
            const endpoint = hasStrategy ? ENDPOINTS.synthesizeUnifiedMacro : ENDPOINTS.synthesizeMacroLight;

            const payload = hasStrategy
                ? {
                    fg_summaries: fgSummariesPayload,
                    fg_quotes: fgQuotesPayload,
                    fg_metadata: fgMetadataPayload,
                    strategy_summaries: strategySummariesPayload,
                    strategy_chunks: strategyChunksPayload,
                    strategy_metadata: strategyMetadataPayload,
                    query: query
                }
                : {
                    fg_summaries: fgSummariesPayload,
                    top_quotes: fgQuotesPayload,
                    fg_metadata: fgMetadataPayload,
                    query: query
                };

            const response = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
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
            // Save the signature of what we just synthesized
            const currentSignature = Array.from(selectedForMacro).sort().join(',') + '|' + Array.from(selectedRaces).sort().join(',');
            setLastSynthesizedSet(currentSignature);
        }
    };

    // Check if current selection matches what we already synthesized
    const currentSelectionSignature = Array.from(selectedForMacro).sort().join(',') + '|' + Array.from(selectedRaces).sort().join(',');
    const isSelectionRedundant = macroResult && lastSynthesizedSet === currentSelectionSignature;

    // Scroll to specific section
    const scrollToSection = (id: string) => {
        const element = document.getElementById(id);
        if (element) {
            element.scrollIntoView({ behavior: 'smooth', block: 'start' });
            // Flash the card to indicate selection
            element.classList.add('ring-2', 'ring-slate-400', 'transition-all');
            setTimeout(() => {
                element.classList.remove('ring-2', 'ring-slate-400');
            }, 1000);
        }
    };

    return (
        <div className="space-y-8 relative">
            {/* Export Button */}
            <div className="flex justify-end gap-3">
                {/* Back to Top */}
                <button
                    onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
                    className="text-slate-400 hover:text-slate-600 text-xs font-mono uppercase tracking-wider flex items-center gap-1"
                >
                    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 10l7-7m0 0l7 7m-7-7v18" />
                    </svg>
                    Top
                </button>
                <button
                    onClick={handleExport}
                    className="flex items-center gap-2 bg-slate-100 text-slate-700 px-3 py-1.5 rounded-md hover:bg-slate-200 transition-colors text-xs font-bold font-mono uppercase tracking-wider"
                >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    Export
                </button>
            </div>

            {/* Research Synthesis - moved to top as high-level overview */}
            {(results.length > 0 || lessons.length > 0) && (
                <div className="bg-slate-50 p-5 border border-slate-200 shadow-sm mb-4 transition-all">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <button
                                onClick={() => setIsMacroPanelCollapsed(!isMacroPanelCollapsed)}
                                className="flex items-center gap-2 text-slate-700 hover:text-slate-900"
                            >
                                <svg
                                    className={`w-4 h-4 transition-transform ${isMacroPanelCollapsed ? '' : 'rotate-90'}`}
                                    fill="none"
                                    stroke="currentColor"
                                    viewBox="0 0 24 24"
                                >
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                                </svg>
                                <h3 className="font-serif font-bold text-slate-800 uppercase tracking-wide text-sm">Executive Synthesis</h3>
                            </button>
                            {!isMacroPanelCollapsed && (
                                <button
                                    onClick={allSelected ? deselectAll : selectAll}
                                    className="text-xs font-mono text-slate-500 hover:text-slate-800 uppercase tracking-wider"
                                >
                                    {allSelected ? '[Deselect All]' : '[Select All]'}
                                </button>
                            )}
                            {isMacroPanelCollapsed && macroResult && (
                                <span className="text-[10px] font-mono text-green-700 bg-green-50 border border-green-200 px-2 py-0.5 uppercase tracking-wider">
                                    Ready
                                </span>
                            )}
                        </div>
                        {!isMacroPanelCollapsed && (
                            <div className="flex items-center gap-4">
                                {/* Summary progress indicator */}
                                {selectedForMacro.size > 0 && !allSummariesReady && (
                                    <span className="text-xs font-mono text-amber-600 flex items-center gap-1.5 uppercase">
                                        <span className="w-2 h-2 bg-amber-500 rounded-full animate-pulse" />
                                        Processing: {summariesReady}/{selectedForMacro.size}
                                    </span>
                                )}
                                {selectedForMacro.size > 0 && allSummariesReady && !isWaitingForSummaries && !isMacroLoading && (
                                    <span className="text-xs font-mono text-green-700 flex items-center gap-1 uppercase">
                                        <span className="w-2 h-2 bg-green-500 rounded-full" />
                                        Ready
                                    </span>
                                )}
                                <button
                                    onClick={handleMacroSynthesis}
                                    disabled={(selectedForMacro.size === 0 && selectedRaces.size === 0) || isMacroLoading || isWaitingForSummaries || !!isSelectionRedundant}
                                    className="bg-slate-800 text-white px-4 py-2 hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed text-xs font-bold font-mono uppercase tracking-wider shadow-sm transition-colors"
                                >
                                    {isMacroLoading
                                        ? 'PRODUCING MEMO...'
                                        : isSelectionRedundant
                                            ? 'SYNTHESIS COMPLETE'
                                            : isWaitingForSummaries
                                                ? `QUEUED (${summariesReady}/${selectedForMacro.size})`
                                                : `SYNTHESIZE (${selectedForMacro.size + selectedRaces.size} sources)`}
                                </button>
                            </div>
                        )}
                    </div>

                    {!isMacroPanelCollapsed && (
                        <>
                            {/* Loading state for macro synthesis */}
                            {isMacroLoading && !macroResult && (
                                <div className="mt-4 p-4 bg-white border border-slate-200">
                                    <div className="space-y-2">
                                        <div className="flex items-center gap-2 text-xs font-mono text-slate-500 uppercase">
                                            <span className="w-3 h-3 border-2 border-slate-400 border-t-transparent rounded-full animate-spin" />
                                            <span>Analyst is processing {selectedForMacro.size} sources...</span>
                                        </div>
                                    </div>
                                </div>
                            )}

                            {/* Macro synthesis result */}
                            {macroResult && (
                                <div className="mt-4 p-6 bg-paper border border-slate-200 max-h-[60vh] overflow-y-auto">
                                    <div className="prose prose-sm max-w-none text-slate-800 font-serif leading-relaxed prose-headings:font-bold prose-headings:text-slate-900 prose-strong:text-slate-900">
                                        <ReactMarkdown>{macroResult}</ReactMarkdown>
                                    </div>
                                    {isMacroLoading && <span className="inline-block w-2 h-4 ml-1 bg-slate-400 animate-pulse" />}
                                </div>
                            )}
                        </>
                    )}
                </div>
            )}

            {/* Result Navigator (Pills) */}
            {results.length > 0 && (
                <div className="flex flex-wrap gap-3 pb-6 border-b border-slate-100">
                    <span className="text-xs font-mono font-bold text-slate-400 uppercase tracking-widest py-1.5">JUMP TO:</span>
                    {results.map((r) => (
                        <button
                            key={r.focus_group_id}
                            onClick={() => scrollToSection(r.focus_group_id)}
                            className="text-[10px] font-mono font-bold text-slate-500 bg-white border border-slate-200 px-3 py-1.5 hover:border-slate-400 hover:text-slate-800 transition-colors uppercase rounded-sm shadow-sm"
                        >
                            {r.focus_group_metadata.location || r.focus_group_id}
                        </button>
                    ))}
                </div>
            )}

            {/* Strategy Section (Campaign Lessons) */}
            <StrategySection
                lessons={lessons}
                query={query}
                onSummariesReady={handleStrategySummariesReady}
                selectedRaces={selectedRaces}
                onToggleRace={toggleRaceSelection}
            />

            {/* List Results with staggered animation */}
            {results.map((group, index) => {
                const fgId = group.focus_group_id;
                const isExpanded = expandedCards.has(fgId);
                const summary = summaries[fgId];
                const isLoadingSummary = loadingSummaries.has(fgId);

                return (
                    <div
                        id={fgId}
                        key={fgId}
                        className="bg-white border border-slate-200 shadow-sm hover:border-slate-300 transition-all duration-300 animate-fadeIn scroll-mt-24"
                        style={{ animationDelay: `${index * 75}ms` }}
                    >
                        {/* Memo Header */}
                        <div className="bg-slate-50 border-b border-slate-200 px-6 py-4 flex items-start justify-between">
                            <div className="flex items-center gap-3">
                                <input
                                    type="checkbox"
                                    checked={selectedForMacro.has(fgId)}
                                    onChange={() => toggleSelection(fgId)}
                                    className="w-4 h-4 text-slate-800 rounded border-slate-300 focus:ring-slate-800 cursor-pointer"
                                />
                                <div>
                                    <div className="flex items-center gap-3">
                                        <h2 className="text-sm font-bold font-serif text-slate-900 tracking-wide uppercase">
                                            {group.focus_group_metadata.location || fgId}
                                        </h2>
                                        <span className={`text-[10px] font-mono px-1.5 py-0.5 border ${group.focus_group_metadata.outcome === 'win'
                                            ? 'bg-green-50 border-green-200 text-green-700'
                                            : 'bg-red-50 border-red-200 text-red-700'
                                            } uppercase`}>
                                            {group.focus_group_metadata.outcome}
                                        </span>
                                    </div>
                                    <div className="text-xs font-mono text-slate-500 mt-1">
                                        {group.focus_group_metadata.race_name} • {group.focus_group_metadata.date}
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div className="p-6">
                            {/* Light Summary (auto-generated) */}
                            <div className="mb-6">
                                {isLoadingSummary ? (
                                    <div className="bg-paper p-4 border-l-2 border-amber-200 animate-pulse">
                                        <div className="h-4 bg-slate-100 rounded w-full mb-2" />
                                        <div className="h-4 bg-slate-100 rounded w-3/4" />
                                    </div>
                                ) : summary ? (
                                    <div className="bg-paper p-5 border-l-2 border-amber-400 text-sm text-slate-800 font-serif leading-relaxed">
                                        <span className="font-bold text-amber-900/50 text-xs font-mono uppercase tracking-wider block mb-2">Moderator Note</span>
                                        {summary}
                                    </div>
                                ) : null}
                            </div>

                            {/* Expandable Quotes Section */}
                            <div>
                                <button
                                    onClick={() => toggleExpanded(fgId)}
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
                        </div>

                        <SynthesisPanel
                            fgId={fgId}
                            fgName={group.focus_group_metadata.location || fgId}
                            quotes={group.chunks}
                            query={query}
                            onSynthesisComplete={handleDeepSynthesisComplete}
                        />
                    </div>
                );
            })}
        </div>
    );
}
