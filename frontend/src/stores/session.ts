import { defineStore } from 'pinia'

export type Operator = {
  code: string
  name: string
  role: string
  area: string
}

export const useSessionStore = defineStore('session', {
  state: () => ({
    operator: null as Operator | null,
    operators: [] as Operator[],
    shiftLabel: '白班 08:00-20:00',
    scope: '光伏电站运维管理平台',
  }),
  getters: {
    isManager: (state) => state.operator?.role === '片区负责人',
    area: (state) => state.operator?.area ?? '',
    identityLabel: (state) =>
      state.operator
        ? `${state.operator.name}（${state.operator.area}·${state.operator.role}）`
        : '只读访客（未选择值班身份）',
  },
  actions: {
    setOperators(operators: Operator[]) {
      this.operators = operators
      if (!this.operator && operators.length > 0) {
        this.operator = operators[0]
      }
    },
    switchOperator(code: string) {
      this.operator = this.operators.find((item) => item.code === code) ?? null
    },
  },
})
