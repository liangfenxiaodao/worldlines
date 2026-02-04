interface Props {
  page: number;
  pages: number;
  onPage: (p: number) => void;
}

export default function Pagination({ page, pages, onPage }: Props) {
  if (pages <= 1) return null;
  return (
    <div className="flex items-center gap-3 mt-4">
      <button
        disabled={page <= 1}
        onClick={() => onPage(page - 1)}
        className="px-3 py-1 text-sm rounded border border-gray-300 disabled:opacity-40"
      >
        Prev
      </button>
      <span className="text-sm text-gray-600">
        {page} / {pages}
      </span>
      <button
        disabled={page >= pages}
        onClick={() => onPage(page + 1)}
        className="px-3 py-1 text-sm rounded border border-gray-300 disabled:opacity-40"
      >
        Next
      </button>
    </div>
  );
}
