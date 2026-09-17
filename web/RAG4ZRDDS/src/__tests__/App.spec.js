// 回答反馈落库链路（「有帮助/无帮助」按钮 → POST /feedback）：
// 这条交互此前只有实现、没有任何用例。本 spec 钉住 App.vue 侧的三段契约——
//   1) 反馈面板只在拿到 request_id 且回答落地后出现（否则后端按 404 拒收孤儿反馈）；
//   2) 提交体是 { request_id, rating }，与 server/api/feedback.py 的 FeedbackRequest 对齐；
//   3) 后端 4xx 的 `detail` 要透出给用户——FastAPI 走 `detail` 而非 `error`，
//      只读 `error` 会把"未找到请求…无法归因反馈"吞成"反馈提交失败：404"。
import { mount, flushPromises } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import App from '../App.vue'

const RID = 'rid-test-0001'
const SOURCE = {
  node_id: 'n1',
  source_id: 'user_manual',
  page_print: [55, 56],
  section_keyword: '6.3.6 选择Domain ID和创建多个域',
}
const HEALTHZ = {
  status: 'ok',
  mode: 'live',
  kb: {
    experiment: 'struct_v1',
    retrieval_mode: 'vector',
    index_dirname: 'idx_v1',
    node_total: 120,
    sources: [],
  },
  experiments: ['struct_v1'],
  experiment_modes: { struct_v1: 'vector' },
}

const jsonResponse = (body, status = 200) => ({
  ok: status >= 200 && status < 300,
  status,
  json: async () => body,
})

// /query 是 SSE：按帧切片喂给 reader，模拟真实的分块读取
const sseResponse = () => {
  const frames = [
    `event: sources\ndata: ${JSON.stringify({ request_id: RID, sources: [SOURCE] })}\n\n`,
    `event: done\ndata: ${JSON.stringify({ request_id: RID, answer: '这是答案', sources: [SOURCE] })}\n\n`,
  ]
  const chunks = frames.map((frame) => new TextEncoder().encode(frame))
  let index = 0
  return {
    ok: true,
    status: 200,
    body: {
      getReader: () => ({
        read: async () =>
          index < chunks.length ? { done: false, value: chunks[index++] } : { done: true, value: undefined },
      }),
    },
  }
}

function installFetch({ feedback, query } = {}) {
  const calls = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url, options = {}) => {
      calls.push({ url, options })
      if (url === '/healthz') return jsonResponse(HEALTHZ)
      if (url === '/query') return query ? query(options) : sseResponse()
      if (String(url).startsWith('/sources/')) return jsonResponse({ request_id: RID, sources: [SOURCE] })
      if (url === '/feedback') return feedback ? feedback(options) : jsonResponse({ status: 'recorded' }, 201)
      throw new Error(`未预期的请求：${url}`)
    }),
  )
  return calls
}

async function submitQuestion() {
  const wrapper = mount(App)
  await flushPromises() // /healthz
  await wrapper.find('textarea').setValue('如何创建 DataWriter？')
  await wrapper.find('button.submit-btn').trigger('click')
  await flushPromises() // /query 流 + /sources 回填
  return wrapper
}

describe('回答反馈落库（E：反馈按钮与数据落库）', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('没有 request_id 时不渲染反馈面板', async () => {
    installFetch()
    const wrapper = mount(App)
    await flushPromises()

    expect(wrapper.find('.feedback-panel').exists()).toBe(false)
  })

  it('回答落地后出现反馈面板，提交体为 { request_id, rating }', async () => {
    const calls = installFetch()
    const wrapper = await submitQuestion()

    expect(wrapper.find('.feedback-panel').exists()).toBe(true)

    await wrapper.findAll('button.feedback-btn')[0].trigger('click')
    await flushPromises()

    const call = calls.find((item) => item.url === '/feedback')
    expect(call).toBeTruthy()
    expect(JSON.parse(call.options.body)).toEqual({ request_id: RID, rating: 'up' })
    expect(wrapper.find('.feedback-status').text()).toBe('感谢反馈')
  })

  it('后端拒绝时透出 detail，而不是通用文案', async () => {
    installFetch({
      feedback: () => jsonResponse({ detail: `未找到请求 ${RID} 的回答记录，无法归因反馈。` }, 404),
    })
    const wrapper = await submitQuestion()

    await wrapper.findAll('button.feedback-btn')[1].trigger('click')
    await flushPromises()

    expect(wrapper.find('.feedback-status.is-error').text()).toContain('未找到请求')
  })
})

describe('/query 失败原因透出（与反馈同口径）', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('/query 4xx 走 detail（未知实验等），不再只显示状态码', async () => {
    installFetch({
      query: () => jsonResponse({ detail: "未知实验 'struct_ghost'；可用实验：struct_v1" }, 400),
    })
    const wrapper = mount(App)
    await flushPromises()
    await wrapper.find('textarea').setValue('如何创建 DataWriter？')
    await wrapper.find('button.submit-btn').trigger('click')
    await flushPromises()

    expect(wrapper.find('.error-box').text()).toContain('未知实验')
  })
})
