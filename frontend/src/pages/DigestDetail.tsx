import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { fetchDigest } from "../api/client";
import type { DigestDetail as DigestDetailType } from "../types/api";
import { dimensionLabel } from "../components/DimensionBadge";

export default function DigestDetail() {
  const { date } = useParams<{ date: string }>();
  const [data, setData] = useState<DigestDetailType | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!date) return;
    fetchDigest(date)
      .then(setData)
      .catch((e: unknown) => {
        setError(e instanceof Error ? e.message : "Failed to load digest");
      });
  }, [date]);

  if (error) return <p className="text-red-600">{error}</p>;
  if (!data) return <p className="text-gray-500">Loading...</p>;

  return (
    <div>
      <Link to="/digests" className="text-sm text-gray-500 hover:underline">
        &larr; Digests
      </Link>
      <h1 className="text-2xl font-semibold mt-2 mb-4">
        Digest: {data.digest_date}
      </h1>

      <div className="grid sm:grid-cols-3 gap-4 mb-6">
        <div className="bg-white rounded shadow px-4 py-3">
          <p className="text-xs text-gray-500 uppercase">Items</p>
          <p className="text-lg font-semibold">{data.item_count}</p>
        </div>
        <div className="bg-white rounded shadow px-4 py-3">
          <p className="text-xs text-gray-500 uppercase">Sent at</p>
          <p className="text-sm">{data.sent_at}</p>
        </div>
        <div className="bg-white rounded shadow px-4 py-3">
          <p className="text-xs text-gray-500 uppercase">Telegram IDs</p>
          <p className="text-sm">{data.telegram_message_ids.join(", ") || "---"}</p>
        </div>
      </div>

      <div className="flex flex-wrap gap-4 mb-6 text-sm">
        <div>
          <h3 className="text-xs text-gray-500 uppercase mb-1">Dimensions</h3>
          {Object.entries(data.dimension_breakdown).map(([dim, c]) => (
            <div key={dim}>
              {dimensionLabel(dim)}: {c}
            </div>
          ))}
        </div>
        <div>
          <h3 className="text-xs text-gray-500 uppercase mb-1">Change types</h3>
          {Object.entries(data.change_type_distribution).map(([ct, c]) => (
            <div key={ct}>
              {ct.replace(/_/g, " ")}: {c}
            </div>
          ))}
        </div>
      </div>

      <div className="bg-white rounded shadow px-6 py-4">
        <h2 className="text-sm font-medium text-gray-700 mb-3">Message</h2>
        <div
          className="prose prose-sm max-w-none"
          dangerouslySetInnerHTML={{ __html: data.message_text }}
        />
      </div>
    </div>
  );
}
