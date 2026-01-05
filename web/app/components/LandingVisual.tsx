'use client';

import React, { useEffect, useState } from 'react';

export default function LandingVisual() {
    const [mounted, setMounted] = useState(false);

    useEffect(() => {
        setMounted(true);
    }, []);

    if (!mounted) return null;

    // Configuration
    const gridCols = 4;
    const gridRows = 6;
    const width = 600;
    const height = 400;

    // Core (Insight) Node Position (Left)
    const coreX = 60;
    const coreY = height / 2;

    // Grid (Data) Nodes Position (Right)
    const gridStartX = 400;
    const gridStartY = 80;
    const gridGapX = 30;
    const gridGapY = 40;

    // Generate grid points
    const points = [];
    for (let i = 0; i < gridCols; i++) {
        for (let j = 0; j < gridRows; j++) {
            points.push({
                x: gridStartX + i * gridGapX,
                y: gridStartY + j * gridGapY,
                id: `p-${i}-${j}`,
                delay: (i + j) * 0.1 // Staggered delay for potential effects
            });
        }
    }

    // Select a subset of points to connect to (for cleaner visuals)
    const connectedPoints = points.filter((_, i) => i % 3 === 0 || i % 7 === 0).slice(0, 8);

    return (
        <div className="w-full h-full min-h-[400px] flex items-center justify-center select-none pointer-events-none opacity-80">
            <svg
                viewBox={`0 0 ${width} ${height}`}
                className="w-full h-full max-w-[800px]"
                style={{ overflow: 'visible' }}
            >
                <defs>
                    <linearGradient id="lineGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" stopColor="#10b981" stopOpacity="0.01" /> {/* Emerald-500 equivalent */}
                        <stop offset="50%" stopColor="#10b981" stopOpacity="0.2" />
                        <stop offset="100%" stopColor="#64748b" stopOpacity="0.1" /> {/* Slate-500 */}
                    </linearGradient>

                    {/* Glow Filter for the Core */}
                    <filter id="glow">
                        <feGaussianBlur stdDeviation="2.5" result="coloredBlur" />
                        <feMerge>
                            <feMergeNode in="coloredBlur" />
                            <feMergeNode in="SourceGraphic" />
                        </feMerge>
                    </filter>
                </defs>

                {/* Connection Lines (Bezier Curves) */}
                {connectedPoints.map((pt, i) => {
                    const controlX1 = coreX + (pt.x - coreX) * 0.5;
                    const controlY1 = coreY;
                    const controlX2 = pt.x - (pt.x - coreX) * 0.2;
                    const controlY2 = pt.y;

                    const d = `M ${coreX} ${coreY} C ${controlX1} ${controlY1}, ${controlX2} ${controlY2}, ${pt.x} ${pt.y}`;

                    return (
                        <g key={`con-${i}`}>
                            {/* Base Line */}
                            <path
                                d={d}
                                stroke="url(#lineGradient)"
                                strokeWidth="1"
                                fill="none"
                            />
                            {/* Animated Pulse Packet */}
                            <circle r="1.5" fill="#10b981">
                                <animateMotion
                                    dur={`${3 + i * 0.5}s`}
                                    repeatCount="indefinite"
                                    path={d}
                                    keyPoints="1;0"
                                    keyTimes="0;1"
                                    calcMode="linear"
                                />
                                <animate
                                    attributeName="opacity"
                                    values="0;0.8;0"
                                    dur={`${3 + i * 0.5}s`}
                                    repeatCount="indefinite"
                                />
                            </circle>
                        </g>
                    );
                })}

                {/* Insight Core (Left Node) */}
                <circle cx={coreX} cy={coreY} r="4" fill="#1e293b" /> {/* Slate-800 */}
                <circle cx={coreX} cy={coreY} r="8" stroke="#10b981" strokeWidth="1" fill="none" opacity="0.3" filter="url(#glow)">
                    <animate attributeName="r" values="6;8;6" dur="3s" repeatCount="indefinite" />
                    <animate attributeName="opacity" values="0.2;0.5;0.2" dur="3s" repeatCount="indefinite" />
                </circle>

                {/* Data Grid (Right Nodes) */}
                {points.map((pt) => (
                    <circle
                        key={pt.id}
                        cx={pt.x}
                        cy={pt.y}
                        r="1.5"
                        fill="#94a3b8"
                        opacity="0.4"
                    />
                ))}

                {/* Highlighted/Active Grid Points */}
                {connectedPoints.map((pt, i) => (
                    <circle
                        key={`active-${i}`}
                        cx={pt.x}
                        cy={pt.y}
                        r="2.5"
                        fill="#64748b"
                    >
                        <animate
                            attributeName="opacity"
                            values="0.4;1;0.4"
                            dur={`${2 + i}s`}
                            repeatCount="indefinite"
                        />
                    </circle>
                ))}

                {/* Label text */}
                <text x={gridStartX + (gridCols * gridGapX) / 2 - 20} y={gridStartY + (gridRows * gridGapY) + 30} className="text-[9px] font-mono fill-slate-400 uppercase tracking-widest opacity-50">
                    Proprietary Corpus
                </text>
                <text x={coreX - 20} y={coreY + 30} className="text-[9px] font-mono fill-slate-800 uppercase tracking-widest opacity-80 text-right">
                    Synthesis
                </text>

            </svg>
        </div>
    );
}
