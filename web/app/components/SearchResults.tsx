'use client';

import React, { useState, useEffect, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import { GroupedResult, StrategyGroupedResult } from '../types';
import RaceGroupComponent from './RaceGroup';
import { groupByRace, getSortedRaceGroups } from '../utils/groupByRace';
import { exportToMarkdown } from '../utils/exportMarkdown';
import { ENDPOINTS } from '../config/api';
import { CorpusItem } from '../hooks/useCorpusIndex';

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
    onViewDocument?: (item: CorpusItem) => void;
}

export default function SearchResults({ results, lessons = [], query, stats, onViewDocument }: SearchResultsProps) {
    // Focus group summaries and selection
    const [fgSummaries, setFgSummaries] = useState<Record<string, string>>({});
    const [loadingFgSummaries, setLoadingFgSummaries] = useState<Set<string>>(new Set());
    const [selectedForMacro, setSelectedForMacro] = useState<Set<string>>(new Set());

    // Strategy summaries and selection
    const [strategySummaries, setStrategySummaries] = useState<Record<string, string>>({});
    const [loadingStrategySummaries, setLoadingStrategySummaries] = useState<Set<string>>(new Set());
    const [selectedRaces, setSelectedRaces] = useState<Set<string>>(new Set());

    // Macro synthesis state
    const [macroResult, setMacroResult] = useState<string>('');
    const [isMacroLoading, setIsMacroLoading] = useState(false);
    const [isWaitingForSummaries, setIsWaitingForSummaries] = useState(false);
    const [isMacroPanelCollapsed, setIsMacroPanelCollapsed] = useState(false);

    // Deep synthesis per focus group
    const [deepSyntheses, setDeepSyntheses] = useState<Record<string, string>>({});
    const [lastSynthesizedSet, setLastSynthesizedSet] = useState<string>('');

    // Group results by race
    const raceGroups = useMemo(() => {
        const grouped = groupByRace(results, lessons);
        return getSortedRaceGroups(grouped);
    }, [results, lessons]);

    // Auto-select all on load
    useEffect(() => {
        if (results.length > 0 && selectedForMacro.size === 0) {
            setSelectedForMacro(new Set(results.map(r => r.focus_group_id)));
        }
        if (lessons.length > 0 && selectedRaces.size === 0) {
            setSelectedRaces(new Set(lessons.map(l => l.race_id)));
        }
    }, [results, lessons]);

    // Auto-generate FG summaries
    useEffect(() => {
        if (!results.length) return;

        results.forEach(async (group, index) => {
            const fgId = group.focus_group_id;
            if (fgSummaries[fgId] || loadingFgSummaries.has(fgId)) return;

            await new Promise(resolve => setTimeout(resolve, index * 200));

            setLoadingFgSummaries(prev => new Set(prev).add(fgId));

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
                    setFgSummaries(prev => ({ ...prev, [fgId]: data.summary }));
                }
            } catch (e) {
                console.error('Failed to generate summary for', fgId);
            } finally {
                setLoadingFgSummaries(prev => {
                    const next = new Set(prev);
                    next.delete(fgId);
                    return next;
                });
            }
        });
    }, [results, query]);

    // Auto-generate strategy summaries
    useEffect(() => {
        if (!lessons.length) return;

        lessons.forEach(async (race, index) => {
            if (strategySummaries[race.race_id] || loadingStrategySummaries.has(race.race_id)) return;

            await new Promise(resolve => setTimeout(resolve, index * 150));

            setLoadingStrategySummaries(prev => new Set(prev).add(race.race_id));

            const meta = race.race_metadata;
            const raceName = `${meta.state || 'Unknown'} ${meta.year || ''}`;

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

                if (res.ok) {
                    const data = await res.json();
                    setStrategySummaries(prev => ({ ...prev, [race.race_id]: data.summary }));
                }
            } catch (err) {
                console.error('Strategy summary error:', err);
            } finally {
                setLoadingStrategySummaries(prev => {
                    const next = new Set(prev);
                    next.delete(race.race_id);
                    return next;
                });
            }
        });
    }, [lessons, query]);

    // Callbacks
    const handleDeepSynthesisComplete = (fgId: string, synthesis: string) => {
        setDeepSyntheses(prev => ({ ...prev, [fgId]: synthesis }));
    };

    const toggleFocusGroupSelection = (fgId: string) => {
        setSelectedForMacro(prev => {
            const next = new Set(prev);
            if (next.has(fgId)) next.delete(fgId);
            else next.add(fgId);
            return next;
        });
    };

    const toggleRaceSelection = (raceId: string) => {
        setSelectedRaces(prev => {
            const next = new Set(prev);
            if (next.has(raceId)) next.delete(raceId);
            else next.add(raceId);
            return next;
        });
    };

    const selectAll = () => {
        setSelectedForMacro(new Set(results.map(r => r.focus_group_id)));
        setSelectedRaces(new Set(lessons.map(l => l.race_id)));
    };

    const deselectAll = () => {
        setSelectedForMacro(new Set());
        setSelectedRaces(new Set());
    };

    const allSelected = (results.length > 0 || lessons.length > 0) &&
        selectedForMacro.size === results.length &&
        selectedRaces.size === lessons.length;

    // Check if all summaries are ready
    const selectedFgIds = Array.from(selectedForMacro);
    const fgSummariesReady = selectedFgIds.filter(fgId => fgSummaries[fgId]).length;
    const allFgSummariesReady = selectedForMacro.size === 0 || fgSummariesReady === selectedForMacro.size;

    const selectedRaceIds = Array.from(selectedRaces);
    const strategySummariesReady = selectedRaceIds.filter(raceId => strategySummaries[raceId]).length;
    const allStrategySummariesReady = selectedRaces.size === 0 || strategySummariesReady === selectedRaces.size;

    const allSummariesReady = allFgSummariesReady && allStrategySummariesReady;

    // Auto-trigger macro synthesis when waiting and summaries become ready
    useEffect(() => {
        if (isWaitingForSummaries && allSummariesReady) {
            setIsWaitingForSummaries(false);
            handleMacroSynthesis();
        }
    }, [isWaitingForSummaries, allSummariesReady]);

    const handleExport = () => {
        exportToMarkdown({
            query,
            results,
            summaries: fgSummaries,
            deepSyntheses,
            macroResult,
            deepMacroThemes: [],
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
        if (selectedForMacro.size === 0 && selectedRaces.size === 0) return;

        if (!allSummariesReady) {
            setIsWaitingForSummaries(true);
            return;
        }

        setIsMacroLoading(true);
        setMacroResult('');

        const selectedResults = results.filter(r => selectedForMacro.has(r.focus_group_id));
        const fgQuotesPayload: Record<string, any[]> = {};
        const fgSummariesPayload: Record<string, string> = {};
        const fgMetadataPayload: Record<string, any> = {};

        selectedResults.forEach(r => {
            fgQuotesPayload[r.focus_group_id] = r.chunks;
            fgSummariesPayload[r.focus_group_id] = fgSummaries[r.focus_group_id] || "Summary not available";
            fgMetadataPayload[r.focus_group_id] = r.focus_group_metadata;
        });

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
            const hasStrategy = selectedLessons.length > 0;
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
            const currentSignature = Array.from(selectedForMacro).sort().join(',') + '|' + Array.from(selectedRaces).sort().join(',');
            setLastSynthesizedSet(currentSignature);
        }
    };

    const currentSelectionSignature = Array.from(selectedForMacro).sort().join(',') + '|' + Array.from(selectedRaces).sort().join(',');
    const isSelectionRedundant = macroResult && lastSynthesizedSet === currentSelectionSignature;

    const scrollToSection = (id: string) => {
        const element = document.getElementById(id);
        if (element) {
            element.scrollIntoView({ behavior: 'smooth', block: 'start' });
            element.classList.add('ring-2', 'ring-slate-400', 'transition-all');
            setTimeout(() => {
                element.classList.remove('ring-2', 'ring-slate-400');
            }, 1000);
        }
    };

    const totalSummariesNeeded = selectedForMacro.size + selectedRaces.size;
    const totalSummariesReady = fgSummariesReady + strategySummariesReady;

    return (
        <div className="space-y-8 relative">
            {/* Export Button */}
            <div className="flex justify-end gap-3">

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

            {/* Executive Synthesis Panel */}
            {(results.length > 0 || lessons.length > 0) && (
                <div className="bg-white border border-slate-200 shadow-xl shadow-slate-200/40 mb-8 transition-all rounded-sm overflow-hidden">
                    <div className="bg-slate-50 px-6 py-4 border-b border-slate-200 flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <button
                                onClick={() => setIsMacroPanelCollapsed(!isMacroPanelCollapsed)}
                                className="flex items-center gap-3 text-slate-900 group"
                            >
                                <svg
                                    className={`w-4 h-4 text-slate-400 group-hover:text-slate-900 transition-transform ${isMacroPanelCollapsed ? '' : 'rotate-90'}`}
                                    fill="none"
                                    stroke="currentColor"
                                    viewBox="0 0 24 24"
                                >
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                                </svg>
                                <h3 className="font-serif font-bold text-slate-900 uppercase tracking-widest text-sm">Executive Synthesis</h3>
                            </button>
                            {!isMacroPanelCollapsed && (
                                <button
                                    onClick={allSelected ? deselectAll : selectAll}
                                    className="ml-2 text-[10px] font-mono font-bold text-slate-400 hover:text-slate-900 uppercase tracking-widest border border-slate-200 px-2 py-0.5 rounded-sm hover:border-slate-400 transition-colors"
                                >
                                    {allSelected ? 'Deselect All' : 'Select All'}
                                </button>
                            )}
                            {isMacroPanelCollapsed && macroResult && (
                                <span className="text-[10px] font-mono font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 uppercase tracking-wider rounded-sm">
                                    Memo Ready
                                </span>
                            )}
                        </div>
                        {!isMacroPanelCollapsed && (
                            <div className="flex items-center gap-4">
                                {totalSummariesNeeded > 0 && !allSummariesReady && (
                                    <span className="text-xs font-mono text-slate-500 flex items-center gap-2 uppercase tracking-wide">
                                        <span className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-pulse" />
                                        Processing: {totalSummariesReady}/{totalSummariesNeeded}
                                    </span>
                                )}
                                {totalSummariesNeeded > 0 && allSummariesReady && !isWaitingForSummaries && !isMacroLoading && (
                                    <span className="text-xs font-mono font-bold text-emerald-700 flex items-center gap-1.5 uppercase tracking-wide">
                                        <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full" />
                                        Context Ready
                                    </span>
                                )}
                                <button
                                    onClick={handleMacroSynthesis}
                                    disabled={(selectedForMacro.size === 0 && selectedRaces.size === 0) || isMacroLoading || isWaitingForSummaries || !!isSelectionRedundant}
                                    className="bg-slate-900 text-white px-5 py-2 hover:bg-slate-800 disabled:opacity-50 disabled:cursor-not-allowed text-[11px] font-bold font-mono uppercase tracking-widest shadow-sm transition-all active:scale-95 rounded-sm"
                                >
                                    {isMacroLoading
                                        ? 'Drafting Memo...'
                                        : isSelectionRedundant
                                            ? 'Memo Complete'
                                            : isWaitingForSummaries
                                                ? `Queued`
                                                : `Generate Memo`}
                                </button>
                            </div>
                        )}
                    </div>

                    {!isMacroPanelCollapsed && (
                        <div className="p-0">
                            {isMacroLoading && !macroResult && (
                                <div className="p-12 text-center">
                                    <div className="inline-flex flex-col items-center gap-3">
                                        <div className="w-4 h-4 border-2 border-slate-900 border-t-transparent rounded-full animate-spin"></div>
                                        <span className="text-xs font-mono font-bold text-slate-500 uppercase tracking-widest">Synthesizing Strategy...</span>
                                    </div>
                                </div>
                            )}

                            {macroResult && (
                                <div className="p-8 bg-white max-h-[70vh] overflow-y-auto">
                                    <div className="prose prose-sm prose-slate max-w-4xl mx-auto text-slate-700 font-serif leading-relaxed prose-headings:font-bold prose-headings:font-serif prose-headings:tracking-tight prose-strong:text-slate-900 prose-a:text-blue-600 prose-p:my-3 prose-li:my-1">
                                        <ReactMarkdown>{macroResult}</ReactMarkdown>
                                    </div>
                                    {isMacroLoading && <span className="inline-block w-2 h-4 ml-1 bg-slate-900 animate-pulse" />}
                                </div>
                            )}
                        </div>
                    )}
                </div>
            )}

            {/* Race Navigator Pills */}
            {raceGroups.length > 0 && (
                <div className="flex flex-wrap gap-3 pb-6 border-b border-slate-100">
                    <span className="text-xs font-mono font-bold text-slate-400 uppercase tracking-widest py-1.5">JUMP TO:</span>
                    {raceGroups.map((rg) => (
                        <button
                            key={rg.raceKey}
                            onClick={() => scrollToSection(`race-${rg.raceKey}`)}
                            className="text-[10px] font-mono font-bold text-slate-500 bg-white border border-slate-200 px-3 py-1.5 hover:border-slate-400 hover:text-slate-800 transition-colors uppercase rounded-sm shadow-sm flex items-center gap-2"
                        >
                            <span className={`w-1.5 h-1.5 rounded-full ${rg.raceMetadata.outcome === 'win' ? 'bg-emerald-500' : 'bg-rose-500'}`} />
                            {rg.raceName}
                        </button>
                    ))}
                </div>
            )}

            {/* Race Groups */}
            {raceGroups.map((raceGroup, index) => (
                <div
                    key={raceGroup.raceKey}
                    id={`race-${raceGroup.raceKey}`}
                    className="scroll-mt-36"
                >
                    <RaceGroupComponent
                        raceGroup={raceGroup}
                        query={query}
                        selectedFocusGroups={selectedForMacro}
                        onToggleFocusGroup={toggleFocusGroupSelection}
                        selectedRaces={selectedRaces}
                        onToggleRace={toggleRaceSelection}
                        fgSummaries={fgSummaries}
                        loadingFgSummaries={loadingFgSummaries}
                        strategySummaries={strategySummaries}
                        loadingStrategySummaries={loadingStrategySummaries}
                        onViewDocument={onViewDocument}
                        onDeepSynthesisComplete={handleDeepSynthesisComplete}
                        animationDelay={index * 100}
                    />
                </div>
            ))}
        </div>
    );
}
