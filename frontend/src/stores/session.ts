import { defineStore } from 'pinia'

export interface OperatorProfile {
  code: string
  name: string
  area: string
  role: string
}

/** 与后端花名册保持一致：工号 -> 姓名/片区/角色，头里只传工号，避免传中文。 */
export const OPERATORS: OperatorProfile[] = [
  { code: 'zhangwei', name: '张伟', area: '一片区', role: '片区负责人' },
  { code: 'sunjie', name: '孙杰', area: '一片区', role: '值班员' },
  { code: 'liuyang', name: '刘洋', area: '二片区', role: '片区负责人' },
  { code: 'chenchen', name: '陈晨', area: '二片区', role: '值班员' },
]

const STORAGE_KEY = 'ops-session-operator'

function resolveOperator(code: string): OperatorProfile {
  return OPERATORS.find((item) => item.code === code) ?? OPERATORS[0]
}

export const useSessionStore = defineStore('session', {
  state: () => {
    const saved = typeof localStorage !== 'undefined' ? localStorage.getItem(STORAGE_KEY) : null
    const profile = resolveOperator(saved ?? OPERATORS[0].code)
    return {
      operatorCode: profile.code,
      operator: profile.name,
      area: profile.area,
      role: profile.role,
      shiftLabel: '白班 08:00-20:00',
      scope: '光伏电站运维管理平台',
    }
  },
  getters: {
    canOperate: (state) => state.operator.length > 0,
    isAreaLead: (state) => state.role === '片区负责人',
  },
  actions: {
    switchOperator(code: string) {
      const profile = resolveOperator(code)
      this.operatorCode = profile.code
      this.operator = profile.name
      this.area = profile.area
      this.role = profile.role
      if (typeof localStorage !== 'undefined') {
        localStorage.setItem(STORAGE_KEY, profile.code)
      }
    },
    setShift(label: string) {
      this.shiftLabel = label
    },
  },
})
