'use client';

import React from 'react';
import { VisualDistillation, VisualConsensus, VisualTranscript, VisualAlignment, VisualLoom } from '../components/VisualVariants';

export default function MockupPage() {
    return (
        <div className="min-h-screen bg-slate-50 font-sans text-slate-900">
            <header className="fixed top-0 left-0 right-0 z-50 h-[60px] bg-slate-50/95 backdrop-blur-md border-b border-slate-200 flex items-center justify-between px-6 shadow-sm">
                <div className="font-serif font-bold text-slate-900">MERIDIAN VISUAL LAB</div>
                <div className="text-xs font-mono text-slate-400">v2.1 Semantics</div>
            </header>

            <main className="pt-[80px] pb-20 px-6 max-w-7xl mx-auto">
                <div className="text-center mb-16 space-y-4">
                    <h1 className="text-4xl font-serif font-bold text-slate-900">Process Visualization Concepts</h1>
                    <p className="text-slate-500 max-w-2xl mx-auto">
                        Abstract representations of Qualitative Data Analysis. <br />
                        Moving from raw, unstructured inputs to coherent strategic insight.
                    </p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">

                    {/* Variant 1: The Distillation */}
                    <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden flex flex-col group hover:shadow-md transition-all">
                        <div className="h-[240px] bg-slate-50/50 flex items-center justify-center relative p-8">
                            <VisualDistillation />
                        </div>
                        <div className="p-6 border-t border-slate-100">
                            <h3 className="font-serif font-bold text-lg text-slate-900">The Distillation</h3>
                            <p className="text-sm text-slate-500 mt-2">Synthesizing thousands of noise points (quotes) into a single strategic beam.</p>
                        </div>
                    </div>

                    {/* Variant 2: The Consensus */}
                    <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden flex flex-col group hover:shadow-md transition-all">
                        <div className="h-[240px] bg-slate-50/50 flex items-center justify-center relative p-8">
                            <VisualConsensus />
                        </div>
                        <div className="p-6 border-t border-slate-100">
                            <h3 className="font-serif font-bold text-lg text-slate-900">The Consensus</h3>
                            <p className="text-sm text-slate-500 mt-2">Identifying shared sentiment as disparate nodes resonate in unison.</p>
                        </div>
                    </div>

                    {/* Variant 3: The Transcript */}
                    <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden flex flex-col group hover:shadow-md transition-all">
                        <div className="h-[240px] bg-slate-50/50 flex items-center justify-center relative p-8">
                            <VisualTranscript />
                        </div>
                        <div className="p-6 border-t border-slate-100">
                            <h3 className="font-serif font-bold text-lg text-slate-900">The Transcript</h3>
                            <p className="text-sm text-slate-500 mt-2">Scanning unstructured documents to extract and tag high-value signals.</p>
                        </div>
                    </div>

                    {/* Variant 4: The Alignment */}
                    <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden flex flex-col group hover:shadow-md transition-all">
                        <div className="h-[240px] bg-slate-50/50 flex items-center justify-center relative p-8">
                            <VisualAlignment />
                        </div>
                        <div className="p-6 border-t border-slate-100">
                            <h3 className="font-serif font-bold text-lg text-slate-900">The Alignment</h3>
                            <p className="text-sm text-slate-500 mt-2">Pattern recognition: Finding the emerging trend direction amidst random noise.</p>
                        </div>
                    </div>

                    {/* Variant 5: The Loom */}
                    <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden flex flex-col group hover:shadow-md transition-all">
                        <div className="h-[240px] bg-slate-50/50 flex items-center justify-center relative p-8">
                            <VisualLoom />
                        </div>
                        <div className="p-6 border-t border-slate-100">
                            <h3 className="font-serif font-bold text-lg text-slate-900">The Loom</h3>
                            <p className="text-sm text-slate-500 mt-2">Weaving cross-race threads and demographics into a unified strategy fabric.</p>
                        </div>
                    </div>

                </div>
            </main>
        </div>
    );
}
