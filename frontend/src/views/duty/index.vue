<template>
  <section class="page" data-module="duty">
    <header class="page-head">
      <div>
        <h2>值班工作台</h2>
        <p class="page-desc">
          检修计划每次状态变化（含越权被拒）都在此留痕，可按计划编号与片区追溯是谁动的。
          当前值班：{{ store.operator }}（{{ store.area }}·{{ store.role }}）
        </p>
      </div>
      <div class="page-actions">
        <button class="btn" type="button" @click="reload">刷新流水</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="(value, label) in summary" :key="label" class="stat-card">
        <span class="stat-label">{{ label }}</span>
        <strong class="stat-value">{{ value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>计划编号</span>
        <input v-model="planNo" placeholder="按计划编号检索" />
      </label>
      <label class="filter-item">
        <span>操作人片区</span>
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
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in logs" :key="String(row.id)">
          <td v-for="column in columns" :key="column">
            <template v-if="column === '结果'">
              <span :class="['status-tag', row[column] === '已生效' ? 'ok' : 'deny']">{{ row[column] }}</span>
            </template>
            <template v-else>{{ row[column] ?? '—' }}</template>
          </td>
        </tr>
        <tr v-if="!logs.length">
          <td :colspan="columns.length" class="empty-state">暂无检修计划变更记录</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条变更记录（最新在前）</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'
import { useSessionStore } from '@/stores/session'

type Row = Record<string, string | number | null>
type Summary = Record<string, number>

const store = useSessionStore()
const columns = ["记录时间", "计划编号", "检修设备", "变更动作", "变更前状态", "变更后状态", "操作人", "操作人片区", "归属队组", "结果", "说明"]

const logs = ref<Row[]>([])
const total = ref(0)
const summary = ref<Summary>({})
const errorMessage = ref('')
const planNo = ref('')
const areaFilter = ref('')

function resetFilters() {
  planNo.value = ''
  areaFilter.value = ''
  void reload()
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams()
  if (planNo.value) query.set('plan_no', planNo.value)
  if (areaFilter.value) query.set('area', areaFilter.value)
  try {
    const [logsRes, summaryRes] = await Promise.all([
      request(`/api/duty/logs?${query.toString()}`),
      request('/api/duty/summary'),
    ])
    if (!logsRes.ok || !summaryRes.ok) throw new Error('值班工作台数据读取失败')
    const payload = await logsRes.json()
    logs.value = payload.items ?? []
    total.value = payload.total ?? logs.value.length
    summary.value = await summaryRes.json()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '值班工作台数据读取失败'
  }
}

onMounted(reload)
</script>
