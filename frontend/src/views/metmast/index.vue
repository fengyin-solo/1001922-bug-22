<template>
  <section class="page" data-module="metmast">
    <header class="page-head">
      <div>
        <h2>测风塔管理</h2>
        <p class="page-desc">维护测风塔，围绕塔架编号、所在场站、塔架高度、测风层数做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn" type="button" @click="loadDeactivations">停用清单</button>
        <button class="btn" type="button" @click="exportRows">导出测风塔清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>塔架编号</span>
        <input v-model="keyword" placeholder="按塔架编号检索" />
      </label>
      <label class="filter-item">
        <span>测风状态</span>
        <select v-model="statusFilter">
          <option value="">全部状态</option>
          <option v-for="s in statuses" :key="s" :value="s">{{ s }}</option>
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
            <button class="link" type="button" @click="runAction('提交校验', row)">提交校验</button>
            <button class="link" type="button" @click="runAction('登记数据缺失', row)">登记数据缺失</button>
            <button class="link" type="button" @click="runAction('停用测风塔', row)">停用测风塔</button>
            <button
              class="link"
              type="button"
              :disabled="row['测风状态'] !== '数据缺失'"
              :title="row['测风状态'] === '数据缺失' ? '恢复使用' : '仅数据缺失状态可恢复'"
              @click="openRecover(row)"
            >
              恢复使用
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无符合条件的测风塔记录</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条测风塔记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <!-- 恢复使用弹窗：失败时保留已填内容，允许直接重试 -->
    <div v-if="recoverOpen" class="modal-mask" @click.self="closeRecover">
      <div class="modal">
        <h3>恢复使用 · {{ recoverForm['塔架编号'] }}</h3>
        <p class="page-desc">恢复后测风状态与数据完整率同时复位；校验历史保留，仅覆盖最近一次恢复结果。</p>
        <label class="filter-item">
          <span>塔架编号（如需更正）</span>
          <input v-model="recoverForm['塔架编号']" placeholder="留空则保持原编号" />
        </label>
        <label class="filter-item">
          <span>数据完整率（0-100，可不带 %）</span>
          <input v-model="recoverForm['数据完整率']" placeholder="例如 98.5，留空按 100% 复位" />
        </label>
        <label class="filter-item">
          <span>登记人</span>
          <input v-model="recoverForm['登记人']" placeholder="默认值班管理员" />
        </label>
        <p v-if="recoverError" class="error-text">{{ recoverError }}</p>
        <div class="modal-actions">
          <button class="btn ghost" type="button" :disabled="submitting" @click="closeRecover">取消</button>
          <button class="btn primary" type="button" :disabled="submitting" @click="submitRecover">
            {{ submitting ? '恢复中…' : '确认恢复' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 详情弹窗：字段与列表同一口径，另带校验历史与最近恢复 -->
    <div v-if="detail" class="modal-mask" @click.self="detail = null">
      <div class="modal">
        <h3>测风塔详情 · {{ detail['塔架编号'] }}</h3>
        <table class="data-table">
          <tbody>
            <tr v-for="column in columns" :key="column">
              <th>{{ column }}</th>
              <td>{{ detail[column] ?? '—' }}</td>
            </tr>
          </tbody>
        </table>
        <h4>校验历史（不被恢复覆盖）</h4>
        <table class="data-table">
          <thead><tr><th>校验日</th><th>结论</th><th>完整率</th></tr></thead>
          <tbody>
            <tr v-for="(h, i) in detail['校验历史']" :key="i">
              <td>{{ h['校验日'] }}</td>
              <td>{{ h['结论'] }}</td>
              <td>{{ h['完整率'] }}</td>
            </tr>
            <tr v-if="!detail['校验历史']?.length"><td colspan="3" class="empty-state">暂无校验记录</td></tr>
          </tbody>
        </table>
        <h4>最近一次恢复结果</h4>
        <p v-if="detail['最近恢复']" class="page-desc">
          {{ detail['最近恢复']['恢复日期'] }} · 完整率 {{ detail['最近恢复']['完整率'] }} · 登记人 {{ detail['最近恢复']['登记人'] }}
        </p>
        <p v-else class="page-desc">暂无恢复记录</p>
        <div class="modal-actions">
          <button class="btn primary" type="button" @click="detail = null">关闭</button>
        </div>
      </div>
    </div>

    <!-- 停用清单：同一座塔只显示一次 -->
    <div v-if="deactivations" class="modal-mask" @click.self="deactivations = null">
      <div class="modal">
        <h3>停用清单（{{ deactivations.length }} 座，已按塔架编号去重）</h3>
        <table class="data-table">
          <thead><tr><th>塔架编号</th><th>所在场站</th><th>停用日期</th></tr></thead>
          <tbody>
            <tr v-for="(d, i) in deactivations" :key="`${d['塔架编号']}-${i}`">
              <td>{{ d['塔架编号'] }}</td>
              <td>{{ d['所在场站'] }}</td>
              <td>{{ d['停用日期'] }}</td>
            </tr>
            <tr v-if="!deactivations.length"><td colspan="3" class="empty-state">暂无停用记录</td></tr>
          </tbody>
        </table>
        <div class="modal-actions">
          <button class="btn primary" type="button" @click="deactivations = null">关闭</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>
type HistoryItem = { '校验日': string; '结论': string; '完整率': string }
type Recovery = { '恢复日期': string; '完整率': string; '登记人': string } | null
type Detail = Row & { '校验历史'?: HistoryItem[]; '最近恢复'?: Recovery }

const ENDPOINT = '/api/metmast'
const columns = ['塔架编号', '所在场站', '塔架高度', '测风层数', '风速仪型号', '上次校验日', '数据完整率', '测风状态']
const statuses = ['待校验', '数据正常', '数据缺失', '已停用']

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const keyword = ref('')
const statusFilter = ref('')
const stats = ref([
  { label: '在运测风塔', value: '—' },
  { label: '数据缺失塔数', value: '—' },
  { label: '数据完整率', value: '—' },
])

const detail = ref<Detail | null>(null)
const deactivations = ref<Array<Record<string, string>> | null>(null)

// 恢复弹窗状态：失败只提示不清表单，保留内容供重试
const recoverOpen = ref(false)
const submitting = ref(false)
const recoverError = ref('')
const recoverTargetId = ref<number | null>(null)
const recoverForm = ref<Record<string, string>>({})

function resetFilters() {
  keyword.value = ''
  statusFilter.value = ''
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

async function openDetail(row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}`)
    if (!response.ok) throw new Error('明细读取失败')
    detail.value = (await response.json()) as Detail
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '明细读取失败'
  }
}

async function loadDeactivations() {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/deactivations`)
    if (!response.ok) throw new Error('停用清单读取失败')
    const payload = (await response.json()) as { items: Array<Record<string, string>> }
    deactivations.value = payload.items ?? []
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '停用清单读取失败'
  }
}

