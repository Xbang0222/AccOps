import { Button } from 'antd'

interface SelectAllToggleOption {
  label: string
  value: string
}

interface SelectAllToggleProps {
  options: SelectAllToggleOption[]
  selected: string[]
  onSelectAll: () => void
  onClear: () => void
  limit?: number
}

const buttonStyle: React.CSSProperties = { padding: 0, height: 'auto', fontSize: 12 }

export function SelectAllToggle({ options, selected, onSelectAll, onClear, limit }: SelectAllToggleProps) {
  if (limit !== undefined && limit <= 0) {
    return (
      <Button type="link" size="small" disabled style={buttonStyle}>
        已满
      </Button>
    )
  }

  const reachable = limit === undefined ? options.length : Math.min(limit, options.length)
  if (reachable === 0) {
    return null
  }

  const selectedSet = new Set(selected)
  const selectedFromOptions = options.reduce(
    (count, option) => count + (selectedSet.has(option.value) ? 1 : 0),
    0,
  )
  const allSelected = selectedFromOptions >= reachable

  const label = allSelected
    ? '取消全选'
    : limit === undefined
      ? '全选'
      : `全选（最多 ${reachable}）`

  return (
    <Button
      type="link"
      size="small"
      onClick={allSelected ? onClear : onSelectAll}
      style={buttonStyle}
    >
      {label}
    </Button>
  )
}
