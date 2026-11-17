// Keeps a WebSocket open to /ws/boards/{id} while the board page is mounted and turns
// server events into TanStack Query cache updates, so every open browser stays in sync.

import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { refreshTokens } from '../api/client'
import { tokenStore } from '../api/tokens'
import type { BoardEvent, Task } from '../api/types'
import { applyTaskEvent } from '../lib/boardCache'
import { boardKeys } from '../lib/queryKeys'

export type SocketStatus = 'connecting' | 'live' | 'offline'

export function socketUrl(boardId: number, token: string, location: Location = window.location): string {
  const base = import.meta.env.VITE_WS_URL ?? `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}`
  return `${base}/ws/boards/${boardId}?token=${encodeURIComponent(token)}`
}

export function useBoardSocket(boardId: number): SocketStatus {
  const queryClient = useQueryClient()
  const [status, setStatus] = useState<SocketStatus>('connecting')
  const retry = useRef(0)

  useEffect(() => {
    let socket: WebSocket | null = null
    let timer: ReturnType<typeof setTimeout> | undefined
    let pinger: ReturnType<typeof setInterval> | undefined
    let stopped = false

    const handle = (event: BoardEvent) => {
      if (event.type.startsWith('task.')) {
        // The unfiltered task list is patched in place: no refetch, no flicker.
        queryClient.setQueryData<Task[]>(boardKeys.allTasks(boardId), (old) => (old ? applyTaskEvent(old, event) : old))
        // Filtered views are simply refetched (the event may change what matches).
        queryClient.invalidateQueries({ queryKey: boardKeys.filteredTasks(boardId), exact: false })
        const taskId = Number(event.data.id)
        if (event.type !== 'task.deleted') queryClient.setQueryData(['task', taskId], event.data)
        queryClient.invalidateQueries({ queryKey: ['activity'] })
      } else if (event.type.startsWith('comment.')) {
        queryClient.invalidateQueries({ queryKey: ['comments', Number(event.data.task_id)] })
        queryClient.invalidateQueries({ queryKey: ['activity'] })
      } else if (event.type.startsWith('attachment.')) {
        queryClient.invalidateQueries({ queryKey: ['attachments', Number(event.data.task_id)] })
      } else if (event.type.startsWith('column.') || event.type.startsWith('label.') || event.type.startsWith('board.')) {
        queryClient.invalidateQueries({ queryKey: boardKeys.board(boardId) })
      }
    }

    const connect = () => {
      const token = tokenStore.access
      if (!token || stopped) return
      setStatus('connecting')
      socket = new WebSocket(socketUrl(boardId, token))
      socket.onopen = () => {
        retry.current = 0
        setStatus('live')
        // We may have missed events while disconnected: refetch once to catch up.
        queryClient.invalidateQueries({ queryKey: boardKeys.board(boardId) })
        queryClient.invalidateQueries({ queryKey: boardKeys.tasksRoot(boardId) })
        pinger = setInterval(() => socket?.readyState === WebSocket.OPEN && socket.send('ping'), 25_000)
      }
      socket.onmessage = (message) => handle(JSON.parse(message.data) as BoardEvent)
      socket.onclose = async (close) => {
        clearInterval(pinger)
        if (stopped) return
        setStatus('offline')
        if (close.code === 4404) return // not a member (or board deleted): don't retry
        if (close.code === 4401) {
          try {
            await refreshTokens() // the access token expired: get a new one first
          } catch {
            return
          }
        }
        const delay = Math.min(1000 * 2 ** retry.current, 15_000) // 1s, 2s, 4s ... 15s
        retry.current += 1
        timer = setTimeout(connect, delay)
      }
    }

    connect()
    return () => {
      stopped = true
      clearTimeout(timer)
      clearInterval(pinger)
      socket?.close()
    }
  }, [boardId, queryClient])

  return status
}
