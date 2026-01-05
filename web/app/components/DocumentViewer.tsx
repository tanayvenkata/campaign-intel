
'use client';

import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { ENDPOINTS } from '../config/api';

interface DocumentViewerProps {
    docType: 'focus_group' | 'strategy_memo';
    docId: string;
    title: string;
    onClose: () => void;
}

export default function DocumentViewer({ docType, docId, title, onClose }: DocumentViewerProps) {
    const [content, setContent] = useState<string>('');
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        async function fetchContent() {
            setLoading(true);
            try {
                const res = await fetch(`${ENDPOINTS.corpus}/${docType}/${docId}`);
                if (!res.ok) throw new Error('Failed to load document content');

                const data = await res.json();
                setContent(data.content);
            } catch (e) {
                console.error(e);
                setError('Failed to load document content');
            } finally {
                setLoading(false);
            }
        }

        fetchContent();
    }, [docType, docId]);

    return (
        <div
            className="fixed inset-0 z-[60] flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4 transition-all duration-300 animate-fadeIn"
            onClick={onClose}
        >
            <div
                className="bg-white w-full max-w-4xl h-[85vh] rounded-xl shadow-2xl flex flex-col overflow-hidden animate-slideUp transform transition-all"
                onClick={(e) => e.stopPropagation()}
            >
                {/* Header */}
                <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-white text-slate-800">
                    <div>
                        <h2 className="text-xl font-bold font-serif text-slate-900 tracking-tight">{title}</h2>
                        <div className="text-xs font-bold font-mono text-slate-400 uppercase tracking-widest flex gap-2 mt-1">
                            <span className="flex items-center gap-1">
                                {docType === 'strategy_memo' ? (
                                    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
                                ) : (
                                    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0z" /></svg>
                                )}
                                {docType.replace('_', ' ')}
                            </span>
                            <span className="text-slate-300">|</span>
                            <span>{docId}</span>
                        </div>
                    </div>
                    <button
                        onClick={onClose}
                        className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-full transition-all"
                        title="Close (Esc)"
                    >
                        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>

                {/* Content */}
                <div className="flex-1 overflow-y-auto p-8 bg-white cursor-auto">
                    {loading ? (
                        <div className="space-y-6 animate-pulse max-w-3xl mx-auto mt-10">
                            <div className="flex gap-4">
                                <div className="h-4 bg-slate-100 rounded w-1/4"></div>
                                <div className="h-4 bg-slate-100 rounded w-1/4"></div>
                            </div>
                            <div className="space-y-3">
                                <div className="h-4 bg-slate-100 rounded w-full"></div>
                                <div className="h-4 bg-slate-100 rounded w-full"></div>
                                <div className="h-4 bg-slate-100 rounded w-5/6"></div>
                            </div>
                            <div className="h-64 bg-slate-50 rounded-lg w-full mt-8 border border-slate-100"></div>
                        </div>
                    ) : error ? (
                        <div className="flex flex-col items-center justify-center h-full text-slate-400">
                            <div className="bg-red-50 p-4 rounded-full mb-4">
                                <svg className="w-8 h-8 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>
                            </div>
                            <div className="text-lg font-medium text-slate-700 mb-1">Error Loading Document</div>
                            <p className="text-sm">{error}</p>
                        </div>
                    ) : (
                        <div className="prose prose-slate prose-sm max-w-3xl mx-auto font-serif leading-relaxed 
                            prose-headings:font-bold prose-headings:text-slate-900 
                            prose-h1:text-xl prose-h1:mb-4 prose-h1:tracking-tight
                            prose-h2:text-lg prose-h2:mt-6 prose-h2:mb-3 prose-h2:border-b prose-h2:border-slate-200 prose-h2:pb-1
                            prose-p:text-slate-700 prose-p:leading-6
                            prose-blockquote:border-l-2 prose-blockquote:border-slate-400 prose-blockquote:bg-slate-50 prose-blockquote:py-1 prose-blockquote:px-4 prose-blockquote:rounded-r prose-blockquote:not-italic prose-blockquote:text-slate-700
                            prose-strong:text-slate-900 prose-strong:font-bold
                            prose-li:text-slate-700">
                            <ReactMarkdown>{content}</ReactMarkdown>
                        </div>
                    )}
                </div>

                {/* Footer */}
                <div className="px-6 py-4 border-t border-slate-200 bg-slate-50 flex justify-between items-center">
                    <div className="text-xs text-slate-400 font-mono">
                        {docType === 'focus_group' ? 'TRANSCRIPT' : 'STRATEGIC MEMO'} // CONFIDENTIAL
                    </div>
                    <button
                        onClick={onClose}
                        className="px-6 py-2 bg-white border border-slate-200 text-slate-600 hover:text-slate-900 hover:border-slate-300 hover:bg-slate-50 rounded-md text-xs font-bold uppercase tracking-wider transition-all shadow-sm"
                    >
                        Close Viewer
                    </button>
                </div>
            </div>
        </div>
    );
}
