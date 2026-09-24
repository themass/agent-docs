export function Tabs<T extends string>({
  value,
  items,
  onChange,
}: {
  value: T
  items: { id: T; label: string }[]
  onChange: (value: T) => void
}) {
  return (
    <div className="tabs" role="tablist">
      {items.map((item) => (
        <button
          key={item.id}
          className={value === item.id ? 'tab active' : 'tab'}
          onClick={() => onChange(item.id)}
          role="tab"
          aria-selected={value === item.id}
        >
          {item.label}
        </button>
      ))}
    </div>
  )
}
