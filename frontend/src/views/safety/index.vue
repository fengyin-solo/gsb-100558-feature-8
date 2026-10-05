<template>
  <section class="page" data-module="safety">
    <header class="page-head">
      <div>
        <h2>安全措施管理</h2>
        <p class="page-desc">
          维护安全措施票：票签发后才能支撑检修计划完工；监护人所在队组是计划归属的唯一判定口径。
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
        <span>措施状态</span>
        <select v-model="statusFilter">
          <option value="">全部</option>
          <option v-for="s in statuses" :key="s" :value="s">{{ s }}</option>
        </select>
      </label>
      <label class="filter-item">
        <span>涉及设备</span>
        <input v-model="equipment" placeholder="按涉及设备检索" />
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
            <template v-if="column === '措施状态'">
              <span :class="['status-tag', row.已签发 ? 'ok' : 'warn']">{{ row[column] ?? '—' }}</span>
            </template>
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

    <div v-if="creating" class="modal-mask" @click.self="creating = false">
      <div class="modal-card">
        <h3>登记安全措施票</h3>
        <label v-for="field in formFields" :key="field.prop" class="form-item">
          <span>{{ field.label }}</span>
          <input v-model="form[field.prop]" :placeholder="field.placeholder" />
        </label>
        <p class="page-desc">监护人须在册（王强/李娟：一片区；赵敏/周磊：二片区），否则无法确定队组归属。</p>
        <div class="modal-actions">
          <button class="btn" type="button" @click="creating = false">取消</button>
          <button class="btn primary" type="button" @click="submitCreate">登记</button>
        </div>
        <p v-if="createError" class="error-text">{{ createError }}</p>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | boolean | null>

const ENDPOINT = '/api/safety'
const columns = ["措施编号", "措施类型", "涉及设备", "签发人", "执行人", "监护人", "归属队组", "所属片区", "有效期至", "措施状态"]
const statuses = ["待签发", "已签发", "执行中", "已解除"]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const keyword = ref('')
const statusFilter = ref('')
const equipment = ref('')

const stats = computed(() => [
  { label: '待签发票', value: rows.value.filter((r) => r.措施状态 === '待签发').length },
  { label: '执行中票', value: rows.value.filter((r) => r.措施状态 === '执行中').length },
  { label: '已签发（含解除）', value: rows.value.filter((r) => r.已签发).length },
])

const formFields = [
  { prop: '措施编号', label: '措施编号', placeholder: '如 SAFE-0006' },
  { prop: '措施类型', label: '措施类型', placeholder: '如 停电隔离' },
  { prop: '涉及设备', label: '涉及设备', placeholder: '须与检修设备名称一致' },
  { prop: '监护人', label: '监护人', placeholder: '王强 / 李娟 / 赵敏 / 周磊' },
  { prop: '执行人', label: '执行人', placeholder: '现场执行人' },
  { prop: '有效期至', label: '有效期至', placeholder: '2026-10-20' },
] as const

const creating = ref(false)
const createError = ref('')
const form = reactive<Record<string, string>>({})

const NEXT_ACTION: Record<string, string[]> = {
  '待签发': ['签发措施'],
  '已签发': ['开始执行'],
  '执行中': ['解除措施'],
  '已解除': [],
}

function availableActions(row: Row): string[] {
  return NEXT_ACTION[String(row.措施状态 ?? '')] ?? []
}

function resetFilters() {
  keyword.value = ''
  statusFilter.value = ''
  equipment.value = ''
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  Object.keys(form).forEach((key) => delete form[key])
  createError.value = ''
  creating.value = true
}

async function submitCreate() {
  createError.value = ''
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values: { ...form } }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      createError.value = payload.detail || payload.message || '登记失败'
      return
    }
    creating.value = false
    await reload()
  } catch (error) {
    createError.value = error instanceof Error ? error.message : '登记失败'
  }
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const payload = await response.json()
    if (!response.ok) {
      errorMessage.value = payload?.detail || '安全措施动作未生效'
    } else if (payload.ok === false) {
      errorMessage.value = payload.message
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
  if (statusFilter.value) query.set('status', statusFilter.value)
  if (equipment.value) query.set('equipment', equipment.value)
  try {
    const response = await request(`${ENDPOINT}?${query.toString()}`)
    if (!response.ok) throw new Error('安全措施票列表读取失败')
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '安全措施列表读取失败'
  }
}

onMounted(reload)
</script>
