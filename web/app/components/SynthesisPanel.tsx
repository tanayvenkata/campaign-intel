'use client';

import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { RetrievalChunk } from '../types';
import { ENDPOINTS } from '../config/api';

interface SynthesisPanelProps {
    fgId: string;
    fgName: string;
    quotes: RetrievalChunk[];
    query: string;
    onSynthesisComplete?: (fgId: string, synthesis: string) => void;
}

export default function SynthesisPanel({ fgId, fgName, quotes, query, onSynthesisComplete }: SynthesisPanelProps) {
    const [synthesis, setSynthesis] = useState<string>('');
    const [isLoading, setIsLoading] = useState(false);
    const [hasGenerated, setHasGenerated] = useState(false);

    const handleDeepSynthesis = async () => {
        setIsLoading(true);
        setHasGenerated(true);
        setSynthesis('');

        try {
            const response = await fetch(ENDPOINTS.synthesizeDeep, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    quotes,
                    query,
                    focus_group_name: fgName
                }),
            });

            if (!response.ok) throw new Error('Synthesis failed');
            if (!response.body) throw new Error('No response body');

            const reader = response.body.getReader();
            const decoder = new TextDecoder();

            let fullSynthesis = '';
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                const text = decoder.decode(value);
                fullSynthesis += text;
                setSynthesis(fullSynthesis);
            }
            // Report completed synthesis to parent
            if (onSynthesisComplete) {
                onSynthesisComplete(fgId, fullSynthesis);
            }
        } catch (error) {
            console.error('Synthesis error:', error);
            setSynthesis('Error generating synthesis. Please try again.');
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="px-6 pb-6">
            {!hasGenerated ? (
                <button
                    onClick={handleDeepSynthesis}
                    disabled={isLoading}
                    className="flex items-center gap-2 text-xs font-bold text-slate-500 hover:text-slate-800 uppercase tracking-wider transition-colors disabled:opacity-50"
                >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.384-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
                    </svg>
                    {isLoading ? 'Generating Deep Synthesis...' : 'Generate Deep Synthesis'}
                </button>
            ) : (
                <div className="bg-slate-50 border border-slate-200 p-6 rounded-lg mt-2 relative overflow-hidden group">
                    <div className="absolute top-0 left-0 w-1 h-full bg-slate-300 group-hover:bg-slate-400 transition-colors" />
                    <h4 className="font-serif font-bold text-slate-900 mb-4 flex items-center gap-2 text-sm uppercase tracking-wide">
                        <svg className="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                        Deep Synthesis
                    </h4>

                    {isLoading && !synthesis ? (
                        <div className="space-y-3 py-2">
                            <div className="flex items-center gap-2 text-xs font-mono text-slate-500 uppercase animate-pulse">
                                <span>Analyzing {quotes.length} quotes...</span>
                            </div>
                            <div className="h-2 bg-slate-200 rounded w-3/4 animate-pulse" />
                            <div className="h-2 bg-slate-200 rounded w-1/2 animate-pulse" />
                        </div>
                    ) : (
                        <>
                            <div className="prose prose-sm max-w-none text-slate-700 font-serif leading-relaxed">
                                <ReactMarkdown>{synthesis}</ReactMarkdown>
                            </div>
                            {isLoading && <span className="inline-block w-2 h-4 ml-1 bg-slate-400 animate-pulse" />}
                        </>
                    )}
                </div>
            )}
        </div>
    );
}
