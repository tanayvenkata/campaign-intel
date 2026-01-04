/**
 * Markdown Export Utility for Focus Group Search Results
 *
 * Generates a well-formatted markdown report that can be:
 * - Viewed directly in any markdown viewer
 * - Converted to PDF via Pandoc, VS Code, or online tools
 * - Edited before sharing
 */

import { GroupedResult } from '../types';

export interface ExportData {
    query: string;
    results: GroupedResult[];
    summaries: Record<string, string>;
    deepSyntheses?: Record<string, string>;  // Deep synthesis per focus group
    macroResult?: string;
    deepMacroThemes?: Array<{ name: string; synthesis: string; focus_groups: string[] }>;
    stats?: {
        total_quotes: number;
        focus_groups_count: number;
        retrieval_time_ms: number;
    };
}

/**
 * Clean quote content by removing metadata prefix if present
 */
function cleanQuoteContent(content: string): string {
    // Remove bracketed metadata prefix like "[Ohio Senate 2024 | Location | Participant...]"
    // Using [\s\S]* instead of .* with /s flag for ES5 compatibility
    const cleaned = content.replace(/^\[[\s\S]*?\]\s*(?:Q:[\s\S]*?\n)?/, '').trim();
    // Remove leading Q: lines
    return cleaned.replace(/^Q:.*\n?/m, '').trim();
}

/**
 * Generate markdown content from export data
 */
function generateMarkdown(data: ExportData): string {
    const { query, results, summaries, deepSyntheses, macroResult, deepMacroThemes, stats } = data;
    const lines: string[] = [];

    // Title
    lines.push('# Focus Group Research Report');
    lines.push('');
    lines.push(`**Query:** ${query}`);
    lines.push('');

    // Stats
    if (stats) {
        lines.push(`${stats.total_quotes} quotes from ${stats.focus_groups_count} focus groups • ${new Date().toLocaleDateString()}`);
        lines.push('');
    }

    // Executive Summary
    if (macroResult?.trim()) {
        lines.push('---');
        lines.push('');
        lines.push('## Summary');
        lines.push('');
        lines.push(macroResult.trim());
        lines.push('');
    }

    // Key Themes
    if (deepMacroThemes && deepMacroThemes.length > 0) {
        lines.push('---');
        lines.push('');
        lines.push('## Themes');
        lines.push('');

        deepMacroThemes.forEach((theme, idx) => {
            lines.push(`### ${idx + 1}. ${theme.name}`);
            lines.push('');
            lines.push(theme.synthesis.trim());
            lines.push('');
            lines.push(`*Sources: ${theme.focus_groups.join(', ')}*`);
            lines.push('');
        });
    }

    // Detailed Findings
    lines.push('---');
    lines.push('');
    lines.push('## Findings by Focus Group');
    lines.push('');

    results.forEach((group) => {
        const metadata = group.focus_group_metadata;
        const location = metadata.location || group.focus_group_id;
        const summary = summaries[group.focus_group_id];
        const deepSynthesis = deepSyntheses?.[group.focus_group_id];

        // Focus Group Header
        const outcome = metadata.outcome === 'win' ? '(Win)' : '(Loss)';
        lines.push(`### ${location} ${outcome}`);
        lines.push('');

        // Metadata line
        const metaParts = [metadata.date, metadata.race_name].filter(Boolean);
        if (metaParts.length > 0) {
            lines.push(`*${metaParts.join(' • ')}*`);
            lines.push('');
        }

        // Deep Synthesis (if available, takes priority)
        if (deepSynthesis) {
            lines.push('#### Deep Analysis');
            lines.push('');
            lines.push(deepSynthesis.trim());
            lines.push('');
        } else if (summary) {
            // Fall back to light summary
            lines.push(`**Synthesis:** ${summary}`);
            lines.push('');
        }

        // Quotes - compact format
        group.chunks.forEach((chunk) => {
            const profile = chunk.participant_profile ? ` (${chunk.participant_profile})` : '';
            let cleanContent = cleanQuoteContent(chunk.content);
            // Remove surrounding quotes if present to avoid double-quoting
            cleanContent = cleanContent.replace(/^[""]|[""]$/g, '').trim();
            lines.push(`> "${cleanContent}"  `);
            lines.push(`> — **${chunk.participant}**${profile}`);
            lines.push('');
        });

        lines.push('');
    });

    return lines.join('\n');
}

/**
 * Export data to markdown file
 */
export function exportToMarkdown(data: ExportData): void {
    try {
        console.log('Generating Markdown report...');

        const markdown = generateMarkdown(data);

        // Create blob and download
        const blob = new Blob([markdown], { type: 'text/markdown;charset=utf-8' });
        const filename = `Report_${data.query.slice(0, 30).replace(/[^a-z0-9]/gi, '_')}.md`;

        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);

        console.log('Markdown export complete!');
    } catch (error) {
        console.error('Markdown export failed:', error);
        throw error;
    }
}
