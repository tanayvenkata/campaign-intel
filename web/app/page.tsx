'use client';

import React, { useState, useEffect } from 'react';
import SearchResults from './components/SearchResults';
import StepLoader from './components/StepLoader';
import EmptyState from './components/EmptyState';
import CorpusSidebar from './components/CorpusSidebar';
import DocumentViewer from './components/DocumentViewer';
import { CorpusItem } from './hooks/useCorpusIndex';
import { useStreamingSearch } from './hooks/useStreamingSearch';
import { prefetchSearch } from './utils/prefetch';

export default function Home() {
  const [query, setQuery] = useState('');
  const [searchedQuery, setSearchedQuery] = useState('');
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [sidebarWidth, setSidebarWidth] = useState(280);
  const [viewedDoc, setViewedDoc] = useState<CorpusItem | null>(null);

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
    <>
      <CorpusSidebar
        isOpen={isSidebarOpen}
        onToggle={() => setIsSidebarOpen(!isSidebarOpen)}
        onViewDocument={setViewedDoc}
        width={sidebarWidth}
        onResize={setSidebarWidth}
        onLogoClick={clearSearch}
      />

      {viewedDoc && (
        <DocumentViewer
          docType={viewedDoc.type}
          docId={viewedDoc.id}
          title={viewedDoc.title}
          onClose={() => setViewedDoc(null)}
        />
      )}

      <main
        className="min-h-screen bg-slate-50 transition-all duration-75 ease-out"
        style={{ paddingLeft: isSidebarOpen ? sidebarWidth : 0, paddingTop: '60px' }}
      >
        {/* Persistent Header */}
        <header
          className="fixed top-0 left-0 right-0 z-50 h-[60px] bg-slate-50/95 backdrop-blur-md border-b border-slate-200 flex items-center justify-between px-4 md:px-6 shadow-sm transition-all duration-75 ease-out"
        >
          {/* Logo Section - Responsive Width */}
          <div
            className="w-[32px] md:w-[280px] flex-shrink-0 flex items-center gap-3 select-none cursor-pointer group"
            onClick={clearSearch}
          >
            <div className={`w-2.5 h-2.5 rounded-full shadow-sm transition-colors duration-500 ${isSearching ? 'bg-emerald-500 shadow-emerald-200' : 'bg-slate-900'}`} />
            <h1 className="hidden md:block text-lg font-serif font-bold tracking-tight text-slate-900 group-hover:text-slate-700 transition-colors whitespace-nowrap">
              MERIDIAN INTELLIGENCE
            </h1>
          </div>

          {/* Search Section - Centered */}
          <div className="flex-1 flex justify-center px-2 md:px-4">
            <form onSubmit={handleSearch} className="w-full max-w-2xl relative group">
              <div className="absolute inset-y-0 left-3 flex items-center pointer-events-none">
                {isSearching ? (
                  <div className="w-4 h-4 border-2 border-slate-400 border-t-transparent rounded-full animate-spin" />
                ) : (
                  <svg className="w-4 h-4 text-slate-400 group-focus-within:text-emerald-600 transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                )}
              </div>
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search protocols..."
                className="w-full pl-10 pr-10 py-1.5 bg-white border border-slate-200 rounded text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-emerald-500/50 focus:border-emerald-500/50 transition-all shadow-sm"
                autoFocus={true}
                spellCheck={false}
              />
              {query && (
                <button
                  type="button"
                  onClick={clearSearch}
                  className="absolute inset-y-0 right-0 pr-3 flex items-center text-slate-400 hover:text-slate-600"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                </button>
              )}
            </form>
          </div>

          {/* Status Section - Fixed Width Desktop */}
          <div className="hidden lg:flex w-[280px] flex-shrink-0 justify-end">
            {data ? (
              <div className="flex gap-6 text-xs font-mono text-slate-500">
                <div className="flex flex-col items-end">
                  <span className="uppercase tracking-widest text-[9px] text-slate-400">Quotes</span>
                  <span className="font-bold text-slate-900 leading-none">{data.stats.total_quotes}</span>
                </div>
                <div className="flex flex-col items-end">
                  <span className="uppercase tracking-widest text-[9px] text-slate-400">Sources</span>
                  <span className="font-bold text-slate-900 leading-none">{data.stats.focus_groups_count}</span>
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-end leading-none">
                <span className="text-[9px] font-mono text-slate-400 uppercase tracking-widest mb-0.5">System Status</span>
                <span className="text-[10px] font-bold text-emerald-600 tracking-wider">ACTIVE</span>
              </div>
            )}
          </div>

          {/* Mobile Spacer */}
          <div className="lg:hidden w-[32px] flex-shrink-0" />
        </header>


        {/* Main Content */}
        <div className="max-w-7xl mx-auto px-4 py-8 sm:px-6 lg:px-8">
          {/* Unified Landing State - Hero Search */}
          {/* Dashboard State (Landing) */}
          {!data && !isSearching && (
            <div className="max-w-4xl mx-auto mt-12 fade-in-up px-4">
              <div className="text-center mb-16">
                <h1 className="text-4xl md:text-5xl font-serif font-bold text-slate-900 tracking-tight mb-6 text-balance">
                  Intelligence Dashboard
                </h1>
                <p className="text-slate-500 text-lg font-light max-w-2xl mx-auto leading-relaxed text-balance">
                  Welcome to the Meridian strategic analysis terminal. <br className="hidden md:block" />
                  Select a suggested inquiry or enter a new protocol above.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-px bg-slate-200 rounded-lg overflow-hidden border border-slate-200 shadow-sm mb-12">
                {[
                  { val: "37", label: "Focus Groups", sub: "Indexed" },
                  { val: "12", label: "Key Races", sub: "Tracked" },
                  { val: "340+", label: "Voters", sub: "Interviewed" }
                ].map((stat, i) => (
                  <div key={i} className="bg-white p-8 group hover:bg-slate-50 transition-colors text-center relative">
                    <div className="text-4xl font-serif font-bold text-slate-900 mb-2">{stat.val}</div>
                    <div className="text-xs font-bold font-mono text-slate-500 uppercase tracking-widest mb-1">{stat.label}</div>
                    <div className="text-[10px] text-slate-400 font-mono">{stat.sub}</div>
                  </div>
                ))}
              </div>

              <div className="text-center">
                <p className="text-xs font-mono font-bold text-slate-400 uppercase tracking-widest mb-6">Suggested Inquiries</p>
                <div className="flex flex-wrap justify-center gap-3">
                  {[
                    "Ohio voters on economy",
                    "Working-class frustration",
                    "Montana loss analysis",
                    "Trust in Wisconsin"
                  ].map((q) => (
                    <button
                      key={q}
                      onClick={() => {
                        setQuery(q);
                        setSearchedQuery(q);
                        search(q);
                      }}
                      className="px-5 py-2.5 bg-white border border-slate-200 rounded-full text-sm font-medium text-slate-600 hover:text-slate-900 hover:border-slate-400 hover:shadow-sm transition-all active:scale-95"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

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
            <div className="transition-opacity animate-fadeIn">
              <SearchResults
                results={data.quotes}
                lessons={data.lessons}
                query={searchedQuery}
                stats={data.stats}
                onViewDocument={setViewedDoc}
              />
            </div>
          )}

          {/* Keyboard hint */}
          {!data && !isSearching && (
            <div className="text-center mt-20 text-xs text-slate-300 font-mono">
              Running v2.0-Alpha • Press <kbd className="font-sans px-1 bg-slate-100 rounded text-slate-500">⌘K</kbd> to focus
            </div>
          )}
        </div>
      </main>
    </>
  );
}
