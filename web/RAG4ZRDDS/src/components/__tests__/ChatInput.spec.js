// ChatInput 回归测试（D 2026-09-16 代修 F4 时补）：
// 变更前组件内有一个同名局部 `const availableExperiments = ref([])` 遮蔽了 prop，
// 导致模板 v-for 绑到空数组、检索模式下拉恒为空——F4 的"实验切换"整条链路不可用。
import { mount } from '@vue/test-utils'
import { describe, it, expect } from 'vitest'
import ChatInput from '../ChatInput.vue'

const EXPERIMENTS = ['struct_v1', 'struct_multisrc_v1', 'struct_bm25']

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
