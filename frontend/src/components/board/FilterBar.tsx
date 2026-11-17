import type { Label, Member, Priority, TaskFilters } from '../../api/types'
import { PRIORITIES } from '../../lib/format'
import { Button, Input, Select } from '../ui'

interface Props {
  filters: TaskFilters
  onChange: (filters: TaskFilters) => void
  members: Member[]
  labels: Label[]
}

export function FilterBar({ filters, onChange, members, labels }: Props) {
  const set = (patch: Partial<TaskFilters>) => {
    const next = { ...filters, ...patch }
    // Drop empty values so the query key (and the URL params) stay clean.
    for (const key of Object.keys(next) as (keyof TaskFilters)[]) {
      if (next[key] === undefined || next[key] === '' || next[key] === false) delete next[key]
    }
    onChange(next)
  }
  const active = Object.keys(filters).length > 0

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Input
        type="search"
        placeholder="Search tasks…"
        aria-label="Search tasks"
        className="w-full sm:w-56"
        value={filters.q ?? ''}
        onChange={(e) => set({ q: e.target.value || undefined })}
      />
      <Select aria-label="Filter by assignee" className="w-auto" value={filters.assignee_id ?? ''} onChange={(e) => set({ assignee_id: e.target.value ? Number(e.target.value) : undefined })}>
        <option value="">Anyone</option>
        {members.map((m) => (
          <option key={m.user.id} value={m.user.id}>
            {m.user.full_name || m.user.username}
          </option>
        ))}
      </Select>
      <Select aria-label="Filter by priority" className="w-auto" value={filters.priority ?? ''} onChange={(e) => set({ priority: (e.target.value || undefined) as Priority | undefined })}>
        <option value="">Any priority</option>
        {PRIORITIES.map((p) => (
          <option key={p} value={p}>
            {p[0].toUpperCase() + p.slice(1)}
          </option>
        ))}
      </Select>
      <Select aria-label="Filter by label" className="w-auto" value={filters.label_id ?? ''} onChange={(e) => set({ label_id: e.target.value ? Number(e.target.value) : undefined })}>
        <option value="">Any label</option>
        {labels.map((l) => (
          <option key={l.id} value={l.id}>
            {l.name}
          </option>
        ))}
      </Select>
      <label className="flex items-center gap-1.5 text-sm text-slate-600 dark:text-slate-300">
        <input type="checkbox" className="accent-indigo-600" checked={!!filters.overdue} onChange={(e) => set({ overdue: e.target.checked })} />
        Overdue
      </label>
      {active && (
        <Button variant="ghost" onClick={() => onChange({})}>
          Clear
        </Button>
      )}
    </div>
  )
}
