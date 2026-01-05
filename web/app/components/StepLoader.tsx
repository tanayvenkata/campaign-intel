'use client';

import React from 'react';
import { SearchStep } from '../hooks/useStreamingSearch';

interface StepLoaderProps {
    steps: SearchStep[];
    isComplete: boolean;
}

export default function StepLoader({ steps, isComplete }: StepLoaderProps) {
    return (
        <div className="bg-white border border-slate-200 shadow-sm p-4 mb-6">
            <div className="space-y-2">
                {steps.map((step, i) => (
                    <div
                        key={i}
                        className="flex items-center gap-2 text-sm animate-fadeIn"
                        style={{ animationDelay: `${i * 50}ms` }}
                    >
                        {step.step === 'complete' ? (
                            <svg className="w-4 h-4 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                            </svg>
                        ) : (
                            <svg className="w-4 h-4 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                            </svg>
                        )}
                        <span className="text-slate-700">{step.message}</span>
                    </div>
                ))}

                {!isComplete && (
                    <div className="flex items-center gap-2 text-sm">
                        <span className="w-4 h-4 border-2 border-slate-600 border-t-transparent rounded-full animate-spin" />
                        <span className="text-slate-500">Processing...</span>
                    </div>
                )}
            </div>
        </div>
    );
}
