// Message Editor — TipTap WYSIWYG редактор для текста рассылки

import { useEffect, useCallback } from 'react'
import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Link from '@tiptap/extension-link'
import Placeholder from '@tiptap/extension-placeholder'
import styles from './MessageEditor.module.css'

interface Props {
  value: string
  onChange: (html: string) => void
}

export function MessageEditor({ value, onChange }: Props) {
  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        // Telegram supports: <b>, <i>, <code>, <pre>, <a>
        // Disable heading, blockquote, etc. for Telegram compatibility
        heading: false,
        blockquote: false,
        bulletList: false,
        orderedList: false,
        listItem: false,
        horizontalRule: false,
      }),
      Link.configure({
        openOnClick: false,
        HTMLAttributes: {
          rel: 'noopener noreferrer',
          target: '_blank',
        },
      }),
      Placeholder.configure({
        placeholder: 'Введите текст рассылки...',
      }),
    ],
    content: value || '',
    onUpdate: ({ editor: ed }) => {
      onChange(ed.getHTML())
    },
  })

  // Sync external value changes
  useEffect(() => {
    if (editor && value !== editor.getHTML()) {
      editor.commands.setContent(value || '')
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value])

  const setLink = useCallback(() => {
    if (!editor) return
    const previousUrl = editor.getAttributes('link').href
    const url = window.prompt('URL ссылки:', previousUrl || 'https://')
    if (url === null) return
    if (url === '') {
      editor.chain().focus().extendMarkRange('link').unsetLink().run()
      return
    }
    editor.chain().focus().extendMarkRange('link').setLink({ href: url }).run()
  }, [editor])

  if (!editor) return null

  return (
    <div className={styles.container}>
      {/* Toolbar */}
      <div className={styles.toolbar}>
        <button
          className={`${styles.toolbarBtn} ${editor.isActive('bold') ? styles.toolbarBtnActive : ''}`}
          onClick={() => editor.chain().focus().toggleBold().run()}
          title="Жирный (Ctrl+B)"
          type="button"
        >
          <strong>B</strong>
        </button>
        <button
          className={`${styles.toolbarBtn} ${editor.isActive('italic') ? styles.toolbarBtnActive : ''}`}
          onClick={() => editor.chain().focus().toggleItalic().run()}
          title="Курсив (Ctrl+I)"
          type="button"
        >
          <em>I</em>
        </button>
        <button
          className={`${styles.toolbarBtn} ${editor.isActive('code') ? styles.toolbarBtnActive : ''}`}
          onClick={() => editor.chain().focus().toggleCode().run()}
          title="Код"
          type="button"
        >
          {'</>'}
        </button>
        <div className={styles.toolbarDivider} />
        <button
          className={`${styles.toolbarBtn} ${editor.isActive('link') ? styles.toolbarBtnActive : ''}`}
          onClick={setLink}
          title="Ссылка"
          type="button"
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M5.5 8.5L8.5 5.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            <path d="M7.5 9.5L6.35 10.65C5.37 11.63 3.77 11.63 2.79 10.65V10.65C1.81 9.67 1.81 8.07 2.79 7.09L3.94 5.94" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            <path d="M6.5 4.5L7.65 3.35C8.63 2.37 10.23 2.37 11.21 3.35V3.35C12.19 4.33 12.19 5.93 11.21 6.91L10.06 8.06" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
        </button>
        {editor.isActive('link') && (
          <button
            className={styles.toolbarBtn}
            onClick={() => editor.chain().focus().unsetLink().run()}
            title="Убрать ссылку"
            type="button"
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M2 2L12 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              <path d="M7.5 9.5L6.35 10.65C5.37 11.63 3.77 11.63 2.79 10.65V10.65C1.81 9.67 1.81 8.07 2.79 7.09L3.94 5.94" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              <path d="M6.5 4.5L7.65 3.35C8.63 2.37 10.23 2.37 11.21 3.35V3.35C12.19 4.33 12.19 5.93 11.21 6.91L10.06 8.06" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
          </button>
        )}
      </div>

      {/* Editor */}
      <EditorContent editor={editor} className={styles.editor} />
    </div>
  )
}
