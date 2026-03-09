// TipTap extension: template variable chip (атомный нередактируемый тег типа {{first_name}})

import { Node, mergeAttributes } from '@tiptap/core'

declare module '@tiptap/core' {
  interface Commands<ReturnType> {
    templateVariable: {
      insertTemplateVariable: (varName: string, label: string) => ReturnType
    }
  }
}

export const TemplateVariableExtension = Node.create({
  name: 'templateVariable',
  group: 'inline',
  inline: true,
  atom: true, // undivisible — удаляется целиком

  addAttributes() {
    return {
      varName: {
        default: null,
        parseHTML: (el) => el.getAttribute('data-var'),
        renderHTML: (attrs) => ({ 'data-var': attrs.varName }),
      },
    }
  },

  parseHTML() {
    return [{ tag: 'span[data-type="template-var"]' }]
  },

  renderHTML({ node, HTMLAttributes }) {
    return [
      'span',
      mergeAttributes(HTMLAttributes, {
        'data-type': 'template-var',
        'class': 'template-var-chip',
        contenteditable: 'false',
      }),
      `{{${node.attrs.varName}}}`,
    ]
  },

  addCommands() {
    return {
      insertTemplateVariable:
        (varName: string, _label: string) =>
        ({ commands }) =>
          commands.insertContent({ type: this.name, attrs: { varName } }),
    }
  },
})
