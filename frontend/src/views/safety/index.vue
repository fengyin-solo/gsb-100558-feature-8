<template>
  <section class="page" data-module="safety">
    <header class="page-head">
      <div>
        <h2>安全措施管理</h2>
        <p class="page-desc">
          维护安全措施票。措施状态与检修计划列表同源实时读取；队组按监护人所在队组判定，全平台只此一份口径。
        </p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记安全措施票</button>
        <button class="btn" type="button" @click="exportRows">导出安全措施清单</button>
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
        <span>措施编号</span>
        <input v-model="keyword" placeholder="按措施编号检索" />
      </label>
      <label class="filter-item">
        <span>涉及设备</span>
        <input v-model="equipment" placeholder="按涉及设备检索" />
      </label>
      <label class="filter-item">
        <span>措施状态</span>
        <select v-model="statusFilter">
          <option value="">全部</option>
          <option v-for="item in statuses" :key="item" :value="item">{{ item }}</option>
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
            <span v-if="column === '措施状态'" :class="['status-tag', ticketClass(row[column])]">{{ row[column] ?? '—' }}</span>
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
          <td :colspan="columns.length + 1" class="empty-state">暂无安全措施数据，可先登记安全措施票</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条安全措施记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/safety'
const columns = ["措施编号", "措施类型", "涉及设备", "签发人", "执行人", "监护人", "监护队组", "有效期至", "措施状态"]
const statuses = ["待签发", "已签发", "执行中", "已解除"]

const stats = computed(() => [
  { label: '待签发票', value: rows.value.filter((row) => row.status === '待签发').length },
  { label: '执行中票', value: rows.value.filter((row) => row.status === '执行中').length },
  { label: '已解除票', value: rows.value.filter((row) => row.status === '已解除').length },
])

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const keyword = ref('')
const equipment = ref('')
const statusFilter = ref('')

function ticketClass(value: Row[keyof Row]) {
  return { 已签发: 'ok', 执行中: 'ok', 待签发: 'warn', 已解除: 'muted' }[String(value)] ?? 'muted'
}

function availableActions(row: Row): string[] {
  switch (String(row.status)) {
    case '待签发':
      return ['签发措施']
    case '已签发':
      return ['开始执行']
    case '执行中':
      return ['解除措施']
    default:
      return []
  }
}

function resetFilters() {
  keyword.value = ''
  equipment.value = ''
  statusFilter.value = ''
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '安全措施票登记入口尚未接入审批流'
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const payload = (await response.json()) as { ok: boolean; message: string }
    if (!response.ok || !payload.ok) {
      errorMessage.value = payload.message || '安全措施动作未生效'
      return
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '安全措施操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams()
  if (keyword.value) query.set('keyword', keyword.value)
  if (equipment.value) query.set('equipment', equipment.value)
  if (statusFilter.value) query.set('status', statusFilter.value)
  try {
    const response = await request(`${ENDPOINT}?${query.toString()}`)
    if (!response.ok) {
      throw new Error('安全措施票列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '安全措施列表读取失败'
  }
}

onMounted(reload)
</script>
