// SendPaymentModal — выбор товара, скидки и отправка ссылки на оплату клиенту
import { useState, useEffect, useMemo } from 'react'
import { api } from '@/services/api'
import styles from './SendPaymentModal.module.css'

type ProductType = 'subscription' | 'tokens' | 'guide' | 'quiz_plan' | 'flagship' | 'single_block'

interface Products {
  subscriptions: Array<{ id: number; name: string; price_rub: number; tokens_included: number; duration_days: number }>
  token_packages: Array<{ id: number; name: string; price_rub: number; tokens_amount: number }>
  guide: { price_rub: number }
  quiz_plan: { price_rub: number }
  quiz_plans?: Array<{ problem_key: string; culture: string; problem: string; price_rub: number }>
  single_blocks?: Array<{
    product_key: string
    culture_title: string
    articles: Array<{ key: string; title: string }>
    price_rub: number
  }>
  flagships: Array<{ product_key: string; title: string; price_rub: number }>
}

interface SendPaymentModalProps {
  clientId: number
  onClose: () => void
  onSent: () => void
}

// Группировка quiz_plans по культуре
type QuizPlan = { problem_key: string; culture: string; problem: string; price_rub: number }
function groupByCulture(plans: QuizPlan[]) {
  const groups: Record<string, QuizPlan[]> = {}
  for (const p of plans) {
    if (!groups[p.culture]) groups[p.culture] = []
    groups[p.culture].push(p)
  }
  return groups
}

