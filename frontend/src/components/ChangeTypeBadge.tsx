const COLORS: Record<string, string> = {
  reinforcing: "bg-green-100 text-green-800",
  friction: "bg-red-100 text-red-800",
  early_signal: "bg-blue-100 text-blue-800",
  neutral: "bg-gray-100 text-gray-600",
};

export default function ChangeTypeBadge({ changeType }: { changeType: string }) {
  const color = COLORS[changeType] ?? "bg-gray-100 text-gray-600";
  const label = changeType.replace(/_/g, " ");
  return (
    <span className={`inline-block text-xs font-medium px-2 py-0.5 rounded ${color}`}>
      {label}
    </span>
  );
}
