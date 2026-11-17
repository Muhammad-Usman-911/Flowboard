import { describe, expect, it } from 'vitest'
import type { BoardEvent, Task } from '../../api/types'
import { applyTaskEvent, moveTaskLocally, removeTaskLocally, tasksInColumn } from '../boardCache'

function task(id: number, column_id: number, position: number): Task {
  return {
    id, column_id, position, board_id: 1, title: `T${id}`, description: '', priority: 'medium', due_date: null,
    assignee: null, created_by_id: null, labels: [], completed_at: null, created_at: '', updated_at: '',
  }
}

const titles = (tasks: Task[], column: number) => tasksInColumn(tasks, column).map((t) => `${t.title}@${t.position}`)

// Column 1: T1, T2, T3   Column 2: T4
const board = [task(1, 1, 0), task(2, 1, 1), task(3, 1, 2), task(4, 2, 0)]

describe('moveTaskLocally', () => {
  it('reorders inside a column', () => {
    expect(titles(moveTaskLocally(board, 3, 1, 0), 1)).toEqual(['T3@0', 'T1@1', 'T2@2'])
  })

  it('moves across columns and closes the gap', () => {
    const next = moveTaskLocally(board, 2, 2, 0)
    expect(titles(next, 1)).toEqual(['T1@0', 'T3@1'])
    expect(titles(next, 2)).toEqual(['T2@0', 'T4@1'])
  })

  it('clamps an index past the end and ignores unknown tasks', () => {
    expect(titles(moveTaskLocally(board, 1, 2, 99), 2)).toEqual(['T4@0', 'T1@1'])
    expect(moveTaskLocally(board, 42, 1, 0)).toBe(board)
  })

  it('does not mutate the input', () => {
    moveTaskLocally(board, 3, 2, 0)
    expect(board[2]).toEqual(task(3, 1, 2))
  })
})

describe('applyTaskEvent', () => {
  const event = (type: string, data: object): BoardEvent => ({ type, board_id: 1, actor_id: 9, data: data as Record<string, unknown> })

  it('applies a move from another user, idempotently', () => {
    const moved = event('task.moved', { ...task(1, 2, 1), title: 'T1' })
    const once = applyTaskEvent(board, moved)
    expect(titles(once, 1)).toEqual(['T2@0', 'T3@1'])
    expect(titles(once, 2)).toEqual(['T4@0', 'T1@1'])
    expect(applyTaskEvent(once, moved)).toEqual(once)
  })

  it('adds created tasks once and replaces updated ones', () => {
    const created = applyTaskEvent(board, event('task.created', task(5, 2, 1)))
    expect(created).toHaveLength(5)
    expect(applyTaskEvent(created, event('task.created', task(5, 2, 1)))).toHaveLength(5)
    const updated = applyTaskEvent(board, event('task.updated', { ...task(4, 2, 0), title: 'Renamed' }))
    expect(updated.find((t) => t.id === 4)?.title).toBe('Renamed')
  })

  it('removes deleted tasks and renumbers', () => {
    expect(titles(applyTaskEvent(board, event('task.deleted', { id: 1, column_id: 1 })), 1)).toEqual(['T2@0', 'T3@1'])
    expect(removeTaskLocally(board, 77)).toBe(board)
  })

  it('ignores unrelated events', () => {
    expect(applyTaskEvent(board, event('comment.created', { id: 1 }))).toBe(board)
  })
})
