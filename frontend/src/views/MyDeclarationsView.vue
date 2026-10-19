<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, ref, watch } from 'vue'

import { unwrap } from '@/api/client'
import DeclarationDialog from '@/components/DeclarationDialog.vue'
import EvidenceDialog from '@/components/EvidenceDialog.vue'
import YearSelect from '@/components/YearSelect.vue'
import { useAuthStore } from '@/stores/auth'
import { useYearStore } from '@/stores/year'
import { type Catalog, type Declaration, itemName, optionName } from '@/utils/catalog'
import { errorMessage } from '@/utils/errors'
import { DECLARATION_STATUS, scoreText } from '@/utils/format'
import { useNarrow } from '@/utils/viewport'

const narrow = useNarrow()
const auth = useAuthStore()
const years = useYearStore()
const catalog = ref<Catalog | null>(null)
const rows = ref<Declaration[]>([])
const loading = ref(false)
const formOpen = ref(false)
const editing = ref<Declaration | null>(null)
const evidenceOpen = ref(false)
const evidenceOf = ref<Declaration | null>(null)

const yearOpen = computed(() => years.selected?.status === 'open')
const editable = (d: Declaration) =>
  yearOpen.value && (d.status === 'draft' || d.status === 'rejected')

async function load(): Promise<void> {
  const yearId = years.selectedId
  if (yearId === null) {
    rows.value = []
    return
  }
  loading.value = true
  try {
    const [cat, list] = await Promise.all([
      auth.api.GET('/api/v1/years/{year_id}/catalog', { params: { path: { year_id: yearId } } }),
      auth.api.GET('/api/v1/declarations', { params: { query: { mine: true, year_id: yearId } } }),
    ])
    catalog.value = unwrap(cat)
    rows.value = unwrap(list)
    if (evidenceOf.value) {
      evidenceOf.value = rows.value.find((d) => d.id === evidenceOf.value?.id) ?? null
    }
  } catch (e) {
    ElMessage.error(errorMessage(e))
  } finally {
    loading.value = false
  }
}

watch(() => years.selectedId, load, { immediate: true })

function create(): void {
  editing.value = null
  formOpen.value = true
}

function edit(d: Declaration): void {
  editing.value = d
  formOpen.value = true
}

function showEvidence(d: Declaration): void {
  evidenceOf.value = d
  evidenceOpen.value = true
}

async function act(d: Declaration, action: 'submit' | 'withdraw'): Promise<void> {
  const text = action === 'submit' ? '提交后等待审核，期间不能修改。确定提交？' : '确定撤回？'
  try {
    await ElMessageBox.confirm(text, action === 'submit' ? '提交审核' : '撤回申报')
  } catch {
    return
  }
  try {
    const path = { params: { path: { declaration_id: d.id } } }
    unwrap(
      action === 'submit'
        ? await auth.api.POST('/api/v1/declarations/{declaration_id}/submit', path)
        : await auth.api.POST('/api/v1/declarations/{declaration_id}/withdraw', path),
    )
    ElMessage.success(action === 'submit' ? '已提交' : '已撤回')
    await load()
  } catch (e) {
    ElMessage.error(errorMessage(e))
  }
}
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h2>我的申报</h2>
      <div class="toolbar">
        <YearSelect />
        <el-button type="primary" :disabled="!yearOpen" data-testid="decl-new" @click="create">
          新建申报
        </el-button>
      </div>
    </div>
    <el-alert
      v-if="years.selected && !yearOpen"
      title="该学年当前不在申报期，只能查看。"
      type="info"
      :closable="false"
      show-icon
      class="gap"
    />
    <el-table v-loading="loading" :data="rows" empty-text="暂无申报" data-testid="decl-table">
      <el-table-column label="项目" min-width="150">
        <template #default="{ row }">
          <div>{{ itemName(catalog, row.catalog_code) }}</div>
          <div class="muted">{{ optionName(catalog, row.catalog_code, row.option_code) }}</div>
        </template>
      </el-table-column>
      <el-table-column prop="title" label="标题" min-width="160" />
      <el-table-column label="建议分" width="90" class-name="score">
        <template #default="{ row }">{{ scoreText(row.suggested_score) }}</template>
      </el-table-column>
      <el-table-column label="申报分" width="80" class-name="score">
        <template #default="{ row }">{{ scoreText(row.claimed_score) }}</template>
      </el-table-column>
      <el-table-column label="审核分" width="80" class-name="score">
        <template #default="{ row }">{{ scoreText(row.approved_score) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="DECLARATION_STATUS[row.status as Declaration['status']].type as never">
            {{ DECLARATION_STATUS[row.status as Declaration['status']].label }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200" :fixed="narrow ? false : 'right'">
        <template #default="{ row }">
          <el-button link type="primary" @click="showEvidence(row as Declaration)">
            材料({{ row.evidence.length }})
          </el-button>
          <template v-if="editable(row as Declaration)">
            <el-button link type="primary" @click="edit(row as Declaration)">修改</el-button>
            <el-button
              link
              type="success"
              data-testid="decl-submit"
              @click="act(row as Declaration, 'submit')"
            >
              提交
            </el-button>
          </template>
          <el-button
            v-if="yearOpen && row.status !== 'approved' && row.status !== 'withdrawn'"
            link
            type="danger"
            @click="act(row as Declaration, 'withdraw')"
          >
            撤回
          </el-button>
        </template>
      </el-table-column>
    </el-table>
    <DeclarationDialog
      v-if="years.selectedId !== null"
      v-model="formOpen"
      :catalog="catalog"
      :year-id="years.selectedId"
      :declaration="editing"
      @saved="load"
    />
    <EvidenceDialog
      v-model="evidenceOpen"
      :declaration="evidenceOf"
      :editable="evidenceOf ? editable(evidenceOf) : false"
      @changed="load"
    />
  </div>
</template>

<style scoped>
.gap {
  margin-bottom: 12px;
}
</style>
