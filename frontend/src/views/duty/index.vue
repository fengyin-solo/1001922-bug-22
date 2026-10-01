<template>
  <section class="page" data-module="duty">
    <header class="page-head">
      <div>
        <h2>值班台账</h2>
        <p class="page-desc">台账是待处理/异常量的唯一权威来源，运营概览看板与本页取自同一份数据；冲突时以本台账为准。</p>
      </div>
    </header>

    <div v-if="conflictNote" class="conflict-banner">
      {{ conflictNote }}
    </div>

    <form class="filter-bar" @submit.prevent="submitLedger">
      <label class="filter-item">
        <span>模块</span>
        <select v-model="form['模块']">
          <option v-for="m in moduleOptions" :key="m.key" :value="m.key">{{ m.label }}</option>
        </select>
      </label>
      <label class="filter-item">
        <span>待处理</span>
        <input v-model="form['待处理']" type="number" min="0" placeholder="0" />
      </label>
      <label class="filter-item">
        <span>异常量</span>
        <input v-model="form['异常量']" type="number" min="0" placeholder="0" />
      </label>
      <label class="filter-item">
        <span>值班人</span>
        <input v-model="form['值班人']" placeholder="默认值班管理员" />
      </label>
      <label class="filter-item wide">
        <span>备注</span>
        <input v-model="form['备注']" placeholder="可说明订正原因" />
      </label>
      <button class="btn primary" type="submit" :disabled="submitting">{{ submitting ? '登记中…' : '登记台账' }}</button>
    </form>
    <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td>{{ moduleLabel(row['模块']) }}</td>
          <td>{{ row['待处理'] }}</td>
          <td>{{ row['异常量'] }}</td>
          <td>{{ row['记录时间'] }}</td>
          <td>{{ row['值班人'] }}</td>
          <td>{{ row['备注'] || '—' }}</td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length" class="empty-state">暂无台账登记，看板暂按模块实时汇总展示</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ rows.length }} 个模块的台账记录（每模块取最近一条）</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'

type LedgerRow = {
  id: number
  模块: string
  待处理: number
  异常量: number
  记录时间: string
  值班人: string
  备注: string
}

const ENDPOINT = '/api/duty'
const columns = ['模块', '待处理', '异常量', '记录时间', '值班人', '备注']
const moduleOptions = [
  { key: 'windfarm', label: '风电场站' },
  { key: 'turbine', label: '风电机组' },
  { key: 'blade', label: '叶片' },
  { key: 'gearbox', label: '齿轮箱' },
  { key: 'generator', label: '发电机' },
  { key: 'pitch', label: '变桨系统' },
  { key: 'yaw', label: '偏航系统' },
  { key: 'metmast', label: '测风塔' },
  { key: 'collector', label: '集电线路' },
  { key: 'substation', label: '升压站' },
  { key: 'forecast', label: '功率预测' },
  { key: 'vibration', label: '振动监测' },
  { key: 'defect', label: '缺陷登记' },
  { key: 'maintjob', label: '检修任务' },
  { key: 'spare', label: '备件领用' },
  { key: 'patrol', label: '巡视检查' },
  { key: 'accept', label: '验收确认' },
  { key: 'settle', label: '电量结算' },
]

const rows = ref<LedgerRow[]>([])
const errorMessage = ref('')
const conflictNote = ref('')
const submitting = ref(false)
const form = ref<Record<string, string | number>>({
  模块: 'metmast',
  待处理: 0,
  异常量: 0,
  值班人: '',
  备注: '',
})

function moduleLabel(key: string): string {
  return moduleOptions.find((m) => m.key === key)?.label ?? key
}

async function submitLedger() {
  errorMessage.value = ''
  submitting.value = true
  try {
    const response = await request(`${ENDPOINT}/ledger`, {
      method: 'POST',
      body: JSON.stringify({ values: { ...form.value } }),
    })
    const payload = (await response.json().catch(() => null)) as { ok?: boolean; message?: string } | null
    if (!response.ok || !payload?.ok) {
      errorMessage.value = payload?.message || '台账登记失败，请重试'
      return
    }
    form.value['备注'] = ''
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '台账登记请求未送达'
  } finally {
    submitting.value = false
  }
}

async function reload() {
  try {
    const response = await request(`${ENDPOINT}/ledger`)
    if (!response.ok) throw new Error('值班台账读取失败')
    const payload = (await response.json()) as { items: LedgerRow[] }
    rows.value = payload.items ?? []
    // 与看板同源：从 /api/overview 读冲突提示，保证两边口径一致
    const overview = await request('/api/overview')
    if (overview.ok) {
      const data = (await overview.json()) as { conflicts?: Array<{ 模块: string }> }
      const names = (data.conflicts ?? []).map((c) => moduleLabel(c['模块'])).join('、')
      conflictNote.value = names
        ? `当前 ${names} 的台账登记与模块实时汇总不一致，看板已按台账口径展示。`
        : ''
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '值班台账读取失败'
  }
}

onMounted(reload)
</script>
