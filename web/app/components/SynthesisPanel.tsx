'use client';

import React, { useState, useRef } from 'react';
import { RetrievalChunk } from '../types';

interface SynthesisPanelProps {
    fgId: string;
    fgName: string;
    quotes: RetrievalChunk[];
    query: string;
}

export default function SynthesisPanel({ fgId, fgName, quotes, query }: SynthesisPanelProps) {
    const [synthesis, setSynthesis] = useState<string>('');
    const [isLoading, setIsLoading] = useState(false);
    const [hasGenerated, setHasGenerated] = useState(false);

    const handleDeepSynthesis = async () => {
        setIsLoading(true);
        setHasGenerated(true);
        setSynthesis('');

        try {
            const response = await fetch('http://localhost:8000/synthesize/deep', {
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

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                const text = decoder.decode(value);
                setSynthesis((prev) => prev + text);
            }
        } catch (error) {
            console.error('Synthesis error:', error);
            setSynthesis('Error generating synthesis. Please try again.');
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="mt-4">
            {!hasGenerated ? (
                <button
                    onClick={handleDeepSynthesis}
                    disabled={isLoading}
                    className="px-4 py-2 bg-white border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[#1f77b4]"
                >
                    {isLoading ? 'Generating...' : 'Deep Synthesis'}
                </button>
            ) : (
                <div className="bg-[#e7f5ff] border border-[#74c0fc] p-4 rounded-lg mt-2 text-gray-800">
                    <h4 className="font-semibold mb-2">Deep Synthesis: {fgName}</h4>
                    <div className="whitespace-pre-wrap">{synthesis}</div>
                    {isLoading && <span className="inline-block w-2 h-4 ml-1 bg-[#1f77b4] animate-pulse" />}
                </div>
            )}
        </div>
    );
}
