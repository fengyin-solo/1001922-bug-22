<template>
  <section class="page">
    <header class="page-head">
      <div>
        <h2>运营概览</h2>
        <p class="page-desc">汇总各业务模块的关键指标，先看总量再看异常。待处理与异常量与值班台账同源，冲突时以台账为准。</p>
      </div>
      <div class="page-actions">
        <RouterLink class="btn" to="/duty">前往值班台账</RouterLink>
      </div>
    </header>

    <div v-if="conflicts.length" class="conflict-banner">
      以下模块的台账登记与模块汇总不一致，已按台账口径展示：
      <span v-for="c in conflicts" :key="c['模块']">
        {{ moduleLabel(c['模块']) }}（待处理 {{ c['模块汇总']['待处理'] }}→{{ c['台账登记']['待处理'] }}，
        异常 {{ c['模块汇总']['异常量'] }}→{{ c['台账登记']['异常量'] }}）
      </span>
    </div>

    <div class="stat-row">
      <article v-for="card in cards" :key="card.label" class="stat-card">
        <span class="stat-label">{{ card.label }}</span>
        <strong class="stat-value">{{ card.value }}</strong>
      </article>
    </div>
    <table class="data-table">
      <thead>
        <tr><th>业务模块</th><th>今日新增</th><th>待处理</th><th>异常量</th><th>数据来源</th></tr>
      </thead>
      <tbody>
        <tr v-for="row in moduleRows" :key="row.name">
          <td>{{ moduleLabel(row.name) }}</td>
          <td>{{ row.created }}</td>
          <td>{{ row.pending }}</td>
          <td>{{ row.abnormal }}</td>
          <td>
            <span v-if="row.source === 'duty'" class="source-tag duty">值班台账</span>
            <span v-else class="source-tag module">模块汇总</span>
          </td>
        </tr>
      </tbody>
    </table>
    <footer class="page-foot">
      <span>数据来源：{{ source === 'duty-ledger' ? '值班台账（权威口径，与台账页同源）' : '模块汇总' }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { fetchJson } from '@/api/client'

type Conflict = {
  模块: string
  模块汇总: { 待处理: number; 异常量: number }
  台账登记: { 待处理: number; 异常量: number }
}
type Overview = {
  cards: { label: string; value: number }[]
  modules: { name: string; created: number; pending: number; abnormal: number; source?: string }[]
  source?: string
  conflicts?: Conflict[]
}

const labels: Record<string, string> = {
  windfarm: '风电场站', turbine: '风电机组', blade: '叶片', gearbox: '齿轮箱',
  generator: '发电机', pitch: '变桨系统', yaw: '偏航系统', metmast: '测风塔',
  collector: '集电线路', substation: '升压站', forecast: '功率预测',
  vibration: '振动监测', defect: '缺陷登记', maintjob: '检修任务',
  spare: '备件领用', patrol: '巡视检查', accept: '验收确认', settle: '电量结算',
}
function moduleLabel(key: string): string {
  return labels[key] ?? key
}

const cards = ref<Overview['cards']>([])
const moduleRows = ref<Overview['modules']>([])
const conflicts = ref<Conflict[]>([])
const source = ref('')

onMounted(async () => {
  try {
    const payload = await fetchJson<Overview>('/api/overview')
    cards.value = payload.cards
    moduleRows.value = payload.modules
    conflicts.value = payload.conflicts ?? []
    source.value = payload.source ?? ''
  } catch {
    cards.value = [{ label: '业务模块', value: 0 }, { label: '今日新增', value: 0 }]
    moduleRows.value = []
  }
})
</script>
