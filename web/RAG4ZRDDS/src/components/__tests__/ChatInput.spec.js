// ChatInput 回归测试（D 2026-09-16 代修 F4 时补）：
// 变更前组件内有一个同名局部 `const availableExperiments = ref([])` 遮蔽了 prop，
// 导致模板 v-for 绑到空数组、检索模式下拉恒为空——F4 的"实验切换"整条链路不可用。
import { mount } from '@vue/test-utils'
import { describe, it, expect } from 'vitest'
import ChatInput from '../ChatInput.vue'
import chatInputSource from '../ChatInput.vue?raw'

const EXPERIMENTS = ['struct_v1', 'struct_multisrc_v1', 'struct_bm25', 'struct_hybrid']

const mountInput = (props = {}) => mount(ChatInput, { props })

describe('ChatInput 检索模式选择器（F4）', () => {
  it('availableExperiments prop 必须渲染为下拉选项', () => {
    const wrapper = mountInput({ availableExperiments: EXPERIMENTS })
    const options = wrapper.findAll('option').map((o) => o.text())
    EXPERIMENTS.forEach((exp) => expect(options).toContain(exp))
    // 首项为"默认（服务端配置）"，故选项数 = 实验数 + 1
    expect(wrapper.findAll('option')).toHaveLength(EXPERIMENTS.length + 1)
  })

  it('未选中实验时只提交 question', async () => {
    const wrapper = mountInput({ availableExperiments: EXPERIMENTS })
    await wrapper.find('textarea').setValue('如何创建 DataWriter？')
    await wrapper.find('.submit-btn').trigger('click')

    expect(wrapper.emitted('submit')).toHaveLength(1)
    expect(wrapper.emitted('submit')[0][0]).toEqual({ question: '如何创建 DataWriter？' })
  })

  it('选中实验后提交体带 experiment 字段', async () => {
    const wrapper = mountInput({ availableExperiments: EXPERIMENTS })
    await wrapper.find('textarea').setValue('E1003 是什么错误？')
    await wrapper.find('.experiment-selector').setValue('struct_bm25')
    await wrapper.find('.submit-btn').trigger('click')

    expect(wrapper.emitted('submit')[0][0]).toEqual({
      question: 'E1003 是什么错误？',
      experiment: 'struct_bm25',
    })
  })

  it('loading 期间选择器与提交按钮禁用', () => {
    const wrapper = mountInput({ availableExperiments: EXPERIMENTS, loading: true })
    expect(wrapper.find('.experiment-selector').attributes('disabled')).toBeDefined()
    expect(wrapper.find('.submit-btn').attributes('disabled')).toBeDefined()
  })
})

describe('工具栏检索通路 chip（F4）', () => {
  const MODES = { struct_v1: 'vector', struct_bm25: 'bm25', struct_hybrid: 'hybrid' }

  it('未选实验时 chip 跟随服务端当前模式（不再写死"语义检索"）', () => {
    const wrapper = mountInput({ availableExperiments: EXPERIMENTS, activeMode: 'bm25' })
    expect(wrapper.findAll('.control-chip')[0].text()).toBe('BM25 词面')
  })

  it('选中实验后 chip 立即按该实验的模式切换（无需先提交）', async () => {
    const wrapper = mountInput({
      availableExperiments: EXPERIMENTS,
      activeMode: 'vector',
      experimentModes: MODES,
    })
    expect(wrapper.findAll('.control-chip')[0].text()).toBe('语义检索')

    await wrapper.find('.experiment-selector').setValue('struct_hybrid')
    expect(wrapper.findAll('.control-chip')[0].text()).toBe('Hybrid RRF')

    // 换回"默认（服务端配置）"后回落服务端模式
    await wrapper.find('.experiment-selector').setValue('')
    expect(wrapper.findAll('.control-chip')[0].text()).toBe('语义检索')
  })

  it('未知模式 / 缺 health 数据时回落到"语义检索"且不渲染原始模式名', () => {
    const unknown = mountInput({ availableExperiments: EXPERIMENTS, activeMode: 'mystery' })
    expect(unknown.findAll('.control-chip')[0].text()).toBe('语义检索')

    const bare = mountInput()
    expect(bare.findAll('.control-chip')[0].text()).toBe('语义检索')
    expect(bare.findAll('.control-chip')[1].text()).toBe('Top-K 5')
  })

  it('Top-K chip 显示后端下发的实际条数（不再写死 5）', () => {
    const wide = mountInput({ availableExperiments: EXPERIMENTS, topK: 8 })
    expect(wide.findAll('.control-chip')[1].text()).toBe('Top-K 8')
  })
})

describe('F4 窄视口可用性（CSS 契约）', () => {
  // @media (max-width: 560px) 曾整块 `display: none` 隐藏 .toolbar-options，把
  // 检索模式选择器一起藏掉——窄窗口/分屏/未合成标签页（媒体查询按窄视口命中）
  // 下 F4 直接不可用。jsdom 不做真实布局，故退化为对 SFC 源码的契约断言。
  const source = chatInputSource
  const narrowBlock = /@media \(max-width: 560px\) \{([\s\S]*?)\n\}/.exec(source)?.[1] || ''

  it('窄视口媒体查询存在且不隐藏 .toolbar-options', () => {
    expect(narrowBlock).not.toBe('')
    expect(narrowBlock).not.toMatch(/\.toolbar-options\s*\{[^}]*display:\s*none/)
  })

  it('窄视口只收起装饰 chip，选择器样式仍生效', () => {
    expect(narrowBlock).toMatch(/\.toolbar-options \.control-chip\s*\{[^}]*display:\s*none/)
    expect(narrowBlock).toMatch(/\.experiment-selector\s*\{/)
  })
})

describe('终止当前回答（ChatInput 侧）', () => {
  it('生成中显示"停止生成"按钮，点击后 emit stop', async () => {
    const wrapper = mountInput({ loading: true })
    const stop = wrapper.find('.stop-btn')
    expect(stop.exists()).toBe(true)
    await stop.trigger('click')
    expect(wrapper.emitted('stop')).toHaveLength(1)
  })

  it('非生成状态不显示停止按钮', () => {
    const wrapper = mountInput({ loading: false })
    expect(wrapper.find('.stop-btn').exists()).toBe(false)
  })

  it('loading 期间停止按钮可用（提交按钮此时是禁用的）', () => {
    const wrapper = mountInput({ loading: true })
    expect(wrapper.find('.stop-btn').attributes('disabled')).toBeUndefined()
    expect(wrapper.find('.submit-btn').attributes('disabled')).toBeDefined()
  })
})
