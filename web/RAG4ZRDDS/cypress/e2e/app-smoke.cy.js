// 端到端冒烟：替换 create-vue 的样板 spec（原断言 h1「You did it!」，本应用不存在该标题，
// 必然失败）。这里只覆盖不依赖真实后端的**可判定**行为——应用外壳，以及 week4 复审 §4.1 F4
// 点名的两类"静态装饰"缺陷（检索模式选择器、Top-K chip）。

describe('应用外壳（无后端）', () => {
  it('渲染标题、输入框，并在拿不到 /healthz 时按默认 Top-K 显示', () => {
    cy.visit('/')
    cy.contains('h1', '从知识库中，找到可信的答案。').should('be.visible')
    cy.get('textarea[aria-label="输入你的问题"]').should('be.visible')
    // Top-K chip 曾写死后端条数（§4.1 F4）；mock/离线时按契约默认 5 显示。
    cy.contains('.control-chip', 'Top-K 5').should('be.visible')
  })

  it('未输入时不能提交，输入后可以提交', () => {
    cy.visit('/')
    cy.get('button.submit-btn').should('be.disabled')
    cy.get('textarea[aria-label="输入你的问题"]').type('如何调用 DataWriter API？')
    cy.get('button.submit-btn').should('be.enabled')
  })
})

describe('F4：检索模式选择器与 chip（/healthz 白名单驱动）', () => {
  beforeEach(() => {
    cy.intercept('GET', '/healthz', {
      statusCode: 200,
      body: {
        status: 'ok',
        mode: 'live',
        // top_k：/healthz 的 kb.top_k 为可选字段（后端按运行时 QUERY_TOP_K 下发，
        // 当前 server 尚未接线），这里故意取非 5 以证明 chip 不再写死
        kb: {
          experiment: 'struct_v1',
          retrieval_mode: 'vector',
          top_k: 3,
          index_dirname: 'idx_v1',
          node_total: 120,
          sources: [],
        },
        experiments: ['struct_v1', 'struct_bm25'],
        experiment_modes: { struct_v1: 'vector', struct_bm25: 'bm25' },
      },
    }).as('healthz')
  })

  it('选择器按白名单渲染，chip 跟随所选实验的通路', () => {
    cy.visit('/')
    cy.wait('@healthz')
    cy.contains('.control-chip', 'Top-K 3').should('be.visible')
    cy.contains('.control-chip', '语义检索').should('be.visible')

    cy.get('select.experiment-selector').select('struct_bm25')
    cy.contains('.control-chip', 'BM25 词面').should('be.visible')
  })

  it('提交时把所选实验带进请求体（否则多来源/BM25 通路在 UI 上不可达）', () => {
    cy.intercept('POST', '/query', { statusCode: 500, body: { error: 'stubbed' } }).as('query')
    cy.visit('/')
    cy.wait('@healthz')

    cy.get('select.experiment-selector').select('struct_bm25')
    cy.get('textarea[aria-label="输入你的问题"]').type('ZRDDS 故障码 E1003 是什么意思？')
    cy.get('button.submit-btn').click()

    cy.wait('@query').its('request.body').should('deep.equal', {
      question: 'ZRDDS 故障码 E1003 是什么意思？',
      experiment: 'struct_bm25',
    })
  })
})