function openRecover(row: Row) {
  recoverTargetId.value = Number(row.id)
  recoverError.value = ''
  // 打开时用当前行预填；提交失败不清空，用户可改完直接重试
  recoverForm.value = {
    塔架编号: String(row['塔架编号'] ?? ''),
    数据完整率: '',
    登记人: '',
  }
  recoverOpen.value = true
}

function closeRecover() {
  if (submitting.value) return
  recoverOpen.value = false
  recoverError.value = ''
}

async function submitRecover() {
  if (recoverTargetId.value === null) return
  submitting.value = true
  recoverError.value = ''
  try {
    const response = await request(`${ENDPOINT}/${recoverTargetId.value}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action: '恢复使用', values: { ...recoverForm.value } }),
    })
    const payload = (await response.json().catch(() => null)) as { ok?: boolean; message?: string } | null
    if (!response.ok || !payload?.ok) {
      // 关键：失败时保留 recoverForm 里已填的内容，让用户改完重试
      recoverError.value = payload?.message || '恢复失败，请检查填写内容后重试'
      return
    }
    recoverOpen.value = false
    await reload()
  } catch (error) {
    recoverError.value = error instanceof Error ? error.message : '恢复请求未送达，内容已保留可重试'
  } finally {
    submitting.value = false
  }
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const payload = (await response.json().catch(() => null)) as { ok?: boolean; message?: string } | null
    if (!response.ok || !payload?.ok) {
      throw new Error(payload?.message || '操作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '测风塔操作失败'
  }
}

async function loadStats() {
  try {
    const response = await request(`${ENDPOINT}/stats`)
    if (!response.ok) return
    const data = (await response.json()) as Record<string, string>
    stats.value = [
      { label: '在运测风塔', value: String(data['在运测风塔'] ?? '—') },
      { label: '数据缺失塔数', value: String(data['数据缺失塔数'] ?? '—') },
      { label: '在运塔平均完整率', value: String(data['数据完整率'] ?? '—') },
    ]
  } catch {
    /* 统计卡片加载失败不阻塞列表 */
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams()
  if (keyword.value.trim()) query.set('keyword', keyword.value.trim())
  if (statusFilter.value) query.set('status', statusFilter.value)
  try {
    const response = await request(`${ENDPOINT}?${query.toString()}`)
    if (!response.ok) throw new Error('测风塔列表读取失败')
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    await loadStats()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '测风塔列表读取失败'
  }
}

onMounted(reload)
</script>