export function SendPaymentModal({ clientId, onClose, onSent }: SendPaymentModalProps) {
  const [products, setProducts] = useState<Products | null>(null)
  const [loading, setLoading] = useState(true)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [productType, setProductType] = useState<ProductType>('subscription')
  const [productId, setProductId] = useState<string>('')
  // Для single_block: отдельный стейт для выбора культуры
  const [selectedCultureKey, setSelectedCultureKey] = useState<string>('')
  const [discountPercent, setDiscountPercent] = useState(0)
  const [discountDuration, setDiscountDuration] = useState(0)
  const [durationUnit, setDurationUnit] = useState<'hours' | 'days'>('hours')
  const [customMessage, setCustomMessage] = useState('')
  const [sendQuizAfterPayment, setSendQuizAfterPayment] = useState(false)

  useEffect(() => {
    api.getAvailableProducts()
      .then(data => {
        setProducts(data)
        if (data.subscriptions.length > 0) {
          setProductId(String(data.subscriptions[0].id))
        }
      })
      .catch(() => setError('Не удалось загрузить товары'))
      .finally(() => setLoading(false))
  }, [])

  // При смене типа товара — сбросить выбор
  useEffect(() => {
    if (!products) return
    switch (productType) {
      case 'subscription':
        setProductId(products.subscriptions[0]?.id ? String(products.subscriptions[0].id) : '')
        break
      case 'tokens':
        setProductId(products.token_packages[0]?.id ? String(products.token_packages[0].id) : '')
        break
      case 'guide':
        setProductId('')
        break
      case 'quiz_plan':
        setProductId(products.quiz_plans?.[0]?.problem_key || '')
        break
      case 'flagship':
        setProductId(products.flagships[0]?.product_key || '')
        break
      case 'single_block': {
        const first = products.single_blocks?.[0]
        if (first) {
          setSelectedCultureKey(first.product_key)
          const firstArticle = first.articles?.[0]
          setProductId(firstArticle ? `${first.product_key}__${firstArticle.key}` : '')
        } else {
          setSelectedCultureKey('')
          setProductId('')
        }
        break
      }
    }
  }, [productType, products])

  // При смене культуры в single_block — выбрать первую тему
  useEffect(() => {
    if (productType !== 'single_block' || !products || !selectedCultureKey) return
    const culture = products.single_blocks?.find(b => b.product_key === selectedCultureKey)
    const firstArticle = culture?.articles?.[0]
    setProductId(firstArticle ? `${selectedCultureKey}__${firstArticle.key}` : '')
  }, [selectedCultureKey, productType, products])

  const originalPrice = useMemo(() => {
    if (!products) return 0
    switch (productType) {
      case 'subscription': {
        const plan = products.subscriptions.find(p => String(p.id) === productId)
        return plan?.price_rub || 0
      }
      case 'tokens': {
        const pkg = products.token_packages.find(p => String(p.id) === productId)
        return pkg?.price_rub || 0
      }
      case 'guide':
        return products.guide.price_rub
      case 'quiz_plan':
        return products.quiz_plan.price_rub
      case 'flagship': {
        const fp = products.flagships.find(f => f.product_key === productId)
        return fp?.price_rub || 0
      }
      case 'single_block': {
        const block = products.single_blocks?.find(b => b.product_key === selectedCultureKey)
        return block?.price_rub || 1990
      }
    }
  }, [products, productType, productId, selectedCultureKey])

  const finalPrice = Math.max(1, Math.round(originalPrice * (1 - discountPercent / 100)))
  const discountHours = durationUnit === 'days' ? discountDuration * 24 : discountDuration

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (sending) return
    setSending(true)
    setError(null)
    try {
      let pid: string | number
      if (productType === 'guide') {
        pid = productType
      } else if (productType === 'quiz_plan') {
        pid = productId || 'quiz_plan'
      } else if (productType === 'flagship' || productType === 'single_block') {
        pid = productId
      } else {
        pid = Number(productId)
      }

      await api.sendPaymentLinkToClient(clientId, {
        product_type: productType,
        product_id: pid,
        discount_percent: discountPercent || undefined,
        discount_duration_hours: discountHours || undefined,
        custom_message: customMessage || undefined,
        send_quiz_after_payment: productType === 'quiz_plan' ? sendQuizAfterPayment : undefined,
      })
      onSent()
    } catch {
      setError('Не удалось отправить ссылку на оплату')
    } finally {
      setSending(false)
    }
  }

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) onClose()
  }

  // Группы quiz_plans по культуре
  const quizGroups = useMemo(() => {
    if (!products?.quiz_plans) return {}
    return groupByCulture(products.quiz_plans)
  }, [products])

  // Текущая культура для single_block
  const currentCultureArticles = useMemo(() => {
    if (!products?.single_blocks || !selectedCultureKey) return []
    return products.single_blocks.find(b => b.product_key === selectedCultureKey)?.articles || []
  }, [products, selectedCultureKey])

  return (
    <div className={styles.backdrop} onClick={handleBackdropClick}>
      <div className={styles.modal}>
        <div className={styles.header}>
          <h3 className={styles.title}>Отправить ссылку на оплату</h3>
          <button className={styles.closeBtn} onClick={onClose}>✕</button>
        </div>

        {loading ? (
          <div className={styles.loading}>Загрузка товаров...</div>
        ) : (
          <form onSubmit={handleSubmit} className={styles.form}>
            {/* Тип товара */}
            <div className={styles.field}>
              <label className={styles.label}>Тип товара</label>
              <select
                className={styles.select}
                value={productType}
                onChange={e => setProductType(e.target.value as ProductType)}
              >
                <option value="subscription">Подписка</option>
                <option value="tokens">Пакет токенов</option>
                <option value="guide">Готовое решение</option>
                <option value="quiz_plan">Презентация (99 ₽)</option>
                {products && products.flagships.length > 0 && (
                  <option value="flagship">Сезонная программа</option>
                )}
                {products && products.single_blocks && products.single_blocks.length > 0 && (
                  <option value="single_block">Отдельная тема (1990 ₽)</option>
                )}
              </select>
            </div>

            {/* Конкретный товар: subscription / tokens / flagship */}
            {(productType === 'subscription' || productType === 'tokens' || productType === 'flagship') && (
              <div className={styles.field}>
                <label className={styles.label}>Товар</label>
                <select
                  className={styles.select}
                  value={productId}
                  onChange={e => setProductId(e.target.value)}
                >
                  {productType === 'subscription' && products?.subscriptions.map(p => (
                    <option key={p.id} value={p.id}>
                      {p.name} — {p.price_rub} ₽ ({p.tokens_included} токенов / {p.duration_days} дн.)
                    </option>
                  ))}
                  {productType === 'tokens' && products?.token_packages.map(p => (
                    <option key={p.id} value={p.id}>
                      {p.tokens_amount} токенов — {p.price_rub} ₽
                    </option>
                  ))}
                  {productType === 'flagship' && products?.flagships.map(f => (
                    <option key={f.product_key} value={f.product_key}>
                      {f.title} — {f.price_rub} ₽
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* quiz_plan — выбор презентации с группировкой по культуре */}
            {productType === 'quiz_plan' && (
              <div className={styles.field}>
                <label className={styles.label}>Презентация</label>
                <select
                  className={styles.select}
                  value={productId}
                  onChange={e => setProductId(e.target.value)}
                >
                  {Object.entries(quizGroups).map(([culture, items]) => (
                    <optgroup key={culture} label={culture}>
                      {items.map(item => (
                        <option key={item.problem_key} value={item.problem_key}>
                          {item.problem}
                        </option>
                      ))}
                    </optgroup>
                  ))}
                </select>
              </div>
            )}

            {/* quiz_plan — опция запуска опроса после оплаты */}
            {productType === 'quiz_plan' && (
              <label className={styles.checkboxLabel}>
                <input
                  type="checkbox"
                  checked={sendQuizAfterPayment}
                  onChange={e => setSendQuizAfterPayment(e.target.checked)}
                  className={styles.checkbox}
                />
                Запустить опрос №2 через 90 сек после оплаты
              </label>
            )}

            {/* single_block — каскадный выбор: культура → тема */}
            {productType === 'single_block' && (
              <>
                <div className={styles.field}>
                  <label className={styles.label}>Культура</label>
                  <select
                    className={styles.select}
                    value={selectedCultureKey}
                    onChange={e => setSelectedCultureKey(e.target.value)}
                  >
                    {products?.single_blocks?.map(b => (
                      <option key={b.product_key} value={b.product_key}>
                        {b.culture_title}
                      </option>
                    ))}
                  </select>
                </div>
                <div className={styles.field}>
                  <label className={styles.label}>Тема</label>
                  <select
                    className={styles.select}
                    value={productId}
                    onChange={e => setProductId(e.target.value)}
                  >
                    {currentCultureArticles.map(a => (
                      <option key={a.key} value={`${selectedCultureKey}__${a.key}`}>
                        {a.title}
                      </option>
                    ))}
                  </select>
                </div>
              </>
            )}

            {/* Цена */}
            <div className={styles.priceBlock}>
              <span className={styles.priceLabel}>Цена:</span>
              {discountPercent > 0 ? (
                <>
                  <span className={styles.priceOld}>{originalPrice} ₽</span>
                  <span className={styles.priceArrow}>→</span>
                  <span className={styles.priceNew}>{finalPrice} ₽</span>
                </>
              ) : (
                <span className={styles.priceNew}>{originalPrice} ₽</span>
              )}
            </div>

            {/* Скидка */}
            <div className={styles.row}>
              <div className={styles.field}>
                <label className={styles.label}>Скидка %</label>
                <input
                  type="number"
                  className={styles.input}
                  value={discountPercent || ''}
                  onChange={e => setDiscountPercent(Math.min(100, Math.max(0, Number(e.target.value))))}
                  placeholder="0"
                  min={0}
                  max={100}
                />
              </div>
              <div className={styles.field}>
                <label className={styles.label}>Срок скидки</label>
                <div className={styles.durationRow}>
                  <input
                    type="number"
                    className={styles.input}
                    value={discountDuration || ''}
                    onChange={e => setDiscountDuration(Math.max(0, Number(e.target.value)))}
                    placeholder="0"
                    min={0}
                  />
                  <select
                    className={styles.unitSelect}
                    value={durationUnit}
                    onChange={e => setDurationUnit(e.target.value as 'hours' | 'days')}
                  >
                    <option value="hours">ч.</option>
                    <option value="days">дн.</option>
                  </select>
                </div>
              </div>
            </div>

            {/* Сообщение */}
            <div className={styles.field}>
              <label className={styles.label}>Сообщение (необязательно)</label>
              <textarea
                className={styles.textarea}
                value={customMessage}
                onChange={e => setCustomMessage(e.target.value)}
                placeholder="Текст перед описанием товара"
                rows={2}
              />
            </div>

            {error && <div className={styles.error}>{error}</div>}

            <div className={styles.actions}>
              <button type="button" className={styles.cancelBtn} onClick={onClose}>
                Отмена
              </button>
              <button
                type="submit"
                className={styles.submitBtn}
                disabled={sending || originalPrice === 0}
              >
                {sending ? 'Отправка...' : `Отправить (${finalPrice} ₽)`}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}
