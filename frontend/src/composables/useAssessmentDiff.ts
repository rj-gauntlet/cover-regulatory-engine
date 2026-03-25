import { computed, type Ref } from 'vue'
import type { Assessment, Constraint, ConstraintDiff } from '@/types'
import { CATEGORY_LABELS } from '@/types'

const CATEGORY_ORDER = ['setback', 'height', 'far', 'density', 'lot', 'use', 'parking', 'adu', 'coverage', 'other']

export function useAssessmentDiff(
  left: Ref<Assessment | null>,
  right: Ref<Assessment | null>,
) {
  const groupedDiffs = computed<[string, ConstraintDiff[]][]>(() => {
    if (!left.value || !right.value) return []

    const leftByParam = new Map<string, Constraint>()
    const rightByParam = new Map<string, Constraint>()

    for (const c of left.value.constraints) leftByParam.set(c.parameter, c)
    for (const c of right.value.constraints) rightByParam.set(c.parameter, c)

    const allParams = new Set([...leftByParam.keys(), ...rightByParam.keys()])
    const diffs: ConstraintDiff[] = []

    for (const param of allParams) {
      const l = leftByParam.get(param) ?? null
      const r = rightByParam.get(param) ?? null
      const isDifferent = !l || !r || l.numeric_value !== r.numeric_value || l.value !== r.value
      diffs.push({
        parameter: param,
        category: l?.category ?? r?.category ?? 'other',
        left: l,
        right: r,
        isDifferent,
      })
    }

    // Group by category
    const groups: Record<string, ConstraintDiff[]> = {}
    for (const d of diffs) {
      if (!groups[d.category]) groups[d.category] = []
      groups[d.category].push(d)
    }

    // Sort by standard category order
    const sorted: [string, ConstraintDiff[]][] = []
    for (const cat of CATEGORY_ORDER) {
      if (groups[cat]) sorted.push([cat, groups[cat]])
    }
    for (const [cat, items] of Object.entries(groups)) {
      if (!CATEGORY_ORDER.includes(cat)) sorted.push([cat, items])
    }

    return sorted
  })

  const diffStats = computed(() => {
    if (!left.value || !right.value) return { total: 0, different: 0, leftOnly: 0, rightOnly: 0 }

    let total = 0, different = 0, leftOnly = 0, rightOnly = 0
    for (const [, diffs] of groupedDiffs.value) {
      for (const d of diffs) {
        total++
        if (!d.left) rightOnly++
        else if (!d.right) leftOnly++
        else if (d.isDifferent) different++
      }
    }
    return { total, different, leftOnly, rightOnly }
  })

  return { groupedDiffs, diffStats }
}
