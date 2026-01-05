'use client';

import React from 'react';

// Shared Props
interface VisualProps {
    className?: string;
}

// 1. THE DISTILLATION: Thousands of points (Raw Quotes) narrowing into a single bright beam (Insight)
export function VisualDistillation({ className = "" }: VisualProps) {
    const width = 400;
    const height = 240;

    // Generate raw noise points on the left
    const noisePoints = Array.from({ length: 40 }).map((_, i) => ({
        x: 20 + Math.random() * 100,
        y: 20 + Math.random() * 200,
        delay: Math.random() * 2
    }));

    return (
        <svg viewBox={`0 0 ${width} ${height}`} className={`w-full h-full ${className}`}>
            <defs>
                <linearGradient id="distillBeam" x1="0" y1="0" x2="1" y2="0">
                    <stop offset="0.2" stopColor="#64748b" stopOpacity="0" />
                    <stop offset="0.8" stopColor="#10b981" stopOpacity="0.8" />
                </linearGradient>
            </defs>

            {/* Funnel Shapes */}
            <path d="M 0 0 L 150 100 L 150 140 L 0 240" fill="none" stroke="#64748b" strokeWidth="0.5" opacity="0.1" />

            {/* Raw Noise Particles (Left) */}
            {noisePoints.map((pt, i) => (
                <circle key={i} cx={pt.x} cy={pt.y} r="1" fill="#94a3b8" opacity="0.4">
                    <animate attributeName="opacity" values="0.2;0.6;0.2" dur={`${1 + pt.delay}s`} repeatCount="indefinite" />
                    {/* Move towards center */}
                    <animate attributeName="cx" values={`${pt.x}; 160`} dur="3s" begin={`${pt.delay}s`} repeatCount="indefinite" />
                    <animate attributeName="cy" values={`${pt.y}; 120`} dur="3s" begin={`${pt.delay}s`} repeatCount="indefinite" />
                </circle>
            ))}

            {/* The Insight Beam (Right) */}
            <line x1="160" y1="120" x2="380" y2="120" stroke="url(#distillBeam)" strokeWidth="2">
                <animate attributeName="stroke-width" values="1;3;1" dur="4s" repeatCount="indefinite" />
            </line>

            {/* Output Particles */}
            <circle cx="160" cy="120" r="2" fill="#10b981">
                <animate attributeName="cx" values="160;380" dur="1.5s" repeatCount="indefinite" />
                <animate attributeName="opacity" values="1;0" dur="1.5s" repeatCount="indefinite" />
            </circle>
        </svg>
    );
}

// 2. THE CONSENSUS: Distinct nodes (Voters) pulsing, triggering a central node (Theme)
export function VisualConsensus({ className = "" }: VisualProps) {
    const width = 400;
    const height = 240;
    const cx = 200;
    const cy = 120;

    // Voter positions roughly circular
    const voters = [0, 60, 120, 180, 240, 300].map(deg => {
        const rad = deg * (Math.PI / 180);
        return {
            x: cx + Math.cos(rad) * 80,
            y: cy + Math.sin(rad) * 80
        };
    });

    return (
        <svg viewBox={`0 0 ${width} ${height}`} className={`w-full h-full ${className}`}>
            {/* Connections */}
            {voters.map((v, i) => (
                <line key={`l-${i}`} x1={v.x} y1={v.y} x2={cx} y2={cy} stroke="#10b981" strokeWidth="0.5" opacity="0.2">
                    <animate attributeName="opacity" values="0.1;0.5;0.1" dur="3s" begin={`${i * 0.5}s`} repeatCount="indefinite" />
                </line>
            ))}

            {/* Voters */}
            {voters.map((v, i) => (
                <circle key={`v-${i}`} cx={v.x} cy={v.y} r="3" fill="#64748b">
                    <animate attributeName="fill" values="#64748b;#10b981;#64748b" dur="3s" begin={`${i * 0.5}s`} repeatCount="indefinite" />
                    <animate attributeName="r" values="3;4;3" dur="3s" begin={`${i * 0.5}s`} repeatCount="indefinite" />
                </circle>
            ))}

            {/* Central Consensus */}
            <circle cx={cx} cy={cy} r="10" fill="#1e293b" stroke="#10b981" strokeWidth="1">
                <animate attributeName="r" values="10;14;10" dur="3s" repeatCount="indefinite" />
                <animate attributeName="stroke-width" values="1;3;1" dur="3s" repeatCount="indefinite" />
            </circle>
            <text x={cx} y={cy + 40} textAnchor="middle" className="text-[10px] font-mono fill-emerald-600 uppercase tracking-widest opacity-80">Shared Sentiment</text>
        </svg>
    );
}

