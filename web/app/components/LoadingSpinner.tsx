'use client';

import React from 'react';

interface LoadingSpinnerProps {
  message?: string;
  color?: 'indigo' | 'green' | 'purple';
  size?: 'sm' | 'md';
  showDots?: boolean;
}

const colorClasses = {
  indigo: {
    spinner: 'border-indigo-600',
    text: 'text-indigo-700',
    dots: 'bg-indigo-300',
  },
  green: {
    spinner: 'border-green-600',
    text: 'text-green-700',
    dots: 'bg-green-300',
  },
  purple: {
    spinner: 'border-purple-600',
    text: 'text-purple-700',
    dots: 'bg-purple-300',
  },
};

const sizeClasses = {
  sm: 'w-4 h-4 border-2',
  md: 'w-5 h-5 border-2',
};

export default function LoadingSpinner({
  message,
  color = 'indigo',
  size = 'sm',
  showDots = false,
}: LoadingSpinnerProps) {
  const colors = colorClasses[color];
  const sizeClass = sizeClasses[size];

  return (
    <div className="space-y-2">
      <div className={`flex items-center gap-2 text-sm ${colors.text}`}>
        <span
          className={`${sizeClass} ${colors.spinner} border-t-transparent rounded-full animate-spin`}
        />
        {message && <span>{message}</span>}
      </div>
      {showDots && (
        <div className="flex gap-1">
          <div
            className={`h-2 w-2 ${colors.dots} rounded-full animate-bounce`}
            style={{ animationDelay: '0ms' }}
          />
          <div
            className={`h-2 w-2 ${colors.dots} rounded-full animate-bounce`}
            style={{ animationDelay: '150ms' }}
          />
          <div
            className={`h-2 w-2 ${colors.dots} rounded-full animate-bounce`}
            style={{ animationDelay: '300ms' }}
          />
        </div>
      )}
    </div>
  );
}
