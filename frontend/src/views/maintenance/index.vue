<template>
  <section class="page" data-module="maintenance">
    <header class="page-head">
      <div>
        <h2>检修计划管理</h2>
        <p class="page-desc">
          检修计划与安全措施票绑定：设备没有已签发措施票不能完工；队组只按票上监护人所在队组算。
          当前身份：<strong>{{ store.identityLabel }}</strong>
        </p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" :disabled="!store.isManager" @click="openCreate">
          登记检修计划
        </button>
        <button class="btn" type="button" @click="exportRows">导出检修计划清单</button>
      </div>
    </header>

    <p v-if="!store.isManager" class="hint-bar">
      计划编号与排期只有本片区负责人能提交、能撤回；你当前身份只能执行本片区现场类动作，跨片区单据仅可查看。
    </p>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>计划编号</span>
        <input v-model="keyword" placeholder="按计划编号检索" />
      </label>
      <label class="filter-item">
        <span>计划状态</span>
        <select v-model="status">
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
            <template v-if="column === '措施状态'">
              <span :class="['status-tag', ticketClass(row[column])]">{{ row[column] ?? '—' }}</span>
            </template>
            <template v-else-if="column === '计划状态'">
              <span :class="['status-tag', planClass(row[column])]">{{ row[column] ?? '—' }}</span>
            </template>
            <template v-else>{{ row[column] ?? '—' }}</template>
          </td>
          <td class="row-actions">
            <template v-if="row.可改动 || row.status === '执行中' || row.status === '已批复'">
              <button
                v-for="action in availableActions(row)"
                :key="action.name"
                class="link"
                type="button"
                :disabled="!action.enabled"
                :title="action.reason"
                @click="runAction(action.name, row)"
              >
                {{ action.name }}
              </button>
            </template>
            <span v-else class="muted-text">{{ row.权限说明 || '只读' }}</span>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无检修计划数据，可先登记检修计划</td>
        </tr>
      </tbody>
    </table>

    <div v-if="creating" class="modal-mask" @click.self="creating = false">
      <form class="modal-card" @submit.prevent="submitCreate">
        <h3>登记检修计划（提交计划编号与排期）</h3>
        <p class="hint-bar">归属片区以后台值班身份为准：{{ store.area }}，前端不能改派到别的片区。</p>
        <label v-for="field in createFields" :key="field.key" class="form-item">
          <span>{{ field.label }}</span>
          <input v-model="form[field.key]" :type="field.type || 'text'" :required="true" />
        </label>
        <footer class="modal-foot">
          <button class="btn" type="button" @click="creating = false">取消</button>
          <button class="btn primary" type="submit">提交编号与排期</button>
        </footer>
      </form>
    </div>

    <footer class="page-foot">
      <span>共 {{ total }} 条检修计划记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'

import { readError, request } from '@/api/client'
import { useSessionStore } from '@/stores/session'

type Row = Record<string, string | number | boolean | null>

const store = useSessionStore()
const ENDPOINT = '/api/maintenance'
const columns = ["计划编号", "所属片区", "检修设备", "检修类别", "计划开始", "计划结束", "责任人",
                 "安全措施票", "措施状态", "所属队组", "队组来源", "计划状态"]
const statuses = ["待审批", "已批复", "执行中", "已完工"]

const stats = computed(() => {
  const waiting = rows.value.filter((row) => row.status === '待审批').length
  const running = rows.value.filter((row) => row.status === '执行中').length
  const done = rows.value.filter((row) => row.status === '已完工').length
  return [
    { label: '待审批计划', value: waiting },
    { label: '执行中计划', value: running },
    { label: '已完工计划', value: done },
  ]
})

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const keyword = ref('')
const status = ref('')
const creating = ref(false)
const createFields = [
  { key: '计划编号', label: '计划编号' },
  { key: '检修设备', label: '检修设备（须与安全措施票“涉及设备”一致）' },
  { key: '检修类别', label: '检修类别' },
  { key: '计划开始', label: '计划开始', type: 'date' },
  { key: '计划结束', label: '计划结束', type: 'date' },
]
const form = reactive<Record<string, string>>({})

const ALL_ACTIONS = ["提交审批", "开始执行", "确认完工", "撤回计划"]

function ticketClass(value: Row[keyof Row]) {
  return { 已签发: 'ok', 执行中: 'ok', 待签发: 'warn', 已解除: 'muted', 未配置: 'danger' }[String(value)] ?? 'muted'
}
function planClass(value: Row[keyof Row]) {
  return { 已完工: 'ok', 执行中: 'ok', 已批复: 'warn', 待审批: 'muted' }[String(value)] ?? 'muted'
}

/** 动作可见性与可用性直接读后端返回的权限字段，前端只做展示，闸门在后端。 */
function availableActions(row: Row) {
  const current = String(row.status ?? '')
  const visible: Record<string, boolean> = {
    提交审批: current === '待审批',
    开始执行: current === '已批复',
    确认完工: current === '执行中',
    撤回计划: current === '已批复',
  }
  const managerOnly = new Set(['提交审批', '撤回计划'])
  return ALL_ACTIONS.filter((name) => visible[name]).map((name) => {
    let enabled = Boolean(row.可改动)
    let reason = String(row.权限说明 ?? '')
    if (!managerOnly.has(name)) {
      const sameArea = store.area !== '' && row.所属片区 === store.area
      enabled = sameArea
      if (!store.operator) {
        enabled = false
        reason = '未选择值班身份，只读'
      } else if (!sameArea) {
        reason = `跨片区单据（${row.所属片区}），仅可查看`
      }
    }
    if (name === '确认完工' && !row.可完工) {
      enabled = false
      reason = '设备没有已签发的安全措施票，不能完工'
    }
    return { name, enabled, reason }
  })
}

function resetFilters() {
  keyword.value = ''
  status.value = ''
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  Object.keys(form).forEach((key) => delete form[key])
  errorMessage.value = ''
  creating.value = true
}

async function submitCreate() {
  errorMessage.value = ''
  const response = await request(ENDPOINT, { method: 'POST', body: JSON.stringify({ values: { ...form } }) })
  if (!response.ok) {
    errorMessage.value = await readError(response, '检修计划登记失败')
    return
  }
  creating.value = false
  await reload()
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
      errorMessage.value = payload.message || '检修计划动作未生效'
      return
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '检修计划操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams()
  if (keyword.value) query.set('keyword', keyword.value)
  if (status.value) query.set('status', status.value)
  try {
    const response = await request(`${ENDPOINT}?${query.toString()}`)
    if (!response.ok) {
      throw new Error('检修计划列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '检修计划列表读取失败'
  }
}

watch(() => store.operator?.code, () => void reload())
onMounted(reload)
</script>