// 3. THE TRANSCRIPT: Scanning text blocks extracting 'signals'
export function VisualTranscript({ className = "" }: VisualProps) {
    const width = 400;
    const height = 240;

    const lines = Array.from({ length: 8 }).map((_, i) => ({
        y: 40 + i * 20,
        width: 150 + Math.random() * 100
    }));

    return (
        <svg viewBox={`0 0 ${width} ${height}`} className={`w-full h-full ${className}`}>
            {/* Text Block Lines */}
            {lines.map((l, i) => (
                <rect key={i} x="50" y={l.y} width={l.width} height="4" fill="#cbd5e1" rx="2">
                    {/* Scan effect */}
                    {i === 2 || i === 5 ? (
                        <animate attributeName="fill" values="#cbd5e1;#10b981;#cbd5e1" dur="4s" begin={`${i}s`} repeatCount="indefinite" />
                    ) : null}
                </rect>
            ))}

            {/* Extracted Signal flying out */}
            <circle cx="200" cy="80" r="3" fill="#10b981" opacity="0">
                <animate attributeName="opacity" values="0;1;0" dur="4s" begin="2s" repeatCount="indefinite" />
                <animate attributeName="cx" values="200;350" dur="4s" begin="2s" repeatCount="indefinite" />
            </circle>
            <circle cx="200" cy="140" r="3" fill="#10b981" opacity="0">
                <animate attributeName="opacity" values="0;1;0" dur="4s" begin="5s" repeatCount="indefinite" />
                <animate attributeName="cx" values="200;350" dur="4s" begin="5s" repeatCount="indefinite" />
            </circle>

            {/* Sidebar collecting signals */}
            <rect x="340" y="40" width="2" height="160" fill="#cbd5e1" />
            <circle cx="341" cy="40" r="2" fill="#64748b" />
            <circle cx="341" cy="200" r="2" fill="#64748b" />
        </svg>
    );
}

