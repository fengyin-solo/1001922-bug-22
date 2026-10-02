<template>
  <section class="page" data-module="duty">
    <header class="page-head">
      <div>
        <h2>值班台账</h2>
        <p class="page-desc">值班排班与当班事项登记。运营看板与本页取自同一份数据，冲突时以台账为准。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记值班</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in statCards" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>值班日期</span>
        <input v-model="filters.shift_date" type="date" />
      </label>
      <label class="filter-item">
        <span>值班班组</span>
        <input v-model="filters.team" placeholder="按班组检索" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length" class="empty-state">暂无值班台账，可先登记值班</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条值班记录（数据来源：值班台账 duty_ledger）</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <div v-if="createVisible" class="modal-mask" @click.self="createVisible = false">
      <div class="modal">
        <h3>登记值班</h3>
        <label v-for="field in createFields" :key="field.prop" class="modal-field">
          <span>{{ field.label }}{{ field.required ? ' *' : '' }}</span>
          <input v-model="createForm[field.prop]" :type="field.type ?? 'text'" />
        </label>
        <p v-if="actionMessage" class="error-text">{{ actionMessage }}</p>
        <div class="modal-actions">
          <button class="btn ghost" type="button" @click="createVisible = false">取消</button>
          <button class="btn primary" type="button" :disabled="submitting" @click="submitCreate">
            {{ submitting ? '提交中…' : '确认登记' }}
          </button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>
type LedgerPayload = {
  items: Row[]
  total: number
  stats: Record<string, number>
  source: string
}

const ENDPOINT = '/api/duty/ledger'
const columns = ['值班日期', '值班班组', '值班人员', '接班时间', '交班时间', '在岗人数', '当班事项', '值班状态']

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<{ shift_date: string; team: string }>({ shift_date: '', team: '' })
const statCards = ref([
  { label: '今日值班记录', value: 0 },
  { label: '在岗班组', value: 0 },
  { label: '在岗人数', value: 0 },
])

const createVisible = ref(false)
const submitting = ref(false)
const actionMessage = ref('')
type CreateField = { prop: string; label: string; type?: string; required: boolean }
const createFields: CreateField[] = [
  { prop: '值班日期', label: '值班日期', type: 'date', required: true },
  { prop: '值班班组', label: '值班班组', required: true },
  { prop: '值班人员', label: '值班人员', required: true },
  { prop: '接班时间', label: '接班时间', required: false },
  { prop: '交班时间', label: '交班时间', required: false },
  { prop: '在岗人数', label: '在岗人数', type: 'number', required: false },
  { prop: '当班事项', label: '当班事项', required: false },
]
const createForm = ref<Record<string, string>>({})

function resetFilters() {
  filters.value = { shift_date: '', team: '' }
  void reload()
}

function openCreate() {
  actionMessage.value = ''
  createForm.value = {}
  createVisible.value = true
}

async function submitCreate() {
  actionMessage.value = ''
  submitting.value = true
  try {
    const response = await request('/api/duty', {
      method: 'POST',
      body: JSON.stringify({ values: { ...createForm.value } }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      throw new Error(payload.message || '值班登记失败')
    }
    createVisible.value = false
    await reload()
  } catch (error) {
    actionMessage.value = error instanceof Error ? error.message : '值班登记失败'
  } finally {
    submitting.value = false
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams()
  if (filters.value.shift_date) {
    query.set('shift_date', filters.value.shift_date)
  }
  if (filters.value.team) {
    query.set('team', filters.value.team)
  }
  try {
    // 台账列表与看板卡片来自同一次 ledger 返回，避免两份数据不一致
    const response = await request(`${ENDPOINT}?${query.toString()}`)
    if (!response.ok) {
      throw new Error('值班台账读取失败')
    }
    const payload = (await response.json()) as LedgerPayload
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    const stats = payload.stats ?? {}
    statCards.value = [
      { label: '今日值班记录', value: stats['今日值班记录'] ?? 0 },
      { label: '在岗班组', value: stats['在岗班组'] ?? 0 },
      { label: '在岗人数', value: stats['在岗人数'] ?? 0 },
    ]
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '值班台账读取失败'
  }
}

onMounted(reload)
</script>

<style scoped>
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 20;
}
.modal {
  background: #fff;
  border-radius: 8px;
  padding: 16px 20px;
  width: 420px;
  max-height: 85vh;
  overflow-y: auto;
}
.modal h3 {
  margin: 0 0 12px;
}
.modal-field {
  display: block;
  margin-bottom: 10px;
}
.modal-field span {
  display: block;
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 4px;
}
.modal-field input {
  width: 100%;
  padding: 6px 8px;
  border: 1px solid var(--border);
  border-radius: 6px;
}
.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 12px;
}
</style>
