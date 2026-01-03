'use client';

import React, { useState, useEffect } from 'react';
import SearchResults from './components/SearchResults';
import StepLoader from './components/StepLoader';
import EmptyState from './components/EmptyState';
import { useStreamingSearch } from './hooks/useStreamingSearch';
import { prefetchSearch } from './hooks/useSearch';

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
      <div className="sticky top-0 z-20 bg-white/80 backdrop-blur-md border-b border-gray-200/50 transition-all duration-300">
        <div className="max-w-7xl mx-auto px-4 py-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Focus Group Search</h1>
              <p className="text-sm text-gray-500">V3 Retrieval + Synthesis Layer</p>
            </div>
            {data && (
              <div className="flex gap-4 text-sm text-gray-600">
                <div>
                  <span className="font-semibold">{data.stats.total_quotes}</span> quotes
                </div>
                <div>
                  <span className="font-semibold">{data.stats.focus_groups_count}</span> focus groups
                </div>
                <div>
                  <span className="font-semibold">{data.stats.retrieval_time_ms}ms</span> latency
                </div>
              </div>
            )}
          </div>

          <form onSubmit={handleSearch} className="flex gap-2">
            <div className="relative flex-1">
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="What did Ohio voters say about the economy?"
                className="w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm p-2 pr-8 border"
                autoFocus
              />
              {query && (
                <button
                  type="button"
                  onClick={clearSearch}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              )}
            </div>
            <button
              type="submit"
              disabled={isSearching}
              className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50"
            >
              {isSearching ? 'Searching...' : 'Search'}
            </button>
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
        {data && data.results.length === 0 && !isSearching && (
          <EmptyState query={searchedQuery} />
        )}

        {/* Show results */}
        {data && data.results.length > 0 && (
          <div className="transition-opacity">
            <SearchResults results={data.results} query={searchedQuery} stats={data.stats} />
          </div>
        )}

        {/* Landing state with guidance */}
        {!data && !isSearching && (
          <div className="max-w-2xl mx-auto mt-12">
            {/* Hero */}
            <div className="text-center mb-10">
              <h2 className="text-2xl font-bold text-gray-900 mb-3">
                Search 37 focus groups across 12 races
              </h2>
              <p className="text-gray-600">
                Surface institutional knowledge from historical focus groups. Every quote links back to its source transcript.
              </p>
            </div>

            {/* Example queries */}
            <div className="bg-white rounded-lg border border-gray-200 p-6 mb-6">
              <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-4">
                Try these queries
              </h3>
              <div className="space-y-2">
                {[
                  { query: "What did Ohio voters say about the economy?", desc: "Topic + location filter" },
                  { query: "Show me quotes about working-class frustration", desc: "Thematic search" },
                  { query: "What did swing voters say about the Democratic candidate?", desc: "Demographic filter" },
                  { query: "Why did we lose in Montana?", desc: "Outcome-based search" },
                ].map((example) => (
                  <button
                    key={example.query}
                    onMouseEnter={() => prefetchSearch(example.query)}
                    onClick={() => {
                      setQuery(example.query);
                      setSearchedQuery(example.query);
                      search(example.query);
                    }}
                    className="w-full text-left p-3 rounded-lg border border-gray-100 hover:border-indigo-200 hover:bg-indigo-50 transition-colors group"
                  >
                    <div className="font-medium text-gray-900 group-hover:text-indigo-700">
                      "{example.query}"
                    </div>
                    <div className="text-sm text-gray-500">{example.desc}</div>
                  </button>
                ))}
              </div>
            </div>

            {/* Quick tips */}
            <div className="grid grid-cols-3 gap-4 text-center">
              <div className="p-4 border border-gray-100 rounded-lg">
                <div className="w-8 h-8 mx-auto mb-2 bg-indigo-100 rounded-full flex items-center justify-center">
                  <svg className="w-4 h-4 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                </div>
                <div className="text-sm font-medium text-gray-900">Smart Routing</div>
                <div className="text-xs text-gray-500 mt-1">Queries auto-filter to relevant focus groups</div>
              </div>
              <div className="p-4 border border-gray-100 rounded-lg">
                <div className="w-8 h-8 mx-auto mb-2 bg-amber-100 rounded-full flex items-center justify-center">
                  <svg className="w-4 h-4 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                </div>
                <div className="text-sm font-medium text-gray-900">Auto Summaries</div>
                <div className="text-xs text-gray-500 mt-1">Each focus group gets a quick synthesis</div>
              </div>
              <div className="p-4 border border-gray-100 rounded-lg">
                <div className="w-8 h-8 mx-auto mb-2 bg-green-100 rounded-full flex items-center justify-center">
                  <svg className="w-4 h-4 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                  </svg>
                </div>
                <div className="text-sm font-medium text-gray-900">Cross-FG Analysis</div>
                <div className="text-xs text-gray-500 mt-1">Select multiple to find patterns</div>
              </div>
            </div>

            {/* Keyboard hint */}
            <div className="text-center mt-8 text-sm text-gray-400">
              Press <kbd className="px-2 py-1 bg-gray-100 rounded text-xs font-mono">⌘K</kbd> to focus search
            </div>
          </div>
        )}
      </div>
    </main>
  );
}

