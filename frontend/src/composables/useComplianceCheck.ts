import { computed, type Ref } from 'vue'
import type { Constraint, ComplianceResult, ComplianceStatus } from '@/types'

export interface ProjectInputsModel {
  stories: number
  bedrooms: number
  bathrooms: number
  sqft: number | null
}

const ESTIMATED_FT_PER_STORY = 10.5
const WARNING_THRESHOLD = 0.9 // warn when within 10% of limit

interface CompareRule {
  getInput: (inputs: ProjectInputsModel, lotArea: number | null) => number | null
  label: string
  unit: string
}

const PARAMETER_MAP: Record<string, CompareRule> = {
  max_stories: {
    getInput: (i) => i.stories,
    label: 'stories',
    unit: 'stories',
  },
  max_height: {
    getInput: (i) => i.stories * ESTIMATED_FT_PER_STORY,
    label: 'est. height',
    unit: 'ft',
  },
  adu_max_height: {
    getInput: (i) => i.stories * ESTIMATED_FT_PER_STORY,
    label: 'est. height',
    unit: 'ft',
  },
  max_floor_area: {
    getInput: (i) => i.sqft,
    label: 'proposed sqft',
    unit: 'sqft',
  },
  adu_max_size: {
    getInput: (i) => i.sqft,
    label: 'proposed sqft',
    unit: 'sqft',
  },
  guest_house_max_size: {
    getInput: (i) => i.sqft,
    label: 'proposed sqft',
    unit: 'sqft',
  },
  max_far: {
    getInput: (i, lotArea) => (i.sqft && lotArea) ? i.sqft / lotArea : null,
    label: 'proposed FAR',
    unit: 'ratio',
  },
}

function checkCompliance(
  inputValue: number,
  limitValue: number,
  inputLabel: string,
  limitUnit: string,
  isMax: boolean,
): ComplianceResult {
  const format = (v: number) => limitUnit === 'ratio' ? v.toFixed(2) : v.toLocaleString()

  if (isMax) {
    if (inputValue > limitValue) {
      return {
        status: 'fail',
        message: `${inputLabel}: ${format(inputValue)} exceeds ${format(limitValue)} ${limitUnit} max`,
        inputValue,
        limitValue,
      }
    }
    if (inputValue > limitValue * WARNING_THRESHOLD) {
      return {
        status: 'warning',
        message: `${inputLabel}: ${format(inputValue)} is close to ${format(limitValue)} ${limitUnit} max`,
        inputValue,
        limitValue,
      }
    }
    return {
      status: 'pass',
      message: `${inputLabel}: ${format(inputValue)} ≤ ${format(limitValue)} ${limitUnit} max`,
      inputValue,
      limitValue,
    }
  }

  // min constraints
  if (inputValue < limitValue) {
    return { status: 'fail', message: `${inputLabel}: ${format(inputValue)} below ${format(limitValue)} ${limitUnit} min`, inputValue, limitValue }
  }
  return { status: 'pass', message: `${inputLabel}: ${format(inputValue)} ≥ ${format(limitValue)} ${limitUnit} min`, inputValue, limitValue }
}

export function useComplianceCheck(
  projectInputs: Ref<ProjectInputsModel>,
  buildingType: Ref<string>,
  constraints: Ref<Constraint[]>,
  lotArea: Ref<number | null>,
) {
  const complianceMap = computed(() => {
    const map = new Map<string, ComplianceResult>()
    const inputs = projectInputs.value

    for (const c of constraints.value) {
      const rule = PARAMETER_MAP[c.parameter]
      if (!rule || c.numeric_value == null) {
        map.set(c.id, { status: 'unknown', message: null, inputValue: null, limitValue: null })
        continue
      }

      // Skip building-type-specific constraints that don't apply
      if (c.parameter === 'adu_max_size' && buildingType.value !== 'ADU') {
        map.set(c.id, { status: 'unknown', message: null, inputValue: null, limitValue: null })
        continue
      }
      if (c.parameter === 'guest_house_max_size' && buildingType.value !== 'Guest House') {
        map.set(c.id, { status: 'unknown', message: null, inputValue: null, limitValue: null })
        continue
      }

      const inputValue = rule.getInput(inputs, lotArea.value)
      if (inputValue == null) {
        map.set(c.id, { status: 'unknown', message: null, inputValue: null, limitValue: null })
        continue
      }

      const isMax = c.parameter.startsWith('max_') || c.parameter.includes('_max_')
      map.set(c.id, checkCompliance(inputValue, c.numeric_value, rule.label, rule.unit, isMax))
    }

    return map
  })

  return { complianceMap }
}
