'use client';

import React from 'react';

// Shared Props
interface VisualProps {
    className?: string;
}

// THE ALIGNMENT: Narrative Arc (Noise -> Scan -> Process -> Insight)
export function VisualAlignment({ className = "" }: VisualProps) {
    const width = 800;
    const height = 400;
    const cx = 400;
    const cy = 200;

    // Grid setup (Expanded for Hero)
    const compasses = [];
    const rows = 6;
    const cols = 12;
    for (let x = 0; x < cols; x++) {
        for (let y = 0; y < rows; y++) {
            compasses.push({
                x: 70 + x * 60,
                y: 50 + y * 50,
                id: `${x}-${y}`,
                rand: Math.random()
            });
        }
    }

    return (
        <svg viewBox={`0 0 ${width} ${height}`} className={`w-full h-full ${className}`}>
            <defs>
                <radialGradient id="queryPulse" cx="0.5" cy="0.5" r="0.5">
                    <stop offset="0%" stopColor="#10b981" stopOpacity="0.4" />
                    <stop offset="100%" stopColor="#10b981" stopOpacity="0" />
                </radialGradient>
            </defs>

            {/* The Query Input (Central Pulse) */}
            <circle cx={cx} cy={cy} r="0" fill="url(#queryPulse)">
                <animate attributeName="r" values="0; 600" dur="12s" begin="0s" repeatCount="indefinite" />
                <animate attributeName="opacity" values="0; 1; 0" keyTimes="0; 0.3; 1" dur="12s" begin="0s" repeatCount="indefinite" />
            </circle>

            {/* Scene Labels */}
            <g className="text-xs font-mono uppercase tracking-widest" textAnchor="middle">
                {/* 0-25% Awaiting Signal */}
                <text x={cx} y={height - 20} fill="#94a3b8" opacity="0">
                    Awaiting Signal
                    <animate attributeName="opacity" values="1; 1; 0; 0" keyTimes="0; 0.23; 0.25; 1" dur="12s" repeatCount="indefinite" />
                </text>

                {/* 25-50% Scanning Corpus */}
                <text x={cx} y={height - 20} fill="#64748b" opacity="0">
                    Scanning Corpus
                    <animate attributeName="opacity" values="0; 0; 1; 1; 0; 0" keyTimes="0; 0.25; 0.27; 0.48; 0.50; 1" dur="12s" repeatCount="indefinite" />
                </text>

                {/* 50-66% Synthesizing */}
                <text x={cx} y={height - 20} fill="#475569" opacity="0">
                    Synthesizing
                    <animate attributeName="opacity" values="0; 0; 1; 1; 0; 0" keyTimes="0; 0.50; 0.52; 0.64; 0.66; 1" dur="12s" repeatCount="indefinite" />
                </text>

                {/* 66-91% Pattern Detected */}
                <text x={cx} y={height - 20} fill="#10b981" opacity="0" fontWeight="bold">
                    Pattern Detected
                    <animate attributeName="opacity" values="0; 0; 1; 1; 0; 0" keyTimes="0; 0.66; 0.68; 0.89; 0.91; 1" dur="12s" repeatCount="indefinite" />
                </text>
            </g>

            {/* Compasses */}
            {compasses.map((c, i) => {
                const rStart = Math.floor(c.rand * 360);
                const rEnd = rStart + 45;

                return (
                    <g key={i} transform={`translate(${c.x}, ${c.y})`}>
                        <circle r="2" fill="#e2e8f0" />
                        <line x1="-12" y1="0" x2="12" y2="0" strokeWidth="1.5" strokeLinecap="round">
                            <animateTransform
                                attributeName="transform"
                                type="rotate"
                                values={`${rStart}; ${rEnd}; 0; 90; 0; ${rStart + 180}; ${rStart - 180}; 45; 45; ${rStart}`}
                                keyTimes="0; 0.25; 0.28; 0.38; 0.5; 0.55; 0.60; 0.66; 0.91; 1"
                                dur="12s"
                                repeatCount="indefinite"
                                calcMode="spline"
                                keySplines="0.4 0 0.2 1; 0.4 0 0.2 1; 0.4 0 0.2 1; 0.4 0 0.2 1; 0.4 0 0.2 1; 0.4 0 0.2 1; 0.4 0 0.2 1; 0.4 0 0.2 1; 0.4 0 0.2 1"
                            />
                            <animate
                                attributeName="stroke"
                                values="#94a3b8; #94a3b8; #64748b; #64748b; #10b981; #10b981; #94a3b8"
                                keyTimes="0; 0.5; 0.55; 0.6; 0.66; 0.91; 1"
                                dur="12s"
                                repeatCount="indefinite"
                            />
                        </line>
                        <circle cx="12" cy="0" r="1.5">
                            <animateTransform
                                attributeName="transform"
                                type="rotate"
                                values={`${rStart}; ${rEnd}; 0; 90; 0; ${rStart + 180}; ${rStart - 180}; 45; 45; ${rStart}`}
                                keyTimes="0; 0.25; 0.28; 0.38; 0.5; 0.55; 0.60; 0.66; 0.91; 1"
                                dur="12s"
                                repeatCount="indefinite"
                                calcMode="spline"
                                keySplines="0.4 0 0.2 1; 0.4 0 0.2 1; 0.4 0 0.2 1; 0.4 0 0.2 1; 0.4 0 0.2 1; 0.4 0 0.2 1; 0.4 0 0.2 1; 0.4 0 0.2 1; 0.4 0 0.2 1"
                            />
                            <animate
                                attributeName="fill"
                                values="#94a3b8; #94a3b8; #10b981; #10b981; #94a3b8"
                                keyTimes="0; 0.66; 0.70; 0.91; 1"
                                dur="12s"
                                repeatCount="indefinite"
                            />
                        </circle>
                    </g>
                )
            })}
        </svg>
    );
}
