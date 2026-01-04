'use client';

import React, { useState, useEffect } from 'react';
import SearchResults from './components/SearchResults';
import StepLoader from './components/StepLoader';
import EmptyState from './components/EmptyState';
import { useStreamingSearch } from './hooks/useStreamingSearch';
import { prefetchSearch } from './utils/prefetch';

export default function Home() {
  const [query, setQuery] = useState('');
  const [searchedQuery, setSearchedQuery] = useState('');

  // Use streaming search hook
  const { search, reset, steps, data, isSearching, error } = useStreamingSearch();

  const clearSearch = () => {
    setQuery('');
    setSearchedQuery('');
    reset();
  };

  // Keyboard shortcut: Cmd+K to focus search
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        document.querySelector<HTMLInputElement>('input[type="text"]')?.focus();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) {
      setSearchedQuery(query);
      search(query);
    }
  };

  return (
    <main className="min-h-screen bg-gray-50 pb-20">
      {/* Header */}
      <div className="sticky top-0 z-20 bg-slate-50/95 backdrop-blur-md border-b border-slate-200 transition-all duration-300">
        <div className="max-w-7xl mx-auto px-4 py-3 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
              <h1 className="text-lg font-serif font-bold text-slate-900 tracking-tight">MERIDIAN INTELLIGENCE</h1>
            </div>
            {data && (
              <div className="flex gap-6 text-xs font-mono text-slate-500">
                <div className="flex flex-col items-end">
                  <span className="uppercase tracking-wider text-[10px] text-slate-400">Quotes</span>
                  <span className="font-semibold text-slate-700">{data.stats.total_quotes}</span>
                </div>
                <div className="flex flex-col items-end">
                  <span className="uppercase tracking-wider text-[10px] text-slate-400">Sources</span>
                  <span className="font-semibold text-slate-700">{data.stats.focus_groups_count}</span>
                </div>
                <div className="flex flex-col items-end">
                  <span className="uppercase tracking-wider text-[10px] text-slate-400">Latency</span>
                  <span className="font-semibold text-slate-700">{data.stats.retrieval_time_ms}ms</span>
                </div>
              </div>
            )}
          </div>

          <form onSubmit={handleSearch} className="mb-0">
            <div className="relative group">
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Enter Briefing Query..."
                className="w-full bg-slate-100 border-none rounded-none border-b-2 border-slate-200 focus:border-slate-800 px-0 py-4 text-xl font-serif text-slate-900 placeholder-slate-400 focus:ring-0 transition-colors"
                autoFocus
                spellCheck={false}
              />
              <div className="absolute right-0 top-1/2 -translate-y-1/2 flex items-center gap-2">
                {isSearching && (
                  <span className="text-xs font-mono text-slate-500 animate-pulse">INDEXING...</span>
                )}
                {query && !isSearching && (
                  <button
                    type="button"
                    onClick={clearSearch}
                    className="text-slate-400 hover:text-slate-600 p-2"
                  >
                    <span className="sr-only">Clear</span>
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                  </button>
                )}
              </div>
            </div>
          </form>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 py-8 sm:px-6 lg:px-8">
        {/* Error state */}
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-md flex items-center gap-3">
            <svg className="w-5 h-5 text-red-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span className="text-red-700">Unable to connect to search service. Please try again.</span>
          </div>
        )}

        {/* Show step loader while searching */}
        {isSearching && steps.length > 0 && (
          <StepLoader steps={steps} isComplete={!!data} />
        )}

        {/* Empty state - searched but no results */}
        {data && data.quotes.length === 0 && data.lessons.length === 0 && !isSearching && (
          <EmptyState query={searchedQuery} />
        )}

        {/* Show results */}
        {data && (data.quotes.length > 0 || data.lessons.length > 0) && (
          <div className="transition-opacity">
            <SearchResults
              results={data.quotes}
              lessons={data.lessons}
              query={searchedQuery}
              stats={data.stats}
            />
          </div>
        )}

        {/* Landing state - Live Corpus Stats */}
        {!data && !isSearching && (
          <div className="max-w-4xl mx-auto mt-16">
            <div className="border-t border-slate-200 pt-8">
              <h3 className="text-xs font-mono font-bold text-slate-400 uppercase tracking-widest mb-6">Live Corpus Index</h3>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
                <div className="p-6 bg-white border border-slate-200 shadow-sm hover:border-slate-300 transition-colors">
                  <div className="text-3xl font-serif font-bold text-slate-900 mb-1">37</div>
                  <div className="text-sm text-slate-500 font-medium">Active Focus Groups</div>
                  <div className="mt-4 text-xs font-mono text-slate-400">UPDATED: 2 DAYS AGO</div>
                </div>

                <div className="p-6 bg-white border border-slate-200 shadow-sm hover:border-slate-300 transition-colors">
                  <div className="text-3xl font-serif font-bold text-slate-900 mb-1">12</div>
                  <div className="text-sm text-slate-500 font-medium">Key Races</div>
                  <div className="mt-4 text-xs font-mono text-slate-400">COVERAGE: MIDWEST</div>
                </div>

                <div className="p-6 bg-white border border-slate-200 shadow-sm hover:border-slate-300 transition-colors">
                  <div className="text-3xl font-serif font-bold text-slate-900 mb-1">340+</div>
                  <div className="text-sm text-slate-500 font-medium">Voters Interviewed</div>
                  <div className="mt-4 text-xs font-mono text-slate-400">STATUS: VERIFIED</div>
                </div>
              </div>

              <div className="mt-12">
                <h3 className="text-xs font-mono font-bold text-slate-400 uppercase tracking-widest mb-4">Recent Internal Queries</h3>
                <div className="space-y-3">
                  {[
                    "What did Ohio voters say about the economy?",
                    "Show me quotes about working-class frustration",
                    "Why did we lose in Montana?",
                    "Distrust in institutions in Wisconsin"
                  ].map((q) => (
                    <button
                      key={q}
                      onClick={() => {
                        setQuery(q);
                        setSearchedQuery(q);
                        search(q);
                      }}
                      className="block w-full text-left group"
                    >
                      <span className="font-serif text-lg text-slate-600 group-hover:text-slate-900 border-b border-transparent group-hover:border-slate-300 transition-all">{q}</span>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Keyboard hint */}
        <div className="text-center mt-8 text-sm text-gray-400">
          Press <kbd className="px-2 py-1 bg-gray-100 rounded text-xs font-mono">⌘K</kbd> to focus search
        </div>
      </div>
        )}
    </div>
    </main >
  );
}

