<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'

import { type Schemas, unwrap } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { useYearStore } from '@/stores/year'
import { errorMessage } from '@/utils/errors'
import { formatTime, YEAR_STATUS } from '@/utils/format'

type Year = Schemas['YearOut']

type YearStatus = Schemas['YearStatus']

// 与后端一致的状态流转（后端会再次校验）：未开放 → 申报中 ⇄ 审核中 → 已结束
const NEXT: Record<YearStatus, YearStatus[]> = {
  draft: ['open'],
  open: ['reviewing'],
  reviewing: ['open', 'closed'],
  closed: [],
}

const auth = useAuthStore()
const years = useYearStore()
const rules = ref<Schemas['RuleVersionOut'][]>([])
const form = reactive({ name: '', rule_version_id: undefined as number | undefined })

async function load(): Promise<void> {
  try {
    rules.value = unwrap(await auth.api.GET('/api/v1/rules'))
    await years.load()
  } catch (e) {
    ElMessage.error(errorMessage(e))
  }
}

onMounted(load)

async function create(): Promise<void> {
  if (!form.name || form.rule_version_id === undefined) {
    ElMessage.warning('请填写学年并选择规则版本')
    return
  }
  try {
    const year = unwrap(
      await auth.api.POST('/api/v1/years', {
        body: { name: form.name, rule_version_id: form.rule_version_id },
      }),
    )
    ElMessage.success(`已新建学年 ${year.name}`)
    form.name = ''
    await years.load()
    years.select(year.id)
  } catch (e) {
    ElMessage.error(errorMessage(e))
  }
}

async function move(year: Schemas['YearOut'], status: YearStatus): Promise<void> {
  try {
    unwrap(
      await auth.api.PATCH('/api/v1/years/{year_id}/status', {
        params: { path: { year_id: year.id } },
        body: { status },
      }),
    )
    ElMessage.success(`${year.name}：${YEAR_STATUS[status]}`)
    await years.load()
  } catch (e) {
    ElMessage.error(errorMessage(e))
  }
}
</script>

<template>
  <section>
    <h3>学年</h3>
    <el-form inline class="toolbar" @submit.prevent="create">
      <el-input v-model.trim="form.name" placeholder="如 2025-2026" style="width: 140px" />
      <el-select v-model="form.rule_version_id" placeholder="规则版本" style="width: 220px">
        <el-option
          v-for="r in rules"
          :key="r.id"
          :value="r.id"
          :label="`${r.rule_id} ${r.version}${r.has_ability_catalog ? '' : '（无申报目录）'}`"
        />
      </el-select>
      <el-button type="primary" native-type="submit">新建学年</el-button>
    </el-form>
    <el-table :data="years.years" size="small" class="gap">
      <el-table-column prop="name" label="学年" min-width="110" />
      <el-table-column label="规则版本" min-width="140">
        <template #default="{ row }">
          {{ rules.find((r) => r.id === row.rule_version_id)?.rule_id }}
          {{ rules.find((r) => r.id === row.rule_version_id)?.version }}
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">{{ YEAR_STATUS[row.status as YearStatus] }}</template>
      </el-table-column>
      <el-table-column label="操作" min-width="180">
        <template #default="{ row }">
          <el-button
            v-for="next in NEXT[row.status as YearStatus]"
            :key="next"
            size="small"
            @click="move(row as Year, next)"
          >
            设为{{ YEAR_STATUS[next] }}
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <h3>规则版本</h3>
    <p class="muted">
      规则用命令行导入：uv run zongce load-rules rules/ujn-v1.json --catalog
      rules/ability-catalog-xxgc-2020.json
    </p>
    <el-table :data="rules" size="small">
      <el-table-column prop="rule_id" label="规则" min-width="100" />
      <el-table-column prop="version" label="版本" width="80" />
      <el-table-column prop="title" label="名称" min-width="200" />
      <el-table-column label="申报目录" width="90">
        <template #default="{ row }">{{ row.has_ability_catalog ? '有' : '无' }}</template>
      </el-table-column>
      <el-table-column label="SHA-256" min-width="120">
        <template #default="{ row }">
          <code>{{ row.sha256.slice(0, 12) }}</code>
        </template>
      </el-table-column>
      <el-table-column label="导入时间" width="150">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
    </el-table>
  </section>
</template>

<style scoped>
.gap {
  margin: 12px 0 24px;
}
</style>
