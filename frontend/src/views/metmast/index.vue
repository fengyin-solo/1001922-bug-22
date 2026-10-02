<template>
  <section class="page" data-module="metmast">
    <header class="page-head">
      <div>
        <h2>测风塔管理</h2>
        <p class="page-desc">维护测风塔，围绕塔架编号、所在场站、塔架高度、测风层数做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记测风塔</button>
        <button class="btn" type="button" :class="{ primary: view === 'deactivations' }" @click="toggleView">
          {{ view === 'deactivations' ? '返回测风塔列表' : '查看停用清单' }}
        </button>
        <button class="btn" type="button" @click="exportRows">导出测风塔清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in statCards" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <!-- 停用清单：同一测风塔只出现一次 -->
    <template v-if="view === 'deactivations'">
      <table class="data-table">
        <thead>
          <tr>
            <th v-for="column in deactivationColumns" :key="column">{{ column }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in deactivationRows" :key="`${row.mast_id}`">
            <td v-for="column in deactivationColumns" :key="column">{{ row[column] ?? '—' }}</td>
          </tr>
          <tr v-if="!deactivationRows.length">
            <td :colspan="deactivationColumns.length" class="empty-state">停用清单为空</td>
          </tr>
        </tbody>
      </table>
      <footer class="page-foot">
        <span>停用清单共 {{ deactivationRows.length }} 条（重复停用不会重复登记）</span>
        <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
      </footer>
    </template>

    <!-- 在运 / 全部测风塔列表 -->
    <template v-else>
      <form class="filter-bar" @submit.prevent="reload">
        <label class="filter-item">
          <span>塔架编号</span>
          <input v-model="filters.keyword" placeholder="按塔架编号检索" />
        </label>
        <label class="filter-item">
          <span>测风状态</span>
          <select v-model="filters.status">
            <option value="">全部状态</option>
            <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
          </select>
        </label>
        <button class="btn" type="submit">查询</button>
        <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
      </form>

      <table class="data-table">
        <thead>
          <tr>
            <th v-for="column in columns" :key="column">{{ column }}</th>
            <th>可执行动作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="String(row.id)">
            <td v-for="column in columns" :key="column">
              <button v-if="column === '塔架编号'" class="link" type="button" @click="openDetail(row)">
                {{ row[column] ?? '—' }}
              </button>
              <template v-else>{{ row[column] ?? '—' }}</template>
            </td>
            <td class="row-actions">
              <button
                v-for="action in availableActions(row)"
                :key="action"
                class="link"
                type="button"
                @click="runAction(action, row)"
              >
                {{ action }}
              </button>
            </td>
          </tr>
          <tr v-if="!rows.length">
            <td :colspan="columns.length + 1" class="empty-state">暂无测风塔数据，可先登记测风塔</td>
          </tr>
        </tbody>
      </table>
      <footer class="page-foot">
        <span>共 {{ total }} 条测风塔记录</span>
        <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
      </footer>
    </template>

    <!-- 登记测风塔 -->
    <div v-if="createVisible" class="modal-mask" @click.self="createVisible = false">
      <div class="modal">
        <h3>登记测风塔</h3>
        <label v-for="field in createFields" :key="field.prop" class="modal-field">
          <span>{{ field.label }}{{ field.required ? ' *' : '' }}</span>
          <input v-model="createForm[field.prop]" :placeholder="`请输入${field.label}`" />
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

    <!-- 恢复使用：失败时保留已填内容并允许重试 -->
    <div v-if="recoverVisible" class="modal-mask" @click.self="recoverVisible = false">
      <div class="modal">
        <h3>恢复使用 · {{ recoverRow?.['塔架编号'] }}</h3>
        <label class="modal-field">
          <span>塔架编号 *</span>
          <input v-model="recoverForm['塔架编号']" placeholder="请核对塔架编号" />
        </label>
        <label class="modal-field">
          <span>数据完整率（%）*</span>
          <input v-model="recoverForm['数据完整率']" placeholder="0～100 的数字，恢复后复位为 100" />
        </label>
        <label class="modal-field">
          <span>操作人</span>
          <input v-model="recoverForm['操作人']" placeholder="默认当前值班管理员" />
        </label>
        <label class="modal-field">
          <span>恢复说明</span>
          <input v-model="recoverForm['恢复说明']" placeholder="如：更换数据采集器" />
        </label>
        <p v-if="actionMessage" class="error-text">{{ actionMessage }}（已保留填写内容，可修改后重试）</p>
        <div class="modal-actions">
          <button class="btn ghost" type="button" @click="recoverVisible = false">取消</button>
          <button class="btn primary" type="button" :disabled="submitting" @click="submitRecover">
            {{ submitting ? '提交中…' : '确认恢复' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 详情：字段顺序与列表一致，附历史校验与最近一次恢复 -->
    <div v-if="detailVisible" class="modal-mask" @click.self="detailVisible = false">
      <div class="modal modal-wide">
        <h3>测风塔详情 · {{ detailRow?.['塔架编号'] }}</h3>
        <table class="data-table">
          <tbody>
            <tr v-for="column in columns" :key="column">
              <th>{{ column }}</th>
              <td>{{ detailRow?.[column] ?? '—' }}</td>
            </tr>
          </tbody>
        </table>
        <h4>历史校验记录（只追加，不覆盖）</h4>
        <table class="data-table">
          <thead>
            <tr><th>校验日期</th><th>操作人</th><th>校验结果</th><th>数据完整率</th></tr>
          </thead>
          <tbody>
            <tr v-for="item in historyRows" :key="String(item.id)">
              <td>{{ item['校验日期'] }}</td>
              <td>{{ item['操作人'] }}</td>
              <td>{{ item['校验结果'] }}</td>
              <td>{{ item['数据完整率'] ?? '—' }}</td>
            </tr>
            <tr v-if="!historyRows.length">
              <td colspan="4" class="empty-state">暂无校验记录</td>
            </tr>
          </tbody>
        </table>
        <h4>最近一次恢复登记（同一测风塔只保留最近一次）</h4>
        <table class="data-table">
          <tbody>
            <tr v-if="latestRecovery">
              <th>恢复日期</th><td>{{ latestRecovery['恢复日期'] }}</td>
              <th>操作人</th><td>{{ latestRecovery['操作人'] }}</td>
            </tr>
            <tr v-if="latestRecovery">
              <th>恢复时完整率</th><td>{{ latestRecovery['数据完整率'] }}</td>
              <th>恢复说明</th><td>{{ latestRecovery['恢复说明'] || '—' }}</td>
            </tr>
            <tr v-else>
              <td colspan="4" class="empty-state">暂无恢复登记</td>
            </tr>
          </tbody>
        </table>
        <div class="modal-actions">
          <button class="btn primary" type="button" @click="detailVisible = false">关闭</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>
type HistoryPayload = {
  校验记录: Array<Record<string, string | number | null>>
  最近恢复: Record<string, string | number | null> | null
}
type Summary = Record<'在运测风塔' | '数据缺失塔数' | '数据完整率', number>

const ENDPOINT = '/api/metmast'
const columns = ['塔架编号', '所在场站', '塔架高度', '测风层数', '风速仪型号', '上次校验日', '数据完整率', '测风状态']
const deactivationColumns = ['塔架编号', '停用日期', '操作人', '停用原因']
const statuses = ['待校验', '数据正常', '数据缺失', '已停用']

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<{ keyword: string; status: string }>({ keyword: '', status: '' })
const view = ref<'list' | 'deactivations'>('list')
const deactivationRows = ref<Row[]>([])
const statCards = ref([
  { label: '在运测风塔', value: 0 },
  { label: '数据缺失塔数', value: 0 },
  { label: '数据完整率', value: 0 },
])

const submitting = ref(false)
const actionMessage = ref('')
const createVisible = ref(false)
const recoverVisible = ref(false)
const detailVisible = ref(false)
const recoverRow = ref<Row | null>(null)
const detailRow = ref<Row | null>(null)
const historyRows = ref<HistoryPayload['校验记录']>([])
const latestRecovery = ref<HistoryPayload['最近恢复']>(null)

const createFields = [
  { prop: '塔架编号', label: '塔架编号', required: true },
  { prop: '所在场站', label: '所在场站', required: true },
  { prop: '塔架高度', label: '塔架高度', required: true },
  { prop: '测风层数', label: '测风层数', required: false },
  { prop: '风速仪型号', label: '风速仪型号', required: false },
] as const
const createForm = ref<Record<string, string>>({})
const recoverForm = ref<Record<string, string>>({
  塔架编号: '',
  数据完整率: '100',
  操作人: '',
  恢复说明: '',
})

function availableActions(row: Row): string[] {
  switch (row['测风状态']) {
    case '待校验':
      return ['提交校验', '登记数据缺失', '停用测风塔']
    case '数据正常':
      return ['登记数据缺失', '停用测风塔']
    case '数据缺失':
      return ['恢复使用', '停用测风塔']
    case '已停用':
      return []
    default:
      return ['提交校验', '登记数据缺失', '停用测风塔']
  }
}

function resetFilters() {
  filters.value = { keyword: '', status: '' }
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

async function toggleView() {
  actionMessage.value = ''
  if (view.value === 'list') {
    view.value = 'deactivations'
    await loadDeactivations()
  } else {
    view.value = 'list'
    await reload()
  }
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
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values: { ...createForm.value } }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      throw new Error(payload.message || '测风塔登记失败')
    }
    createVisible.value = false
    await Promise.all([reload(), loadSummary()])
  } catch (error) {
    actionMessage.value = error instanceof Error ? error.message : '测风塔登记失败'
  } finally {
    submitting.value = false
  }
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  actionMessage.value = ''
  if (action === '恢复使用') {
    openRecover(row)
    return
  }
  try {
    const response = await postAction(row.id as number, action, {})
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      throw new Error(payload.message || '测风塔动作未生效，请稍后重试')
    }
    await Promise.all([reload(), loadSummary()])
    if (view.value === 'deactivations') {
      await loadDeactivations()
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '测风塔操作失败'
  }
}

function openRecover(row: Row) {
  actionMessage.value = ''
  // 换一座塔重新带出编号；同一座塔重试时保留已填内容
  if (recoverRow.value?.id !== row.id) {
    recoverForm.value = {
      塔架编号: String(row['塔架编号'] ?? ''),
      数据完整率: '100',
      操作人: '',
      恢复说明: '',
    }
  }
  recoverRow.value = row
  recoverVisible.value = true
}

async function submitRecover() {
  if (!recoverRow.value) {
    return
  }
  actionMessage.value = ''
  submitting.value = true
  try {
    // 服务端做权威校验；失败时弹窗保留、已填内容不清空
    const response = await postAction(recoverRow.value.id as number, '恢复使用', { ...recoverForm.value })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      throw new Error(payload.message || '恢复失败，请稍后重试')
    }
    recoverVisible.value = false
    recoverRow.value = null
    await Promise.all([reload(), loadSummary()])
  } catch (error) {
    actionMessage.value = error instanceof Error ? error.message : '恢复失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}

async function openDetail(row: Row) {
  detailRow.value = row
  historyRows.value = []
  latestRecovery.value = null
  detailVisible.value = true
  try {
    const response = await request(`${ENDPOINT}/${row.id}/history`)
    if (!response.ok) {
      throw new Error('详情读取失败')
    }
    const payload = (await response.json()) as HistoryPayload
    historyRows.value = payload['校验记录'] ?? []
    latestRecovery.value = payload['最近恢复'] ?? null
  } catch {
    // 明细行已经有主表数据，历史拉不到时不阻塞查看
  }
}

function postAction(id: number, action: string, values: Record<string, string>) {
  return request(`${ENDPOINT}/${id}/actions`, {
    method: 'POST',
    body: JSON.stringify({ values: { action, ...values } }),
  })
}

async function loadSummary() {
  try {
    const response = await request(`${ENDPOINT}/summary`)
    if (!response.ok) {
      return
    }
    const payload = (await response.json()) as Summary
    statCards.value = [
      { label: '在运测风塔', value: payload['在运测风塔'] },
      { label: '数据缺失塔数', value: payload['数据缺失塔数'] },
      { label: '数据完整率', value: payload['数据完整率'] },
    ]
  } catch {
    // 统计卡片读取失败不阻塞列表
  }
}

async function loadDeactivations() {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/deactivations`)
    if (!response.ok) {
      throw new Error('停用清单读取失败')
    }
    const payload = await response.json()
    deactivationRows.value = payload.items ?? []
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '停用清单读取失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams()
  if (filters.value.keyword) {
    query.set('keyword', filters.value.keyword)
  }
  if (filters.value.status) {
    query.set('status', filters.value.status)
  }
  try {
    const response = await request(`${ENDPOINT}?${query.toString()}`)
    if (!response.ok) {
      throw new Error('测风塔列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '测风塔列表读取失败'
  }
}

onMounted(() => {
  void reload()
  void loadSummary()
})
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
.modal-wide {
  width: 720px;
}
.modal h3 {
  margin: 0 0 12px;
}
.modal h4 {
  margin: 14px 0 6px;
  font-size: 14px;
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
