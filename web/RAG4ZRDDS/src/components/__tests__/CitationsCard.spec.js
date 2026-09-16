// CitationsCard 回归测试（D 2026-09-16 代修时补）：
//  1) 相关度指标按检索模式显示——bm25/hybrid 的分数量纲不可比，不能伪装成"相关度百分比"；
//  2) 节点详情按来源格式展示——PDF 显示印刷/物理页区间，HTML 不显示页码、显示文件与格式。
import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, afterEach } from 'vitest'
import CitationsCard from '../CitationsCard.vue'

const sources = [
  { node_id: 'n1', source_id: 'user_manual', source_name: 'ZRDDS用户手册.pdf',
    section: '8.3.1 创建DataWriter', page_print: 80, page_physical: 86, score: 0.66 },
  { node_id: 'n2', source_id: 'user_manual', source_name: 'ZRDDS用户手册.pdf',
    section: '8.3.2', page_print: 82, page_physical: 88, score: 0.41 },
]

const mountCard = (props = {}) => mount(CitationsCard, {
  props: { sources, requestId: 'rid-12345678', health: { kb: {} }, ...props },
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('相关度指标按检索模式显示', () => {
  it('vector：显示"向量相关度"百分比与关联强度', () => {
    const text = mountCard({ scoreMode: 'vector' }).text()
    expect(text).toContain('向量相关度')
    expect(text).toContain('66.0%')
    expect(text).toMatch(/强关联|中关联|弱关联/)
    expect(text).not.toContain('池内相对')
  })

  it('bm25：显示原始词面分与不可比说明，不再渲染成百分比', () => {
    const wrapper = mountCard({
      scoreMode: 'bm25',
      sources: sources.map((s, i) => ({ ...s, score: i === 0 ? 20.037 : 8.5 })),
    })
    const text = wrapper.text()
    expect(text).toContain('BM25 词面分')
    expect(text).toContain('20.037')
    expect(text).toContain('不可比')
    expect(text).toContain('第 1 位')          // 用池内位次代替"关联强度"
    expect(text).not.toContain('66.0%')
  })

  it('hybrid：RRF 分数同样按"池内相对"标注', () => {
    const wrapper = mountCard({
      scoreMode: 'hybrid',
      sources: sources.map((s, i) => ({ ...s, score: i === 0 ? 0.0328 : 0.0164 })),
    })
    const text = wrapper.text()
    expect(text).toContain('RRF 融合分')
    expect(text).toContain('池内相对')
    expect(text).toContain('0.033')
  })
})

describe('节点详情按来源格式展示', () => {
  const openDetails = async (wrapper, payload) => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => payload })))
    await wrapper.findAll('.view-details-btn')[0].trigger('click')
    await flushPromises()
  }

  it('PDF：显示印刷页/物理页（跨页时显示区间）', async () => {
    const wrapper = mountCard()
    await openDetails(wrapper, {
      node_id: 'n1', source_id: 'user_manual', source_type: 'pdf', version: '2.0',
      page_print: 80, page_print_end: 81, page_physical: 86, page_physical_end: 87,
      section_path: 'PART 2 / 第8章 / 8.3.1 创建DataWriter', text: '正文…', source_url: null,
    })
    const panel = wrapper.find('.details-panel')
    expect(panel.text()).toContain('PDF 手册')
    expect(panel.text()).toContain('印刷页 80–81')
    expect(panel.text()).toContain('物理页 86–87')
    expect(panel.text()).toContain('正文…')
  })

  it('HTML：不显示页码，显示格式与可用的原文链接', async () => {
    const wrapper = mountCard({
      sources: [{ ...sources[0], node_id: 'h1', source_id: 'zrdds_dev_guide', source_name: 'cdoc' }],
    })
    await openDetails(wrapper, {
      node_id: 'h1', source_id: 'zrdds_dev_guide', source_type: 'html', version: '2.4',
      title: 'DDS_Publisher_create_datawriter',
      page_print: null, page_print_end: null, page_physical: null, page_physical_end: null,
      section_path: '发布模块 / 函数说明', text: 'DCPSDLL …',
      source_url: '/documents/zrdds_dev_guide/group___c_publication.html',
    })
    const panel = wrapper.find('.details-panel')
    expect(panel.text()).toContain('HTML 文档')
    expect(panel.text()).not.toContain('印刷页')
    expect(panel.text()).not.toContain('物理页')
    expect(panel.find('a.source-link').attributes('href'))
      .toBe('/documents/zrdds_dev_guide/group___c_publication.html')
    expect(panel.text()).toContain('打开该节点 HTML 原文')
  })
})
