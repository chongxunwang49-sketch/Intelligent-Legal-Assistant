import { marked } from 'marked'
import DOMPurify from 'dompurify'

marked.setOptions({ gfm: true, breaks: true })

const ALLOWED = [...DOMPurify.defaults.ALLOWED_TAGS, 'span', 'h1', 'h2', 'h3', 'img']
const ALLOWED_ATTR = [...DOMPurify.defaults.ALLOWED_ATTR, 'class', 'target']

export function renderMarkdown(text: string): string {
  if (!text) return ''
  const html = marked.parse(text) as string
  // 法条引用高亮：《XX》第X条
  const highlighted = html.replace(
    /《([^》<]{1,40}?)》(?:第([零一二三四五六七八九十百千0-9]+)条)?/g,
    (_, name, art) => `<span class="law-citation">《${name}》${art ? `第${art}条` : ''}</span>`
  )
  return DOMPurify.sanitize(highlighted, { ALLOWED_TAGS: ALLOWED, ALLOWED_ATTR: ALLOWED_ATTR })
}
