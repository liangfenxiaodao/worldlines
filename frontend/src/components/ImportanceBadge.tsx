const COLORS: Record<string, string> = {
  high: "bg-red-100 text-red-800",
  medium: "bg-amber-100 text-amber-800",
  low: "bg-gray-100 text-gray-600",
};

export default function ImportanceBadge({ importance }: { importance: string }) {
  const color = COLORS[importance] ?? "bg-gray-100 text-gray-600";
  return (
    <span className={`inline-block text-xs font-medium px-2 py-0.5 rounded ${color}`}>
      {importance}
    </span>
  );
}
