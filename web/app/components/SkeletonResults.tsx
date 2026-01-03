'use client';

interface SkeletonResultsProps {
  count?: number;
}

function SkeletonCard({ delay }: { delay: number }) {
  return (
    <div
      className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 animate-pulse"
      style={{ animationDelay: `${delay}ms` }}
    >
      {/* Header */}
      <div className="flex items-center gap-3 mb-4">
        <div className="w-4 h-4 bg-gray-200 rounded" />
        <div className="h-6 bg-gray-200 rounded w-48" />
        <div className="h-4 bg-gray-100 rounded w-20" />
      </div>
      <div className="h-4 bg-gray-100 rounded w-64 mb-6" />

      {/* Summary placeholder */}
      <div className="bg-yellow-50 border-l-4 border-yellow-200 p-3 mb-4">
        <div className="h-4 bg-yellow-100 rounded w-full mb-2" />
        <div className="h-4 bg-yellow-100 rounded w-3/4" />
      </div>

      {/* Quote placeholders */}
      <div className="space-y-3">
        {[0, 1, 2].map((i) => (
          <div key={i} className="border-l-4 border-gray-200 pl-4 py-2">
            <div className="h-4 bg-gray-100 rounded w-full mb-2" />
            <div className="h-4 bg-gray-100 rounded w-5/6 mb-2" />
            <div className="h-3 bg-gray-50 rounded w-32" />
          </div>
        ))}
      </div>
    </div>
  );
}

export default function SkeletonResults({ count = 3 }: SkeletonResultsProps) {
  return (
    <div className="space-y-6">
      {/* Skeleton for macro synthesis bar */}
      <div className="bg-white p-4 rounded-lg border border-gray-200 shadow-sm animate-pulse">
        <div className="flex items-center justify-between">
          <div className="h-5 bg-gray-200 rounded w-48" />
          <div className="h-9 bg-gray-200 rounded w-36" />
        </div>
      </div>

      {/* Skeleton cards */}
      {Array.from({ length: count }).map((_, i) => (
        <SkeletonCard key={i} delay={i * 100} />
      ))}
    </div>
  );
}
