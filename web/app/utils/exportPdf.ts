/**
 * PDF Export Utility for Focus Group Search Results
 *
 * Implements a "Political Consultant" style report:
 * - Professional Cover Page
 * - "Executive Summary" style Macro Synthesis
 * - Clean, non-italicized quotes with clear attribution
 * - Proper headers/footers and pagination
 */

import jsPDF from 'jspdf';
import { GroupedResult } from '../types';

// ============================================================================
// Configuration - Centralized styling constants
// ============================================================================

const PDF_CONFIG = {
    colors: {
        primary: [79, 70, 229] as const,      // Indigo 600 - brand color
        gray900: [17, 24, 39] as const,
        gray800: [31, 41, 55] as const,
        gray700: [55, 65, 81] as const,
        gray600: [75, 85, 99] as const,
        gray500: [107, 114, 128] as const,
        gray400: [156, 163, 175] as const,
        gray300: [209, 213, 219] as const,
        gray200: [229, 231, 235] as const,
        gray100: [243, 244, 246] as const,
        gray50: [249, 250, 251] as const,
        success: [22, 163, 74] as const,      // Green 600
        error: [220, 38, 38] as const,        // Red 600
        black: [0, 0, 0] as const,
    },
    typography: {
        title: 36,
        subtitle: 24,
        sectionTitle: 18,
        subsection: 16,
        heading: 14,
        large: 13,
        body: 11,
        small: 10,
        caption: 9,
        tiny: 8,
    },
    layout: {
        margin: 20,
        headerSpacing: 10,
        lineHeightFactor: 1.15,
        accentBarWidth: 8,
    },
} as const;

// ============================================================================
// Types
// ============================================================================

export interface ExportData {
    query: string;
    results: GroupedResult[];
    summaries: Record<string, string>;
    macroResult?: string;
    deepMacroThemes?: Array<{ name: string; synthesis: string; focus_groups: string[] }>;
    stats?: {
        total_quotes: number;
        focus_groups_count: number;
        retrieval_time_ms: number;
    };
}

interface PdfContext {
    y: number;
    margin: number;
    contentWidth: number;
    pageHeight: number;
    pageWidth: number;
    currentPage: number;
}

// ============================================================================
// Core Layout Utilities
// ============================================================================

function createContext(doc: jsPDF): PdfContext {
    const pageWidth = doc.internal.pageSize.getWidth();
    const pageHeight = doc.internal.pageSize.getHeight();
    const margin = 20; // Standard 20mm margin (~0.8 inches)
    return {
        y: margin,
        margin,
        contentWidth: pageWidth - margin * 2,
        pageHeight,
        pageWidth,
        currentPage: 1,
    };
}

/**
 * Checks if content fits on current page. If not, adds new page and resets Y.
 */
function checkPageBreak(doc: jsPDF, ctx: PdfContext, requiredSpace: number): void {
    if (ctx.y + requiredSpace > ctx.pageHeight - ctx.margin) {
        doc.addPage();
        ctx.currentPage++;
        ctx.y = ctx.margin + 10; // Extra space for header on new pages
        renderPageHeader(doc, ctx);
        renderPageFooter(doc, ctx);
    }
}

/**
 * Adds text with automatic wrapping.
 */
function addWrappedText(
    doc: jsPDF,
    ctx: PdfContext,
    text: string,
    fontSize: number,
    options: {
        bold?: boolean;
        color?: [number, number, number];
        italic?: boolean;
        indent?: number;
        align?: 'left' | 'center' | 'right';
        lineHeightFactor?: number;
    } = {}
): void {
    const {
        bold = false,
        color = [0, 0, 0], // Default black
        italic = false,
        indent = 0,
        align = 'left',
        lineHeightFactor = 1.15
    } = options;

    doc.setFontSize(fontSize);
    doc.setFont('helvetica', bold ? 'bold' : italic ? 'italic' : 'normal');
    doc.setTextColor(...color);

    const maxWidth = ctx.contentWidth - indent;
    const lines = doc.splitTextToSize(text, maxWidth);
    const lineHeight = fontSize * 0.3527 * lineHeightFactor; // Convert pt to mm approx

    // Pre-calculate height to check for page break once for the whole block if possible,
    // or line-by-line for long blocks.
    // For very long blocks, we do line-by-line.
    for (const line of lines) {
        checkPageBreak(doc, ctx, lineHeight);

        let xPos = ctx.margin + indent;
        if (align === 'center') {
            xPos = (ctx.pageWidth - doc.getTextWidth(line)) / 2;
        } else if (align === 'right') {
            xPos = ctx.pageWidth - ctx.margin - doc.getTextWidth(line);
        }

        doc.text(line, xPos, ctx.y);
        ctx.y += lineHeight;
    }
}

