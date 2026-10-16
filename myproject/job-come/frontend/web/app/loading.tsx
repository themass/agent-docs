export default function Loading() {
  return (
    <div className="animate-fade-in space-y-4">
      <div className="skeleton h-7 w-48" />
      <div className="skeleton h-4 w-full max-w-prose" />
      <div className="card card-pad space-y-3">
        <div className="skeleton h-4 w-32" />
        <div className="skeleton h-9 w-full" />
        <div className="skeleton h-9 w-40" />
      </div>
    </div>
  );
}
