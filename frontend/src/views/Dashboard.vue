<template>
  <section class="page">
    <header class="page-head">
      <div>
        <h2>运营概览</h2>
        <p class="page-desc">汇总各业务模块的关键指标，先看总量再看异常。</p>
      </div>
    </header>

    <h3 class="section-title">值班看板</h3>
    <div class="stat-row">
      <article v-for="card in dutyCards" :key="card.label" class="stat-card">
        <span class="stat-label">{{ card.label }}</span>
        <strong class="stat-value">{{ card.value }}</strong>
      </article>
    </div>
    <p class="source-note">值班看板与「值班台账」取自同一份数据（duty_ledger），冲突时以台账为准。</p>

    <h3 class="section-title">业务模块</h3>
    <div class="stat-row">
      <article v-for="card in cards" :key="card.label" class="stat-card">
        <span class="stat-label">{{ card.label }}</span>
        <strong class="stat-value">{{ card.value }}</strong>
      </article>
    </div>
    <table class="data-table">
      <thead>
        <tr><th>业务模块</th><th>今日新增</th><th>待处理</th><th>异常量</th></tr>
      </thead>
      <tbody>
        <tr v-for="row in moduleRows" :key="row.name">
          <td>{{ row.name }}</td>
          <td>{{ row.created }}</td>
          <td>{{ row.pending }}</td>
          <td>{{ row.abnormal }}</td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { fetchJson, request } from '@/api/client'

type Overview = {
  cards: { label: string; value: number }[]
  modules: { name: string; created: number; pending: number; abnormal: number }[]
}

type DutyLedger = {
  stats: Record<string, number>
  source: string
}

const cards = ref<Overview['cards']>([])
const moduleRows = ref<Overview['modules']>([])
const dutyCards = ref<{ label: string; value: number }[]>([])

async function loadDutyBoard() {
  // 看板不单独维护统计，直接消费台账接口返回的同源 stats
  try {
    const response = await request('/api/duty/ledger')
    if (!response.ok) {
      return
    }
    const payload = (await response.json()) as DutyLedger
    dutyCards.value = [
      { label: '今日值班记录', value: payload.stats['今日值班记录'] ?? 0 },
      { label: '在岗班组', value: payload.stats['在岗班组'] ?? 0 },
      { label: '在岗人数', value: payload.stats['在岗人数'] ?? 0 },
    ]
  } catch {
    // 台账接口不可用时看板卡片留空，不用第二份数据兜底，避免口径不一致
  }
}

onMounted(async () => {
  void loadDutyBoard()
  try {
    const payload = await fetchJson<Overview>('/api/overview')
    cards.value = payload.cards
    moduleRows.value = payload.modules
  } catch {
    cards.value = [{"label": "业务模块", "value": 0}, {"label": "今日新增", "value": 0}]
    moduleRows.value = [{"name": "风电场站", "created": 0, "pending": 0, "abnormal": 0}, {"name": "风电机组", "created": 0, "pending": 0, "abnormal": 0}, {"name": "叶片", "created": 0, "pending": 0, "abnormal": 0}, {"name": "齿轮箱", "created": 0, "pending": 0, "abnormal": 0}, {"name": "发电机", "created": 0, "pending": 0, "abnormal": 0}, {"name": "变桨系统", "created": 0, "pending": 0, "abnormal": 0}, {"name": "偏航系统", "created": 0, "pending": 0, "abnormal": 0}, {"name": "测风塔", "created": 0, "pending": 0, "abnormal": 0}, {"name": "集电线路", "created": 0, "pending": 0, "abnormal": 0}, {"name": "升压站", "created": 0, "pending": 0, "abnormal": 0}, {"name": "功率预测", "created": 0, "pending": 0, "abnormal": 0}, {"name": "振动监测", "created": 0, "pending": 0, "abnormal": 0}, {"name": "缺陷登记", "created": 0, "pending": 0, "abnormal": 0}, {"name": "检修任务", "created": 0, "pending": 0, "abnormal": 0}, {"name": "备件领用", "created": 0, "pending": 0, "abnormal": 0}, {"name": "巡视检查", "created": 0, "pending": 0, "abnormal": 0}, {"name": "验收确认", "created": 0, "pending": 0, "abnormal": 0}, {"name": "电量结算", "created": 0, "pending": 0, "abnormal": 0}]
  }
})
</script>

<style scoped>
.section-title { font-size: 15px; margin: 16px 0 8px; }
.source-note { font-size: 12px; color: var(--muted); margin: 0 0 12px; }
</style>
