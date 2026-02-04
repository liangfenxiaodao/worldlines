const LABELS: Record<string, string> = {
  compute_and_computational_paradigms: "Compute",
  capital_flows_and_business_models: "Capital",
  energy_resources_and_physical_constraints: "Energy",
  technology_adoption_and_industrial_diffusion: "Tech Adoption",
  governance_regulation_and_societal_response: "Governance",
};

const COLORS: Record<string, string> = {
  compute_and_computational_paradigms: "bg-violet-100 text-violet-800",
  capital_flows_and_business_models: "bg-emerald-100 text-emerald-800",
  energy_resources_and_physical_constraints: "bg-orange-100 text-orange-800",
  technology_adoption_and_industrial_diffusion: "bg-sky-100 text-sky-800",
  governance_regulation_and_societal_response: "bg-rose-100 text-rose-800",
};

export function dimensionLabel(dim: string): string {
  return LABELS[dim] ?? dim;
}

export default function DimensionBadge({ dimension }: { dimension: string }) {
  const color = COLORS[dimension] ?? "bg-gray-100 text-gray-700";
  return (
    <span className={`inline-block text-xs font-medium px-2 py-0.5 rounded ${color}`}>
      {dimensionLabel(dimension)}
    </span>
  );
}