function stripMarkdown(text: string): string {
    return text
        .replace(/#{1,6}\s/g, '') // Headers
        .replace(/\*\*([^*]+)\*\*/g, '$1') // Bold
        .replace(/\*([^*]+)\*/g, '$1') // Italic
        .replace(/`([^`]+)`/g, '$1') // Code
        .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1') // Links
        .replace(/^[-*+]\s/gm, '• ') // List items
        .trim();
}

// ============================================================================
// Section Renderers
// ============================================================================

/**
 * Renders the Cover Page (Page 1)
 */
function renderCoverPage(doc: jsPDF, ctx: PdfContext, data: ExportData): void {
    // Background accent (optional subtle bar on left)
    doc.setFillColor(79, 70, 229); // Indigo brand color
    doc.rect(0, 0, 8, ctx.pageHeight, 'F');

    let currentY = ctx.pageHeight / 3;

    // Report Title
    doc.setFontSize(36);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(17, 24, 39); // Gray 900
    doc.text('Research Report', ctx.margin + 10, currentY);
    currentY += 15;

    doc.setFontSize(24);
    doc.setFont('helvetica', 'normal');
    doc.setTextColor(75, 85, 99); // Gray 600
    doc.text('Focus Group Synthesis', ctx.margin + 10, currentY);
    currentY += 30;

    // Query Details
    doc.setFontSize(14);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(55, 65, 81); // Gray 700
    doc.text('Research Query:', ctx.margin + 10, currentY);
    currentY += 8;

    doc.setFontSize(16);
    doc.setFont('helvetica', 'normal');
    doc.setTextColor(17, 24, 39);
    const queryLines = doc.splitTextToSize(data.query, ctx.contentWidth - 20);
    doc.text(queryLines, ctx.margin + 10, currentY);
    currentY += (queryLines.length * 8) + 20;

    // Stats Grid
    if (data.stats) {
        const statsY = currentY;

        doc.setDrawColor(229, 231, 235); // Gray 200
        doc.line(ctx.margin + 10, statsY, ctx.pageWidth - ctx.margin, statsY);
        currentY += 10;

        doc.setFontSize(12);
        doc.setTextColor(107, 114, 128); // Gray 500

        doc.text('Total Quotes', ctx.margin + 10, currentY);
        doc.text('Focus Groups', ctx.margin + 70, currentY);
        doc.text('Date Generated', ctx.margin + 130, currentY);

        currentY += 6;

        doc.setFontSize(14);
        doc.setTextColor(17, 24, 39); // Gray 900
        doc.setFont('helvetica', 'bold');

        doc.text(data.stats.total_quotes.toString(), ctx.margin + 10, currentY);
        doc.text(data.stats.focus_groups_count.toString(), ctx.margin + 70, currentY);
        doc.text(new Date().toLocaleDateString(), ctx.margin + 130, currentY);
    }
}

/**
 * Renders standard header on subsequent pages
 */
function renderPageHeader(doc: jsPDF, ctx: PdfContext): void {
    if (ctx.currentPage === 1) return; // No header on cover

    doc.setFontSize(8);
    doc.setFont('helvetica', 'normal');
    doc.setTextColor(156, 163, 175); // Gray 400
    doc.text(`Research Report`, ctx.margin, 10);
    doc.text(new Date().toLocaleDateString(), ctx.pageWidth - ctx.margin - 20, 10);
}

/**
 * Renders footer with page numbers
 */
function renderPageFooter(doc: jsPDF, ctx: PdfContext): void {
    if (ctx.currentPage === 1) return;

    doc.setFontSize(9);
    doc.setTextColor(156, 163, 175);
    const pageString = `Page ${ctx.currentPage}`;
    const textWidth = doc.getTextWidth(pageString);
    doc.text(pageString, (ctx.pageWidth - textWidth) / 2, ctx.pageHeight - 10);
}

/**
 * Renders Executive Summary (Macro Synthesis)
 */
function renderExecutiveSummary(doc: jsPDF, ctx: PdfContext, macroResult: string): void {
    if (!macroResult?.trim()) return;

    doc.addPage();
    ctx.currentPage++;
    ctx.y = ctx.margin;
    renderPageHeader(doc, ctx);
    renderPageFooter(doc, ctx);

    // Section Title
    doc.setFontSize(18);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(17, 24, 39);
    doc.text("Executive Summary", ctx.margin, ctx.y);
    ctx.y += 10;

    // Content Box
    doc.setFillColor(249, 250, 251); // Gray 50
    doc.setDrawColor(229, 231, 235); // Gray 200

    // Estimate height
    const cleanText = stripMarkdown(macroResult);
    const lines = doc.splitTextToSize(cleanText, ctx.contentWidth - 10);
    const textHeight = lines.length * 5; // approx 5mm per line

    // We can't draw a single rectangle if it spans pages, so we just render text on background.
    // For now, let's keep it simple with text.

    addWrappedText(doc, ctx, cleanText, 11, {
        color: [31, 41, 55], // Gray 800
        lineHeightFactor: 1.5 // Relaxed reading
    });

    ctx.y += 15;
}

/**
 * Renders Deep Macro Themes
 */
function renderDeepMacroThemes(
    doc: jsPDF,
    ctx: PdfContext,
    themes: Array<{ name: string; synthesis: string; focus_groups: string[] }>
): void {
    if (!themes?.length) return;

    checkPageBreak(doc, ctx, 30);

    doc.setFontSize(16);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(17, 24, 39);
    doc.text("Key Themes", ctx.margin, ctx.y);
    ctx.y += 10;

    themes.forEach((theme, idx) => {
        checkPageBreak(doc, ctx, 40);

        // Theme Header
        addWrappedText(doc, ctx, `${idx + 1}. ${theme.name}`, 13, {
            bold: true,
            color: [79, 70, 229] // Indigo 600
        });
        ctx.y += 4;

        // Theme Content
        addWrappedText(doc, ctx, stripMarkdown(theme.synthesis), 11, {
            color: [55, 65, 81],
            lineHeightFactor: 1.4
        });
        ctx.y += 4;

        // Participating Groups
        const groupsText = `Evidence from: ${theme.focus_groups.join(', ')}`;
        addWrappedText(doc, ctx, groupsText, 9, {
            color: [107, 114, 128], // Gray 500
            italic: true
        });

        ctx.y += 10;
    });
}

/**
 * Renders a single focus group section
 */
function renderFocusGroup(
    doc: jsPDF,
    ctx: PdfContext,
    group: GroupedResult,
    summary: string | undefined
): void {
    // Always start a new page for a new Focus Group implies a significant section break
    // User might prefer continuous if they are small, but clarity is key.
    // Let's check space. If less than half page remains, break.
    if (ctx.y > ctx.pageHeight / 2) {
        doc.addPage();
        ctx.currentPage++;
        ctx.y = ctx.margin + 10;
        renderPageHeader(doc, ctx);
        renderPageFooter(doc, ctx);
    } else {
        ctx.y += 10; // Spacing from previous section
    }

    const metadata = group.focus_group_metadata;
    const location = metadata.location || group.focus_group_id;

    // --- Header Row ---
    doc.setFillColor(243, 244, 246); // Gray 100
    doc.rect(ctx.margin, ctx.y, ctx.contentWidth, 12, 'F');

    // Location
    doc.setFontSize(12);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(17, 24, 39);
    doc.text(location, ctx.margin + 4, ctx.y + 8);

    // Outcome Badge (Text)
    if (metadata.outcome) {
        const isWin = metadata.outcome === 'win';
        doc.setTextColor(isWin ? 22 : 220, isWin ? 163 : 38, isWin ? 74 : 38); // Green-600 or Red-600
        doc.text(metadata.outcome.toUpperCase(), ctx.pageWidth - ctx.margin - 4, ctx.y + 8, { align: 'right' });
    }

    ctx.y += 18;

    // --- Metadata Information ---
    doc.setFontSize(10);
    doc.setFont('helvetica', 'normal');
    doc.setTextColor(75, 85, 99);

    const metaParts = [];
    if (metadata.date) metaParts.push(metadata.date);
    if (metadata.vehicle) metaParts.push(metadata.vehicle);
    if (metadata.race_name) metaParts.push(metadata.race_name);

    if (metaParts.length > 0) {
        doc.text(metaParts.join('  •  '), ctx.margin, ctx.y);
        ctx.y += 8;
    }

    // --- Group Summary ---
    if (summary) {
        checkPageBreak(doc, ctx, 20);
        addWrappedText(doc, ctx, "Group Synthesis:", 10, { bold: true, color: [55, 65, 81] });
        ctx.y += 4;
        addWrappedText(doc, ctx, stripMarkdown(summary), 10, {
            color: [75, 85, 99],
            italic: true
        });
        ctx.y += 10;
    }

    // --- Quotes Section ---
    group.chunks.forEach(chunk => {
        checkPageBreak(doc, ctx, 30);

        // Attribution Line
        const participantInfo = `${chunk.participant}${chunk.participant_profile ? ` (${chunk.participant_profile})` : ''}`;

        doc.setFontSize(9);
        doc.setFont('helvetica', 'bold');
        doc.setTextColor(17, 24, 39); // Gray 900
        doc.text(participantInfo, ctx.margin, ctx.y);
        ctx.y += 4;

        // Quote Body
        // Visual indicator: gray vertical line
        const quoteStart = ctx.y;
        addWrappedText(doc, ctx, chunk.content, 10, {
            color: [0, 0, 0],
            indent: 4, // Indent text slightly
            lineHeightFactor: 1.3
        });
        const quoteEnd = ctx.y;

        // Draw line
        doc.setDrawColor(209, 213, 219); // Gray 300
        doc.setLineWidth(0.5);
        doc.line(ctx.margin, quoteStart, ctx.margin, quoteEnd - 2);

        ctx.y += 6; // Spacing between quotes
    });

    ctx.y += 5; // Spacing after group
}


// ============================================================================
// Main Export Function
// ============================================================================

export function exportToPdf(data: ExportData): void {
    try {
        console.log('Starting PDF Export...', data);
        const doc = new jsPDF();
        console.log('jsPDF instance created');
        const ctx = createContext(doc);

        // 1. Cover Page
        console.log('Rendering Cover Page...');
        renderCoverPage(doc, ctx, data);

        // 2. Executive Summary
        if (data.macroResult) {
            console.log('Rendering Executive Summary...');
            renderExecutiveSummary(doc, ctx, data.macroResult);
        }

        // 3. Deep Themes (if any)
        if (data.deepMacroThemes && data.deepMacroThemes.length > 0) {
            console.log('Rendering Deep Macro Themes...');
            // If we are already on a new page from Executive Summary, continue.
            // Otherwise start new page.
            if (ctx.y > ctx.pageHeight / 3) {
                doc.addPage();
                ctx.currentPage++;
                ctx.y = ctx.margin + 10;
                renderPageHeader(doc, ctx);
                renderPageFooter(doc, ctx);
            } else {
                ctx.y += 10;
            }
            renderDeepMacroThemes(doc, ctx, data.deepMacroThemes);
        }

        // 4. Focus Groups
        console.log('Rendering Focus Groups...');
        // Start fresh page for detailed findings
        doc.addPage();
        ctx.currentPage++;
        ctx.y = ctx.margin + 10;
        renderPageHeader(doc, ctx);
        renderPageFooter(doc, ctx);

        addWrappedText(doc, ctx, "Detailed Findings", 16, { bold: true });
        ctx.y += 10;

        data.results.forEach((group) => {
            console.log(`Rendering group: ${group.focus_group_id}`);
            renderFocusGroup(
                doc,
                ctx,
                group,
                data.summaries[group.focus_group_id]
            );
        });

        console.log('Saving PDF...');
        // Save
        const filename = `Report_${data.query.slice(0, 20).replace(/[^a-z0-9]/gi, '_')}.pdf`;

        // Manual Blob Download to force filename
        const pdfBlob = doc.output('blob');
        const url = URL.createObjectURL(pdfBlob);
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);

        console.log('PDF Saved!');
    } catch (error) {
        console.error('PDF Generation Failed:', error);
        alert(`PDF Generation Failed: ${error instanceof Error ? error.message : String(error)}`);
    }
}

