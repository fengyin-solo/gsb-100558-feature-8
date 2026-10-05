<template>
  <section class="page" data-module="maintenance">
    <header class="page-head">
      <div>
        <h2>检修计划管理</h2>
        <p class="page-desc">
          检修设备必须先有已签发的安全措施票，票未签发不许完工；计划归属按措施票监护人所在队组判定。
          当前值班：{{ store.operator }}（{{ store.area }}·{{ store.role }}）
        </p>
      </div>
      <div class="page-actions">
        <button v-if="store.isAreaLead" class="btn primary" type="button" @click="openCreate">登记检修计划</button>
        <button class="btn" type="button" @click="exportRows">导出检修计划清单</button>
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
        <span>计划编号/设备</span>
        <input v-model="keyword" placeholder="按计划编号或检修设备检索" />
      </label>
      <label class="filter-item">
        <span>计划状态</span>
        <select v-model="statusFilter">
          <option value="">全部</option>
          <option v-for="s in statuses" :key="s" :value="s">{{ s }}</option>
        </select>
      </label>
      <label class="filter-item">
        <span>所属片区</span>
        <select v-model="areaFilter">
          <option value="">全部</option>
          <option value="一片区">一片区</option>
          <option value="二片区">二片区</option>
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
            <template v-if="column === '安全措施'">
              <a class="link" href="javascript:void(0)" @click="openTicket(row)">{{ row[column] || '—' }}</a>
            </template>
            <template v-else-if="column === '措施状态'">
              <span :class="['status-tag', row.措施已签发 ? 'ok' : 'warn']">{{ row[column] ?? '—' }}</span>
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
            <span v-if="!availableActions(row).length" class="muted-text">只读/无可用动作</span>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无检修计划数据，可先登记检修计划</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条检修计划记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <!-- 登记计划 -->
    <div v-if="creating" class="modal-mask" @click.self="creating = false">
      <div class="modal-card">
        <h3>登记检修计划（提交排期）</h3>
        <p class="page-desc">只有本片区负责人可提交；检修设备须绑定已签发的安全措施票。</p>
        <label v-for="field in formFields" :key="field.prop" class="form-item">
          <span>{{ field.label }}</span>
          <input v-model="form[field.prop]" :placeholder="field.placeholder" />
        </label>
        <div class="modal-actions">
          <button class="btn" type="button" @click="creating = false">取消</button>
          <button class="btn primary" type="button" @click="submitCreate">提交计划</button>
        </div>
        <p v-if="createError" class="error-text">{{ createError }}</p>
      </div>
    </div>

    <!-- 措施票详情 -->
    <div v-if="ticketDetail" class="modal-mask" @click.self="ticketDetail = null">
      <div class="modal-card">
        <h3>安全措施票详情</h3>
        <table class="detail-table">
          <tbody>
            <tr v-for="field in ticketFields" :key="field">
              <th>{{ field }}</th>
              <td>{{ ticketDetail[field] ?? '—' }}</td>
            </tr>
          </tbody>
        </table>
        <p class="page-desc">措施状态与检修计划列表实时同源；状态变化以安全措施页签发动作为准。</p>
        <div class="modal-actions">
          <button class="btn primary" type="button" @click="ticketDetail = null">知道了</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import { request } from '@/api/client'
import { useSessionStore } from '@/stores/session'

type Row = Record<string, string | number | boolean | null>

const store = useSessionStore()
const ENDPOINT = '/api/maintenance'
const columns = ["计划编号", "检修设备", "检修类别", "计划开始", "计划结束", "责任人", "安全措施", "措施状态", "措施监护人", "归属队组", "所属片区", "计划状态"]
const statuses = ["待审批", "已批复", "执行中", "已完工"]
const ticketFields = ["措施编号", "措施类型", "涉及设备", "签发人", "执行人", "监护人", "归属队组", "所属片区", "有效期至", "措施状态", "已签发"]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const keyword = ref('')
const statusFilter = ref('')
const areaFilter = ref('')

const stats = computed(() => [
  { label: '待审批计划', value: rows.value.filter((r) => r.计划状态 === '待审批').length },
  { label: '执行中计划', value: rows.value.filter((r) => r.计划状态 === '执行中').length },
  { label: '已完工计划', value: rows.value.filter((r) => r.计划状态 === '已完工').length },
])

const formFields = [
  { prop: '计划编号', label: '计划编号', placeholder: '如 MAIN-0006' },
  { prop: '检修设备', label: '检修设备', placeholder: '须与措施票涉及设备一致' },
  { prop: '检修类别', label: '检修类别', placeholder: '计划检修/日常维护/故障抢修/试验校验' },
  { prop: '计划开始', label: '计划开始', placeholder: '2026-10-08 09:00' },
  { prop: '计划结束', label: '计划结束', placeholder: '2026-10-08 17:00' },
  { prop: '安全措施', label: '措施编号', placeholder: '已签发的安全措施票编号，如 SAFE-0001' },
] as const

const creating = ref(false)
const createError = ref('')
const form = reactive<Record<string, string>>({})
const ticketDetail = ref<Row | null>(null)

// 当前状态可执行的动作
const NEXT_ACTION: Record<string, string[]> = {
  '待审批': ['提交审批'],
  '已批复': ['开始执行', '撤回计划'],
  '执行中': ['确认完工'],
  '已完工': [],
}
// 仅片区负责人可做的动作：计划编号提交、排期撤回
const LEAD_ACTIONS = new Set(['提交审批', '撤回计划'])

function canTouch(row: Row): boolean {
  return row.所属片区 === store.area
}

function availableActions(row: Row): string[] {
  const actions = NEXT_ACTION[String(row.计划状态 ?? '')] ?? []
  return actions.filter((action) => {
    if (!canTouch(row)) return false // 跨片区只读
    if (LEAD_ACTIONS.has(action)) return store.isAreaLead // 只有本片区负责人
    return true
  })
}

function resetFilters() {
  keyword.value = ''
  statusFilter.value = ''
  areaFilter.value = ''
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

async function openTicket(row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`/api/safety?keyword=${encodeURIComponent(String(row.安全措施 || ''))}`)
    const payload = await response.json()
    ticketDetail.value = (payload.items ?? [])[0] ?? null
    if (!ticketDetail.value) errorMessage.value = '未找到绑定的安全措施票'
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '措施票详情读取失败'
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
      errorMessage.value = payload?.detail || '操作被拒绝'
    } else if (payload.ok === false) {
      errorMessage.value = payload.message
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
  if (statusFilter.value) query.set('status', statusFilter.value)
  if (areaFilter.value) query.set('area', areaFilter.value)
  try {
    const response = await request(`${ENDPOINT}?${query.toString()}`)
    if (!response.ok) throw new Error('检修计划列表读取失败')
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '检修计划列表读取失败'
  }
}

onMounted(reload)
</script>
