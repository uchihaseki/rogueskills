import type { RepositoryMetadata, SkillGenome, SkillRecord } from '@/types/domain'

export function loadJson<T>(key: string, fallback: T): T {
  try {
    const value = localStorage.getItem(key)
    return value ? JSON.parse(value) as T : fallback
  } catch {
    return fallback
  }
}

export function saveJson(key: string, value: unknown): void {
  localStorage.setItem(key, JSON.stringify(value))
}

export function recordToGenome(skill: SkillRecord): SkillGenome {
  const repository: RepositoryMetadata = {
    id: skill.id,
    status: skill.status,
    currentVersionId: skill.currentVersionId,
    versions: skill.versions ?? [],
    evaluations: skill.evaluations ?? [],
    snapshots: skill.snapshots ?? [],
  }
  return { ...skill.genome, repository }
}

export function shortDate(value?: string): string {
  if (!value) return '未知'
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  }).format(new Date(value))
}

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}
