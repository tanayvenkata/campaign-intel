'use client';

import React, { useState, useMemo, useCallback } from 'react';
import { useCorpusIndex, CorpusItem } from '../hooks/useCorpusIndex';

interface CorpusSidebarProps {
    isOpen: boolean;
    onToggle: () => void;
    onViewDocument: (item: CorpusItem) => void;
    activeDocId?: string;
    width?: number; // Optional to support backward compatibility or default
    onResize?: (width: number) => void;
    onLogoClick?: () => void; // Added to interface to match usage
}

export default function CorpusSidebar({
    isOpen,
    onToggle,
    onViewDocument,
    activeDocId,
    width = 280,
    onResize,
    onLogoClick
}: CorpusSidebarProps) {
    const { index, loading, error } = useCorpusIndex();
    const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());
    const [selectedYear, setSelectedYear] = useState<string>('all');

    const toggleGroup = (raceName: string) => {
        setExpandedGroups(prev => {
            const next = new Set(prev);
            if (next.has(raceName)) next.delete(raceName);
            else next.add(raceName);
            return next;
        });
    };

    // Resize Handler
    const handleMouseDown = useCallback((e: React.MouseEvent) => {
        e.preventDefault();
        const startX = e.clientX;
        const startWidth = width;

        const handleMouseMove = (mv: MouseEvent) => {
            if (!onResize) return;
            const newWidth = startWidth + (mv.clientX - startX);
            // Constrain width between 200px and 600px
            onResize(Math.max(200, Math.min(600, newWidth)));
        };

        const handleMouseUp = () => {
            document.removeEventListener('mousemove', handleMouseMove);
            document.removeEventListener('mouseup', handleMouseUp);
            document.body.style.cursor = 'default';
            document.body.style.userSelect = 'auto';
        };

        document.addEventListener('mousemove', handleMouseMove);
        document.addEventListener('mouseup', handleMouseUp);
        document.body.style.cursor = 'col-resize';
        document.body.style.userSelect = 'none';
    }, [width, onResize]);

    // Group items by Race Name with normalization
    const groupedItems = useMemo(() => {
        const groups: Record<string, CorpusItem[]> = {};

        index.forEach(item => {
            let groupName = item.race_name || 'Other';

            // Strategy Memo Categorization Fix
            if (item.type === 'strategy_memo') {
                const yearMatch = item.title.match(/20\d\d/);
                if (yearMatch && !groupName.includes(yearMatch[0])) {
                    groupName = `${groupName} ${yearMatch[0]}`;
                }
            }

            // Data overrides
            if (groupName === 'Wisconsin 2024') groupName = 'Wisconsin Senate 2024';
            if (groupName.trim() === 'Arizona Governor') groupName = 'Arizona Governor 2022';

            if (!groups[groupName]) groups[groupName] = [];
            groups[groupName].push(item);
        });
        return groups;
    }, [index]);

    const years = useMemo(() => {
        const unique = new Set<string>();
        Object.keys(groupedItems).forEach(name => {
            const m = name.match(/20\d\d/);
            if (m) unique.add(m[0]);
        });
        return Array.from(unique).sort().reverse();
    }, [groupedItems]);

    const sortedGroups = Object.keys(groupedItems).sort((a, b) => {
        const getYear = (s: string) => {
            const match = s.match(/20\d\d/);
            return match ? parseInt(match[0]) : 0;
        };
        const yearA = getYear(a);
        const yearB = getYear(b);
        if (yearA !== yearB) return yearB - yearA; // Descending
        return a.localeCompare(b);
    });

    const visibleGroups = useMemo(() => {
        if (selectedYear === 'all') return sortedGroups;
        return sortedGroups.filter(g => g.includes(selectedYear));
    }, [sortedGroups, selectedYear]);

    if (!isOpen) {
        return (
            <button
                onClick={onToggle}
                className="fixed left-0 top-[72px] z-30 bg-white border border-slate-200 p-2 shadow-sm rounded-r-md hover:bg-slate-50 transition-all group"
                title="Open Corpus Index"
            >
                <div className="w-4 h-4 text-slate-500 group-hover:text-slate-800">
                    <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                    </svg>
                </div>
            </button>
        );
    }

    return (
        <aside
            className="fixed left-0 top-[60px] bottom-0 bg-slate-50 border-r border-slate-200 z-40 flex flex-col font-sans shadow-none group/sidebar"
            style={{ width: width, transition: 'width 0.1s ease-out' }} // Faster transition during drag
        >
            {/* Resize Handle */}
            <div
                onMouseDown={handleMouseDown}
                className="absolute right-0 top-0 bottom-0 w-1 cursor-col-resize hover:bg-emerald-500/50 transition-colors z-20"
                title="Drag to resize"
            />

            <div className="h-[50px] px-5 border-b border-slate-200 flex items-center justify-between bg-slate-50/50 backdrop-blur-sm">
                <div className="flex items-center gap-2">
                    <svg className="w-3.5 h-3.5 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                    </svg>
                    <h3 className="text-[10px] font-bold text-slate-500 tracking-widest uppercase">
                        Research Index
                    </h3>
                </div>
                <button
                    onClick={onToggle}
                    className="text-slate-400 hover:text-slate-900 hover:bg-slate-200 p-1.5 rounded-md transition-colors"
                >
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                    </svg>
                </button>
            </div>

            <div className="px-4 py-2 border-b border-slate-100 bg-slate-50/50">
                <select
                    value={selectedYear}
                    onChange={(e) => setSelectedYear(e.target.value)}
                    className="w-full text-xs border border-slate-200 rounded px-2 py-1.5 bg-white text-slate-600 focus:outline-none focus:ring-1 focus:ring-slate-300 transition-shadow cursor-pointer appearance-none"
                    style={{ backgroundImage: 'url("data:image/svg+xml;charset=US-ASCII,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%22292.4%22%20height%3D%22292.4%22%3E%3Cpath%20fill%3D%22%2364748b%22%20d%3D%22M287%2069.4a17.6%2017.6%200%200%200-13-5.4H18.4c-5%200-9.3%201.8-12.9%205.4A17.6%2017.6%200%200%200%200%2082.2c0%205%201.8%209.3%205.4%2012.9l128%20127.9c3.6%203.6%207.8%205.4%2012.8%205.4s9.2-1.8%2012.8-5.4L287%2095c3.5-3.5%205.4-7.8%205.4-12.8%200-5-1.9-9.2-5.5-12.8z%22%2F%3E%3C%2Fsvg%3E")', backgroundRepeat: 'no-repeat', backgroundPosition: 'right 0.5rem center', backgroundSize: '0.6em' }}
                >
                    <option value="all">All Election Cycles</option>
                    {years.map(y => (
                        <option key={y} value={y}>{y} Cycle</option>
                    ))}
                </select>
            </div>

            <div className="flex-1 overflow-y-auto bg-slate-50/50 corpus-scrollbar">
                {loading ? (
                    <div className="p-4 space-y-4">
                        {[1, 2, 3].map((i) => (
                            <div key={i} className="space-y-2">
                                <div className="h-3 bg-slate-200/60 rounded w-1/2" />
                                <div className="pl-3 space-y-1.5">
                                    <div className="h-6 bg-slate-200/40 rounded w-full" />
                                    <div className="h-6 bg-slate-200/40 rounded w-full" />
                                </div>
                            </div>
                        ))}
                    </div>
                ) : error ? (
                    <div className="p-4">
                        <div className="p-2 text-xs text-red-600 bg-red-50 rounded border border-red-100 flex items-center gap-2">
                            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                            Failed to load.
                        </div>
                    </div>
                ) : (
                    <div className="pb-8">
                        {visibleGroups.map(raceName => {
                            const items = groupedItems[raceName];
                            const strategies = items.filter(i => i.type === 'strategy_memo');
                            const focusGroups = items.filter(i => i.type === 'focus_group');
                            const isExpanded = expandedGroups.has(raceName);

                            // Sort focus groups by title/location
                            focusGroups.sort((a, b) => (a.location || '').localeCompare(b.location || ''));

                            return (
                                <div key={raceName} className="group/section">
                                    <div
                                        onClick={() => toggleGroup(raceName)}
                                        className="px-4 py-2 bg-slate-100/80 sticky top-0 z-10 border-y border-slate-200 backdrop-blur-sm cursor-pointer hover:bg-slate-200/80 transition-colors flex items-center justify-between group/header"
                                    >
                                        <h4 className="text-[9px] font-bold text-slate-500 uppercase tracking-widest leading-none">
                                            {raceName}
                                        </h4>
                                        <svg
                                            className={`w-3 h-3 text-slate-400 transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`}
                                            fill="none"
                                            stroke="currentColor"
                                            viewBox="0 0 24 24"
                                        >
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                                        </svg>
                                    </div>

                                    {isExpanded && (
                                        <div className="px-1.5 py-1 space-y-0.5 animate-in slide-in-from-top-1 duration-200">
                                            {/* Strategy Memos */}
                                            {strategies.map(item => (
                                                <button
                                                    key={item.id}
                                                    onClick={() => onViewDocument(item)}
                                                    className={`w-full text-left flex items-start gap-2.5 px-2.5 py-1.5 rounded transition-all group ${activeDocId === item.id
                                                        ? 'bg-slate-100 text-slate-900 border border-slate-300 shadow-sm'
                                                        : 'hover:bg-white text-slate-600 hover:text-slate-900 hover:shadow-sm border border-transparent hover:border-slate-100'
                                                        }`}
                                                >
                                                    <div className={`mt-0.5 p-0.5 rounded ${activeDocId === item.id ? 'bg-slate-200 text-slate-700' : 'bg-slate-100 text-slate-400 group-hover:text-slate-600'}`}>
                                                        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                                        </svg>
                                                    </div>
                                                    <div className="min-w-0">
                                                        <div className={`text-[11px] font-bold uppercase tracking-tight ${activeDocId === item.id ? 'text-slate-900' : 'text-slate-700'}`}>
                                                            {item.title.replace('Strategy: ', '')}
                                                        </div>
                                                        <div className="text-[9px] text-slate-400 font-serif italic leading-tight truncate pr-1">
                                                            Strategy Memo
                                                        </div>
                                                    </div>
                                                </button>
                                            ))}

                                            {/* Focus Groups */}
                                            {focusGroups.map(item => (
                                                <button
                                                    key={item.id}
                                                    onClick={() => onViewDocument(item)}
                                                    className={`w-full text-left flex items-start gap-2.5 px-2.5 py-1.5 rounded transition-all group ${activeDocId === item.id
                                                        ? 'bg-white shadow-sm ring-1 ring-slate-200 z-10'
                                                        : 'hover:bg-white text-slate-600 hover:text-slate-900 hover:shadow-sm border border-transparent hover:border-slate-100'
                                                        }`}
                                                >
                                                    <div className="mt-1 flex-shrink-0">
                                                        <div className={`w-1.5 h-1.5 rounded-full ring-1 ring-offset-1 transition-all ${item.outcome === 'win'
                                                            ? 'bg-emerald-400 ring-emerald-100 group-hover:ring-emerald-200'
                                                            : 'bg-rose-400 ring-rose-100 group-hover:ring-rose-200'
                                                            }`} />
                                                    </div>
                                                    <div className="min-w-0">
                                                        <div className="text-[11px] font-medium truncate leading-tight text-slate-700 group-hover:text-slate-900">
                                                            {item.location || item.title}
                                                        </div>
                                                    </div>
                                                </button>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>

            <div className="px-5 py-4 border-t border-slate-200 bg-white shadow-[0_-4px_6px_-1px_rgba(0,0,0,0.05)]">
                <div className="flex items-center justify-between text-[10px] font-mono font-medium text-slate-400 uppercase">
                    <span>{index.length} Indexed Sources</span>
                    <div className="flex gap-2">
                        <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>Win</span>
                        <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-rose-400"></span>Loss</span>
                    </div>
                </div>
            </div>
        </aside>
    );
}