// 4. THE ALIGNMENT: Chaos -> Query -> Consensus
export function VisualAlignment({ className = "" }: VisualProps) {
    const width = 400;
    const height = 240;

    // Grid of 'compasses'
    const compasses = [];
    const rows = 4;
    const cols = 6;
    for (let x = 0; x < cols; x++) {
        for (let y = 0; y < rows; y++) {
            // Generate a stable random starting angle for one compass
            const randomAngle = (x * y * 45 + x * 30 + y * 50) % 360;
            compasses.push({
                x: 60 + x * 56,
                y: 40 + y * 50,
                id: `${x}-${y}`,
                startAngle: randomAngle
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
            <circle cx="200" cy="120" r="0" fill="url(#queryPulse)">
                <animate attributeName="r" values="0; 250" dur="6s" begin="0s" repeatCount="indefinite" />
                <animate attributeName="opacity" values="0; 1; 0" keyTimes="0; 0.3; 1" dur="6s" begin="0s" repeatCount="indefinite" />
            </circle>

            {/* The Compass Grid */}
            {compasses.map((c, i) => (
                <g key={i} transform={`translate(${c.x}, ${c.y})`}>
                    {/* Compass Housing */}
                    <circle r="2" fill="#e2e8f0" />

                    {/* The Needle */}
                    <g>
                        <line x1="-12" y1="0" x2="12" y2="0" strokeWidth="1.5" strokeLinecap="round">
                            {/* 
                                Animation Sequence (6s cycle):
                                0s-2s: Chaos (Hold random angle)
                                2s-5s: Alignment (Rotate to 45deg)
                                5s-6s: Return to Chaos
                             */}
                            <animateTransform
                                attributeName="transform"
                                type="rotate"
                                values={`${c.startAngle}; ${c.startAngle}; 45; 45; ${c.startAngle}`}
                                keyTimes="0; 0.3; 0.4; 0.8; 1"
                                dur="6s"
                                repeatCount="indefinite"
                                calcMode="spline"
                                keySplines="0.4 0 0.2 1; 0.4 0 0.2 1; 0.4 0 0.2 1; 0.4 0 0.2 1"
                            />
                            <animate
                                attributeName="stroke"
                                values="#94a3b8; #94a3b8; #10b981; #10b981; #94a3b8"
                                keyTimes="0; 0.3; 0.4; 0.8; 1"
                                dur="6s"
                                repeatCount="indefinite"
                            />
                        </line>
                        {/* Tip indicator */}
                        <circle cx="12" cy="0" r="1.5">
                            <animateTransform
                                attributeName="transform"
                                type="rotate"
                                values={`${c.startAngle}; ${c.startAngle}; 45; 45; ${c.startAngle}`}
                                keyTimes="0; 0.3; 0.4; 0.8; 1"
                                dur="6s"
                                repeatCount="indefinite"
                                calcMode="spline"
                                keySplines="0.4 0 0.2 1; 0.4 0 0.2 1; 0.4 0 0.2 1; 0.4 0 0.2 1"
                            />
                            <animate
                                attributeName="fill"
                                values="#94a3b8; #94a3b8; #10b981; #10b981; #94a3b8"
                                keyTimes="0; 0.3; 0.4; 0.8; 1"
                                dur="6s"
                                repeatCount="indefinite"
                            />
                        </circle>
                    </g>
                </g>
            ))}

            {/* Status Label */}
            <text x="200" y="230" textAnchor="middle" className="text-[10px] font-mono uppercase tracking-widest transition-colors duration-500" fill="#64748b">
                <animate
                    attributeName="fill"
                    values="#64748b; #64748b; #059669; #059669; #64748b"
                    keyTimes="0; 0.3; 0.4; 0.8; 1"
                    dur="6s"
                    repeatCount="indefinite"
                />
                Signal Detected
            </text>
        </svg>
    );
}

// 5. THE LOOM: Different threads weaving together
export function VisualLoom({ className = "" }: VisualProps) {
    const width = 400;
    const height = 240;

    return (
        <svg viewBox={`0 0 ${width} ${height}`} className={`w-full h-full ${className}`}>
            {/* Vertical Threads (Inputs) */}
            {[80, 100, 120].map((y, i) => (
                <path
                    key={`in-${i}`}
                    d={`M 0 ${y} C 100 ${y}, 150 ${y}, 200 120`}
                    stroke="#cbd5e1"
                    fill="none"
                    strokeWidth="1"
                />
            ))}
            {[160, 180, 200].map((y, i) => (
                <path
                    key={`in-b-${i}`}
                    d={`M 0 ${y} C 100 ${y}, 150 ${y}, 200 120`}
                    stroke="#cbd5e1"
                    fill="none"
                    strokeWidth="1"
                />
            ))}

            {/* Weaving Point */}
            <circle cx="200" cy="120" r="4" fill="#1e293b" stroke="#10b981" />

            {/* Output Thread (Stronger) */}
            <path d="M 200 120 C 250 120, 300 120, 400 120" stroke="#10b981" strokeWidth="2" fill="none" strokeDasharray="4 4">
                <animate attributeName="stroke-dashoffset" values="8;0" dur="1s" repeatCount="indefinite" />
            </path>
        </svg>
    );
}
