'use client';

import React from 'react';
import { VisualAlignment } from '../components/VisualVariants';

export default function MockupPage() {
    return (
        <div className="min-h-screen bg-slate-50 font-sans text-slate-900">
            <header className="fixed top-0 left-0 right-0 z-50 h-[60px] bg-slate-50/95 backdrop-blur-md border-b border-slate-200 flex items-center justify-between px-6 shadow-sm">
                <div className="font-serif font-bold text-slate-900">MERIDIAN VISUAL LAB</div>
                <div className="text-xs font-mono text-slate-400">v2.1 Final Concept</div>
            </header>

            <main className="pt-[100px] pb-20 px-6 max-w-7xl mx-auto flex flex-col items-center justify-center min-h-[80vh]">

                <div className="text-center mb-12 space-y-6 max-w-3xl">
                    <h1 className="text-5xl font-serif font-bold text-slate-900 tracking-tight">Pattern Recognition</h1>
                    <p className="text-xl text-slate-500 font-light leading-relaxed">
                        The Meridian engine constantly scans the corpus for emerging signals.<br />
                        When alignment is detected across disparate sources, it locks in.
                    </p>
                </div>

                {/* Hero Visual Container */}
                <div className="w-full max-w-5xl aspect-[2/1] bg-white rounded-2xl border border-slate-200 shadow-xl overflow-hidden flex items-center justify-center relative p-12">
                    <div className="absolute inset-0 bg-slate-50/50" />
                    <div className="relative w-full h-full">
                        <VisualAlignment />
                    </div>
                </div>

            </main>
        </div>
    );
}
