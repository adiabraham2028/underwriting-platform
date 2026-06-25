export default function ClassificationBadge({ confidence, matchType }) {
  if (matchType === 'exact_known') {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
        Known Match
      </span>
    )
  }

  if (confidence >= 0.9) {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
        High {Math.round(confidence * 100)}%
      </span>
    )
  }

  if (confidence >= 0.7) {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
        Medium {Math.round(confidence * 100)}%
      </span>
    )
  }

  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
      Low {Math.round(confidence * 100)}%
    </span>
  )
}
