// AdminMessageInput — отправка сообщений клиенту из админ-панели
import { useState, useRef, useCallback } from 'react'
import { api } from '@/services/api'
import styles from './AdminMessageInput.module.css'

interface AdminMessageInputProps {
  clientId: number
  disabled?: boolean
}

export function AdminMessageInput({ clientId, disabled }: AdminMessageInputProps) {
  const [text, setText] = useState('')
  const [isSending, setIsSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const handleSend = useCallback(async () => {
    const trimmed = text.trim()
    if (!trimmed || isSending) return

    setIsSending(true)
    setError(null)
    try {
      await api.sendMessageToClient(clientId, trimmed)
      setText('')
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto'
      }
    } catch (e) {
      setError('Не удалось отправить сообщение')
      console.error('Failed to send message:', e)
    } finally {
      setIsSending(false)
    }
  }, [clientId, text, isSending])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setText(e.target.value)
    const ta = e.target
    ta.style.height = 'auto'
    ta.style.height = Math.min(ta.scrollHeight, 120) + 'px'
  }

  return (
    <div className={styles.wrapper}>
      {error && <div className={styles.error}>{error}</div>}
      <div className={styles.inputRow}>
        <textarea
          ref={textareaRef}
          className={styles.textarea}
          value={text}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          placeholder="Написать клиенту..."
          rows={1}
          disabled={disabled || isSending}
        />
        <button
          className={styles.sendBtn}
          onClick={handleSend}
          disabled={!text.trim() || isSending || disabled}
          title="Отправить (Enter)"
        >
          {isSending ? '...' : '↑'}
        </button>
      </div>
    </div>
  )
}
