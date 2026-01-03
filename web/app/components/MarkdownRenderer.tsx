'use client';

import React from 'react';
import ReactMarkdown from 'react-markdown';

interface MarkdownRendererProps {
  content: string;
  variant?: 'default' | 'green' | 'purple';
  showCursor?: boolean;
}

const variantClasses = {
  default: 'prose-strong:font-bold prose-headings:font-bold text-gray-800',
  green: 'prose-headings:font-bold prose-headings:text-green-900 prose-strong:text-green-900 text-gray-800',
  purple: 'prose-headings:font-bold prose-headings:text-purple-900 prose-strong:text-purple-900 text-gray-800',
};

export default function MarkdownRenderer({
  content,
  variant = 'default',
  showCursor = false,
}: MarkdownRendererProps) {
  return (
    <div className={`prose prose-sm max-w-none ${variantClasses[variant]}`}>
      <ReactMarkdown>{content}</ReactMarkdown>
      {showCursor && (
        <span className="inline-block w-2 h-4 ml-1 bg-current animate-pulse" />
      )}
    </div>
  );
}
