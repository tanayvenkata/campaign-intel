'use client';

import React, { useState, useEffect, useCallback } from 'react';
import SearchResults from './components/SearchResults';
import SkeletonResults from './components/SkeletonResults';
import { SearchResponse } from './types';

export default function Home() {
  const [query, setQuery] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [data, setData] = useState<SearchResponse | null>(null);
  const [searchedQuery, setSearchedQuery] = useState('');

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

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setIsSearching(true);
    setSearchedQuery(query);
    // Keep stale data visible (dimmed) while loading - don't clear

    try {
      const res = await fetch('http://localhost:8000/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query,
          top_k: 5,
          score_threshold: 0.75
        }),
      });

      if (res.ok) {
        const json = await res.json();
        setData(json);
      } else {
        console.error('Search failed');
      }
    } catch (error) {
      console.error('Network error', error);
    } finally {
      setIsSearching(false);
    }
  };

  return (
    <main className="min-h-screen bg-gray-50 pb-20">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 sticky top-0 z-20">
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
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="What did Ohio voters say about the economy?"
              className="flex-1 rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm p-2 border"
              autoFocus
            />
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
        {/* Show skeleton loaders while searching (first search) */}
        {isSearching && !data && (
          <SkeletonResults count={3} />
        )}

        {/* Show stale results dimmed while loading new ones */}
        {data && (
          <div className={isSearching ? 'opacity-50 pointer-events-none transition-opacity' : 'transition-opacity'}>
            <SearchResults results={data.results} query={searchedQuery} />
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
                    onClick={() => {
                      setQuery(example.query);
                      // Auto-submit after setting query
                      setTimeout(() => {
                        document.querySelector<HTMLFormElement>('form')?.requestSubmit();
                      }, 100);
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
