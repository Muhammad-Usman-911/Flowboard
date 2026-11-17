// TanStack Query cache keys in one place. A key is an array; invalidating a prefix
// (e.g. ['tasks', 5]) refreshes every query that starts with it.

import type { TaskFilters } from '../api/types'

export const boardKeys = {
  board: (boardId: number) => ['board', boardId] as const,
  tasksRoot: (boardId: number) => ['tasks', boardId] as const,
  /** The full, unfiltered task list (the one WebSocket events patch directly). */
  allTasks: (boardId: number) => ['tasks', boardId, 'all'] as const,
  filteredTasks: (boardId: number, filters?: TaskFilters) =>
    filters ? (['tasks', boardId, 'filtered', filters] as const) : (['tasks', boardId, 'filtered'] as const),
}
