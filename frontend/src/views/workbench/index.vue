<template>
  <section class="page" data-module="workbench">
    <header class="page-head">
      <div>
        <h2>值班工作台</h2>
        <p class="page-desc">检修计划状态变化逐笔落库，成功流转与越权拒绝都可追溯：谁、在什么时间、对哪条计划做了什么。</p>
      </div>
      <div class="page-actions">
        <button class="btn" type="button" @click="reload">刷新流水</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in summaryCards" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>结果</span>
        <select v-model="resultFilter">
          <option value="">全部</option>
          <option value="成功">成功</option>
          <option value="拒绝">越权拒绝</option>
        </select>
      </label>
      <label class="filter-item">
        <span>关键词</span>
        <input v-model="keyword" placeholder="计划编号 / 设备 / 操作人" />
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
        <tr v-for="row in rows" :key="String(row.id)" :class="{ 'row-denied': row.结果 === '拒绝' }">
          <td v-for="column in columns" :key="column">
            <span v-if="column === '结果'" :class="['status-tag', row.结果 === '成功' ? 'ok' : 'danger']">
              {{ row[column] }}
            </span>
            <template v-else>{{ row[column] ?? '—' }}</template>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length" class="empty-state">暂无状态变更流水</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条变更记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'

type ChangeRow = Record<string, string | number | null>

const ENDPOINT = '/api/workbench/changes'
const columns = ["时间", "模块", "动作", "结果", "计划编号", "检修设备", "所属片区", "操作人", "详情"]

const rows = ref<ChangeRow[]>([])
const total = ref(0)
const errorMessage = ref('')
const resultFilter = ref('')
const keyword = ref('')
const summaryCards = ref([
  { label: '变更总数', value: 0 },
  { label: '成功', value: 0 },
  { label: '越权拒绝', value: 0 },
])

function resetFilters() {
  resultFilter.value = ''
  keyword.value = ''
  void reload()
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams()
  if (resultFilter.value) query.set('result', resultFilter.value)
  if (keyword.value) query.set('keyword', keyword.value)
  try {
    const [listResp, summaryResp] = await Promise.all([
      request(`${ENDPOINT}?${query.toString()}`),
      request('/api/workbench/summary'),
    ])
    if (!listResp.ok || !summaryResp.ok) {
      throw new Error('值班工作台数据读取失败')
    }
    const payload = await listResp.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    const summary = await summaryResp.json()
    summaryCards.value = [
      { label: '变更总数', value: summary.变更总数 ?? 0 },
      { label: '成功', value: summary.成功 ?? 0 },
      { label: '越权拒绝', value: summary.越权拒绝 ?? 0 },
    ]
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '值班工作台数据读取失败'
  }
}

onMounted(reload)
</script>
