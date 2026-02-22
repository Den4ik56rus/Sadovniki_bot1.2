// Activity Item Component
import { format } from 'date-fns'
import { ru } from 'date-fns/locale'
import type { ActivityEvent } from '@/types'
import { useCurrencyStore } from '@/store'
import styles from './ActivityItem.module.css'

/** Удаляет HTML-теги из текста (для chat_message) */
function stripHtml(html: string): string {
  return html.replace(/<[^>]*>/g, '')
}

interface ActivityItemProps {
  event: ActivityEvent
  onTaskComplete?: (taskId: number) => void
  onTaskDelete?: (taskId: number) => void
  onNoteDelete?: (noteId: number) => void
  onTopicClick?: (topicId: number) => void
  onArticleClick?: (articleId: number) => void
}

export function ActivityItem({
  event,
  onTaskComplete,
  onTaskDelete,
  onNoteDelete,
  onTopicClick,
  onArticleClick,
}: ActivityItemProps) {
  const { usdRate } = useCurrencyStore()

  const formatDate = (dateStr: string) => {
    try {
      return format(new Date(dateStr), 'd MMM, HH:mm', { locale: ru })
    } catch {
      return dateStr
    }
  }

  const formatCost = (costUsd: number) => {
    const costRub = costUsd * usdRate
    if (costRub < 1) {
      return `${Math.round(costRub * 100)} коп.`
    }
    return `${costRub.toFixed(0)} ₽`
  }

  const getEventIcon = () => {
    switch (event.event_type) {
      case 'consultation':
        return '💬'
      case 'chat_message':
        return event.event_data.direction === 'user' ? '👤' : '🤖'
      case 'task_created':
        return '📋'
      case 'task_completed':
        return '✅'
      case 'note':
        return '📝'
      case 'status_change':
        return '🔄'
      case 'tag_change':
        return '🏷️'
      case 'field_change':
        return '✏️'
      case 'article':
        return '📄'
      case 'payment':
        return '💰'
      case 'broadcast_sent':
        return '📢'
      case 'broadcast_button_click':
        return '👆'
      case 'broadcast_poll_answer':
        return '📊'
      default:
        return '📌'
    }
  }

  const handleConsultationClick = () => {
    const topicId = event.event_data.topic_id as number | undefined
    if (topicId && onTopicClick) {
      onTopicClick(topicId)
    }
  }

  const handleArticleClick = () => {
    const articleId = event.event_data.article_id as number | undefined
    if (articleId && onArticleClick) {
      onArticleClick(articleId)
    }
  }

  const renderContent = () => {
    const data = event.event_data

    switch (event.event_type) {
      case 'chat_message': {
        const direction = data.direction as string
        const text = stripHtml(data.text as string)
        const meta = data.meta as {
          type?: string
          callback_data?: string
          keyboard?: {
            type: string
            buttons: Array<Array<{ text: string; callback_data?: string }>>
          }
        } | null
        const isCallback = meta?.type === 'callback'
        const hasKeyboard = direction === 'bot' && meta?.keyboard?.buttons
        return (
          <div className={`${styles.chatBubble} ${direction === 'user' ? styles.chatUser : styles.chatBot}`}>
            {isCallback && <span className={styles.chatCallbackBadge}>кнопка</span>}
            <div className={styles.chatText}>{text}</div>
            {hasKeyboard && meta?.keyboard && (
              <div className={styles.keyboardButtons}>
                {meta.keyboard.buttons.map((row, rowIdx) => (
                  <div key={rowIdx} className={styles.keyboardRow}>
                    {row.map((btn, btnIdx) => (
                      <span key={btnIdx} className={styles.keyboardButton}>
                        {btn.text}
                      </span>
                    ))}
                  </div>
                ))}
              </div>
            )}
          </div>
        )
      }

      case 'consultation':
        return (
          <div
            className={`${styles.consultation} ${onTopicClick ? styles.clickable : ''}`}
            onClick={handleConsultationClick}
            role={onTopicClick ? 'button' : undefined}
            tabIndex={onTopicClick ? 0 : undefined}
            onKeyDown={(e) => e.key === 'Enter' && handleConsultationClick()}
          >
            <div className={styles.consultationHeader}>
              <span className={styles.consultationCategory}>
                {(data.category as string) || 'Консультация'}
              </span>
              {data.culture ? (
                <span className={styles.consultationCulture}>
                  {String(data.culture)}
                </span>
              ) : null}
              {onTopicClick && (
                <span className={styles.clickHint}>→</span>
              )}
            </div>
            {data.first_question ? (
              <div className={styles.consultationQuestion}>
                {String(data.first_question)}
                {String(data.first_question).length >= 150 && '...'}
              </div>
            ) : null}
            <div className={styles.consultationMeta}>
              <span>{String(data.message_count)} сообщ.</span>
              <span className={styles.consultationCost}>
                {formatCost((data.total_cost_usd as number) || 0)}
              </span>
            </div>
          </div>
        )

      case 'task_created':
        return (
          <div className={styles.task}>
            <div className={styles.taskTitle}>{String(data.title)}</div>
            {data.due_date ? (
              <div className={styles.taskDue}>
                📅 {formatDate(data.due_date as string)}
              </div>
            ) : null}
            {data.priority && data.priority !== 'medium' ? (
              <span className={`${styles.priority} ${styles[String(data.priority)]}`}>
                {data.priority === 'high' ? '🔴 Высокий' : '🔵 Низкий'}
              </span>
            ) : null}
            <div className={styles.taskActions}>
              <button
                className={styles.completeBtn}
                onClick={() => onTaskComplete?.(data.task_id as number)}
              >
                Выполнить
              </button>
              <button
                className={styles.deleteBtn}
                onClick={() => onTaskDelete?.(data.task_id as number)}
              >
                Удалить
              </button>
            </div>
          </div>
        )

      case 'task_completed':
        return (
          <div className={styles.taskCompleted}>
            <span className={styles.strikethrough}>{data.title as string}</span>
            <span className={styles.completedLabel}>выполнено</span>
          </div>
        )

      case 'note':
        return (
          <div className={styles.note}>
            <div className={styles.noteText}>
              {data.text_preview as string}
            </div>
            <button
              className={styles.deleteBtn}
              onClick={() => onNoteDelete?.(data.note_id as number)}
            >
              Удалить
            </button>
          </div>
        )

      case 'status_change':
        return (
          <div className={styles.statusChange}>
            <span className={styles.oldStatus}>{getStatusLabel(data.old_status as string)}</span>
            <span className={styles.arrow}>→</span>
            <span className={styles.newStatus}>{getStatusLabel(data.new_status as string)}</span>
          </div>
        )

      case 'tag_change':
        return (
          <div className={styles.tagChange}>
            {data.action === 'added' ? (
              <span>Добавлен тег <strong>{data.tag_name as string}</strong></span>
            ) : (
              <span>Удалён тег <strong>{data.tag_name as string}</strong></span>
            )}
          </div>
        )

      case 'field_change':
        return (
          <div className={styles.fieldChange}>
            <span>Изменено поле <strong>{data.field_name as string}</strong></span>
          </div>
        )

      case 'article':
        return (
          <div
            className={`${styles.article} ${onArticleClick ? styles.clickable : ''}`}
            onClick={handleArticleClick}
            role={onArticleClick ? 'button' : undefined}
            tabIndex={onArticleClick ? 0 : undefined}
            onKeyDown={(e) => e.key === 'Enter' && handleArticleClick()}
          >
            <div className={styles.articleHeader}>
              <span className={styles.articleLabel}>Статья</span>
              {onArticleClick && (
                <span className={styles.clickHint}>→</span>
              )}
            </div>
            {data.topic ? (
              <div className={styles.articleTopic}>
                {String(data.topic)}
                {String(data.topic).length >= 100 && '...'}
              </div>
            ) : null}
            <div className={styles.articleMeta}>
              <span>{Number(data.article_length || 0).toLocaleString()} симв.</span>
              <span className={styles.articleCost}>
                {formatCost((data.cost_usd as number) || 0)}
              </span>
              {data.llm_model ? (
                <span className={styles.articleModel}>{String(data.llm_model)}</span>
              ) : null}
            </div>
          </div>
        )

      case 'payment': {
        const paymentData = data as {
          payment_id: number
          amount_rub: number
          payment_type: 'subscription' | 'tokens'
          paid: boolean
          product_name: string
          paid_at: string | null
        }

        return (
          <div className={styles.payment}>
            <div className={styles.paymentHeader}>
              <span className={styles.paymentType}>
                {paymentData.payment_type === 'subscription' ? 'Подписка' : 'Токены'}
              </span>
              <span className={paymentData.paid ? styles.paymentBadge : styles.paymentBadgePending}>
                {paymentData.paid ? '✓ Оплачено' : '⏳ Ожидание'}
              </span>
            </div>
            <div className={styles.paymentProduct}>{paymentData.product_name}</div>
            <div className={styles.paymentMeta}>
              <span className={styles.paymentAmount}>{paymentData.amount_rub.toFixed(0)} ₽</span>
              {paymentData.paid_at && (
                <span>{format(new Date(paymentData.paid_at), 'd MMM yyyy', { locale: ru })}</span>
              )}
            </div>
          </div>
        )
      }

      case 'broadcast_sent': {
        // message_text = full HTML (new API), message_preview = fallback (old API)
        const hasFullData = Boolean(data.message_text)
        const messageText = hasFullData
          ? String(data.message_text)
          : (data.message_preview ? stripHtml(String(data.message_preview)) : '')
        const photoFilename = data.photo_filename ? String(data.photo_filename) : ''
        const apiBase = import.meta.env.VITE_API_URL || '/api/admin'
        const photoUrl = photoFilename ? `${apiBase}/broadcasts/photo/${photoFilename}` : ''
        const buttons = Array.isArray(data.inline_buttons) ? data.inline_buttons as Array<{
          row: number; text: string; type: string; option_key?: string; url?: string
        }> : []
        const hasPoll = Boolean(data.has_poll)
        const pollQuestion = data.poll_question ? String(data.poll_question) : ''
        const pollOptions: string[] = Array.isArray(data.poll_options) ? data.poll_options as string[] : []
        const userPollRaw = data.user_poll_option_ids
        const userPollIds: number[] = Array.isArray(userPollRaw) ? userPollRaw : []
        const hasUserPollAnswer = userPollIds.length > 0
        const userButtonClicksRaw = data.user_button_clicks
        const userButtonClicks: string[] = Array.isArray(userButtonClicksRaw)
          ? userButtonClicksRaw.map(String)
          : (data.user_button_click ? [String(data.user_button_click)] : [])

        // Group buttons by row
        const buttonRows: Array<Array<typeof buttons[0]>> = []
        for (const btn of buttons) {
          while (buttonRows.length <= btn.row) buttonRows.push([])
          buttonRows[btn.row].push(btn)
        }

        return (
          <div className={styles.broadcast}>
            <div className={styles.broadcastHeader}>
              <span className={styles.broadcastLabel}>📢 Рассылка</span>
              <span className={styles.broadcastName}>{String(data.broadcast_title)}</span>
            </div>
            {photoUrl && (
              <div className={styles.broadcastPhoto}>
                <img
                  src={photoUrl}
                  alt="Фото рассылки"
                  className={styles.broadcastImg}
                  loading="lazy"
                />
              </div>
            )}
            {messageText && (
              hasFullData ? (
                <div
                  className={styles.broadcastText}
                  dangerouslySetInnerHTML={{ __html: messageText }}
                />
              ) : (
                <div className={styles.broadcastText}>{messageText}</div>
              )
            )}
            {buttonRows.length > 0 && (
              <div className={styles.broadcastButtons}>
                {buttonRows.map((row, rowIdx) => (
                  <div key={rowIdx} className={styles.broadcastButtonRow}>
                    {row.map((btn, btnIdx) => (
                      <span
                        key={btnIdx}
                        className={`${styles.broadcastButton} ${
                          btn.type === 'url' ? styles.broadcastButtonUrl : ''
                        } ${userButtonClicks.includes(btn.text) ? styles.broadcastButtonClicked : ''}`}
                      >
                        {btn.type === 'url' && '🔗 '}
                        {userButtonClicks.includes(btn.text) && '✓ '}
                        {btn.text}
                      </span>
                    ))}
                  </div>
                ))}
              </div>
            )}
            {hasPoll && pollQuestion && (
              <div className={styles.broadcastPoll}>
                <div className={styles.broadcastPollQuestion}>📊 {pollQuestion}</div>
                <div className={styles.broadcastPollOptions}>
                  {pollOptions.map((opt, i) => {
                    const isSelected = userPollIds.includes(i)
                    // Simulate percentage: selected options get a share, rest 0%
                    const pct = hasUserPollAnswer
                      ? (isSelected ? Math.round(100 / userPollIds.length) : 0)
                      : 0
                    return (
                      <div
                        key={i}
                        className={`${styles.broadcastPollOption} ${isSelected ? styles.broadcastPollSelected : ''}`}
                      >
                        {hasUserPollAnswer && (
                          <div
                            className={styles.broadcastPollBar}
                            style={{ width: `${pct}%` }}
                          />
                        )}
                        <span className={styles.broadcastPollOptionContent}>
                          {isSelected && <span className={styles.broadcastPollCheck}>✓</span>}
                          <span className={styles.broadcastPollOptionText}>{String(opt)}</span>
                        </span>
                        {hasUserPollAnswer && (
                          <span className={styles.broadcastPollPct}>{pct}%</span>
                        )}
                      </div>
                    )
                  })}
                </div>
              </div>
            )}
            {!hasFullData && (Boolean(data.has_photo) || (hasPoll && !pollQuestion)) && (
              <div className={styles.broadcastFallbackMeta}>
                {Boolean(data.has_photo) && !photoUrl && <span>📷 Фото</span>}
                {hasPoll && !pollQuestion && <span>📊 Опрос</span>}
              </div>
            )}
          </div>
        )
      }

      case 'broadcast_button_click': {
        const isUrlClick = data.button_type === 'url'
        const replyText = data.reply_text ? String(data.reply_text) : null
        const askForResponse = data.ask_for_response === true
        const textResponse = data.text_response ? String(data.text_response) : null
        return (
          <>
            <div className={`${styles.broadcastResponse} ${isUrlClick ? styles.broadcastResponseUrl : ''}`}>
              <div className={styles.broadcastResponseIcon}>{isUrlClick ? '🔗' : '👆'}</div>
              <div className={styles.broadcastResponseBody}>
                <span className={styles.broadcastResponseAction}>
                  {isUrlClick ? 'Перешёл по ссылке' : 'Нажал кнопку'}
                </span>
                <span className={styles.broadcastResponseValue}>«{String(data.button_text)}»</span>
                <span className={styles.broadcastResponseContext}>в рассылке «{String(data.broadcast_title)}»</span>
              </div>
            </div>
            {replyText && (
              <div className={styles.botReplyBubble}>
                <div className={styles.botReplyIcon}>🤖</div>
                <div className={styles.botReplyText} dangerouslySetInnerHTML={{ __html: replyText }} />
              </div>
            )}
            {askForResponse && (
              <div className={styles.botReplyBubble}>
                <div className={styles.botReplyIcon}>🤖</div>
                <div className={styles.botReplyText}>Расскажите подробнее — мы обязательно прочитаем ваш ответ:</div>
              </div>
            )}
            {textResponse && (
              <div className={styles.userTextResponse}>
                <div className={styles.userTextResponseIcon}>✍️</div>
                <div className={styles.userTextResponseBody}>
                  <span className={styles.userTextResponseLabel}>Ответ пользователя:</span>
                  <span className={styles.userTextResponseText}>{textResponse}</span>
                </div>
              </div>
            )}
          </>
        )
      }

      // broadcast_poll_answer — hidden, shown inline in broadcast_sent card
      case 'broadcast_poll_answer':
        return null

      default:
        return <div>Неизвестное событие</div>
    }
  }

  const getStatusLabel = (status: string) => {
    const labels: Record<string, string> = {
      new: 'Новый',
      tried: 'Попробовал',
      trial_ended: 'Закончился триал',
      paid: 'Купил',
    }
    return labels[status] || status
  }

  // Poll answers are shown inline in broadcast_sent card — skip separate event
  if (event.event_type === 'broadcast_poll_answer') {
    return null
  }

  // Chat messages use a different layout (full-width, aligned bubbles)
  if (event.event_type === 'chat_message') {
    const direction = event.event_data.direction as string
    return (
      <div className={`${styles.chatItem} ${direction === 'user' ? styles.chatItemUser : styles.chatItemBot}`}>
        <div className={styles.content}>
          <div className={styles.body}>{renderContent()}</div>
          <div className={`${styles.time} ${direction === 'user' ? styles.chatTimeRight : ''}`}>
            {formatDate(event.created_at)}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className={styles.item}>
      <div className={styles.icon}>{getEventIcon()}</div>
      <div className={styles.content}>
        <div className={styles.body}>{renderContent()}</div>
        <div className={styles.time}>{formatDate(event.created_at)}</div>
      </div>
    </div>
  )
}
